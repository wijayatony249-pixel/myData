"""
Monitor Kegagalan (Fault Monitor) Master myData.
Memantau heartbeat worker (timeout 6 dtk -> DOWN), memeriksa kedaluwarsa lease (30 dtk),
serta melakukan re-queue task otomatis ke antrean depan.
"""

import asyncio
from datetime import datetime, timedelta
import logging
from sqlalchemy import select, and_, or_
from master.database import AsyncSessionLocal
from master.models import Worker, Task, Job, Event
from common.config import HEARTBEAT_TIMEOUT_SEC, MAX_TASK_ATTEMPTS

logger = logging.getLogger("fault_monitor")

# Kamus pelacak waktu deteksi kegagalan task untuk perhitungan Recovery Time
_FAILURE_TIMESTAMPS: dict[int, datetime] = {} # {task_id: detected_down_time}

async def run_fault_monitor_loop(poll_interval: float = 1.0):
    """Loop latar belakang berkala untuk memeriksa kesehatan worker dan task lease."""
    logger.info("[*] Fault Monitor aktif memantau deteksi kegagalan & lease...")
    while True:
        try:
            await check_worker_heartbeats_and_leases()
        except Exception as e:
            logger.error(f"[!] Kesalahan pada fault monitor: {e}")
        await asyncio.sleep(poll_interval)

async def check_worker_heartbeats_and_leases():
    """Pemeriksaan heartbeat worker dan perpanjangan lease."""
    now = datetime.utcnow()
    timeout_threshold = now - timedelta(seconds=HEARTBEAT_TIMEOUT_SEC)
    
    async with AsyncSessionLocal() as db:
        # 1. Deteksi Worker yang tidak mengirim heartbeat > HEARTBEAT_TIMEOUT_SEC
        q_down_workers = await db.execute(
            select(Worker).where(
                and_(
                    Worker.status != "DOWN",
                    Worker.last_heartbeat < timeout_threshold
                )
            )
        )
        down_workers = q_down_workers.scalars().all()
        
        for w in down_workers:
            w.status = "DOWN"
            logger.warning(f"[!] Worker {w.id} ({w.hostname}) terdeteksi DOWN (tanpa heartbeat > {HEARTBEAT_TIMEOUT_SEC}s)")
            
            # Catat event kegagalan worker
            ev = Event(
                worker_id=w.id,
                type="WORKER_DOWN",
                detail={
                    "reason": f"Heartbeat terputus lebih dari {HEARTBEAT_TIMEOUT_SEC} detik",
                    "last_heartbeat": w.last_heartbeat.isoformat()
                }
            )
            db.add(ev)
            
            # Cari task aktif yang sedang dikerjakan worker ini
            q_tasks = await db.execute(
                select(Task).where(
                    and_(
                        Task.worker_id == w.id,
                        Task.status.in_(["RUNNING", "ASSIGNED"])
                    )
                )
            )
            affected_tasks = q_tasks.scalars().all()
            for t in affected_tasks:
                _FAILURE_TIMESTAMPS[t.id] = now
                if t.attempt >= MAX_TASK_ATTEMPTS:
                    t.status = "FAILED"
                    logger.error(f"[X] Task #{t.id} gagal permanen (mencapai batas {MAX_TASK_ATTEMPTS} attempt)")
                else:
                    t.status = "REQUEUED"
                    t.attempt += 1
                    t.worker_id = None
                    t.leased_until = None
                    logger.info(f"[*] Task #{t.id} di-REQUEUE ke antrean depan (Attempt baru: {t.attempt})")
                    
                ev_task = Event(
                    job_id=t.job_id,
                    task_id=t.id,
                    worker_id=w.id,
                    type="TASK_REQUEUED",
                    detail={
                        "reason": f"Worker {w.id} mati saat mengerjakan task",
                        "attempt": t.attempt,
                        "failure_detected_at": now.isoformat()
                    }
                )
                db.add(ev_task)
                
        # 2. Periksa lease task yang kedaluwarsa meskipun worker masih dianggap aktif
        q_expired_tasks = await db.execute(
            select(Task).where(
                and_(
                    Task.status == "RUNNING",
                    Task.leased_until < now
                )
            )
        )
        expired_tasks = q_expired_tasks.scalars().all()
        for t in expired_tasks:
            _FAILURE_TIMESTAMPS[t.id] = now
            if t.attempt >= MAX_TASK_ATTEMPTS:
                t.status = "FAILED"
            else:
                t.status = "REQUEUED"
                t.attempt += 1
                t.worker_id = None
                t.leased_until = None
                logger.info(f"[*] Task #{t.id} lease kedaluwarsa, di-REQUEUE (Attempt: {t.attempt})")
                
            ev_lease = Event(
                job_id=t.job_id,
                task_id=t.id,
                type="LEASE_EXPIRED",
                detail={"attempt": t.attempt, "expired_at": now.isoformat()}
            )
            db.add(ev_lease)
            
        await db.commit()

def pop_failure_detected_time(task_id: int) -> datetime:
    """Mengambil dan menghapus waktu deteksi kegagalan untuk perhitungan recovery time."""
    return _FAILURE_TIMESTAMPS.pop(task_id, None)
