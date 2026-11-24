"""
Endpoint Pengelolaan Worker (Registrasi, Heartbeat, Monitoring).
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import CLUSTER_TOKEN, LEASE_DURATION_SEC
from common.schemas import (
    WorkerRegisterRequest, WorkerRegisterResponse,
    WorkerHeartbeatRequest, WorkerHeartbeatResponse
)
from master.database import get_db
from master.models import Worker, Metric, Task
from master.sse_manager import sse_manager

router = APIRouter(prefix="/workers", tags=["Workers"])

def verify_token(x_cluster_token: str = Header(None)):
    """Verifikasi token keamanan cluster jika header disertakan."""
    if x_cluster_token and x_cluster_token != CLUSTER_TOKEN:
        raise HTTPException(status_code=403, detail="Cluster token tidak valid")

@router.post("/register", response_model=WorkerRegisterResponse)
async def register_worker(
    req: WorkerRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _token: None = Depends(verify_token)
):
    """Mendaftarkan Worker baru atau memperbarui status Worker yang baru pulih."""
    now = datetime.utcnow()
    q = await db.execute(select(Worker).where(Worker.id == req.id))
    worker = q.scalars().first()
    
    if worker:
        # Worker pulih dan mendaftar kembali
        worker.hostname = req.hostname
        worker.ip = req.ip
        worker.os = req.os
        worker.python_version = req.python_version
        worker.cpu_model = req.cpu_model
        worker.cores = req.cores
        worker.ram_mb = req.ram_mb
        worker.status = "ACTIVE"
        worker.last_heartbeat = now
    else:
        # Worker baru pertama kali mendaftar
        worker = Worker(
            id=req.id,
            hostname=req.hostname,
            ip=req.ip,
            os=req.os,
            python_version=req.python_version,
            cpu_model=req.cpu_model,
            cores=req.cores,
            ram_mb=req.ram_mb,
            status="ACTIVE",
            last_heartbeat=now
        )
        db.add(worker)
        
    await db.commit()
    
    # Broadcast status ke SSE
    await sse_manager.broadcast("worker_registered", {
        "id": req.id,
        "hostname": req.hostname,
        "os": req.os,
        "cores": req.cores
    })
    
    return WorkerRegisterResponse(
        status="registered",
        message=f"Worker {req.id} ({req.hostname}) berhasil terdaftar",
        cluster_token_valid=True
    )

@router.post("/{worker_id}/heartbeat", response_model=WorkerHeartbeatResponse)
async def worker_heartbeat(
    worker_id: str,
    req: WorkerHeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    _token: None = Depends(verify_token)
):
    """Menerima denyut detak (heartbeat) dan memperpanjang lease task aktif."""
    now = datetime.utcnow()
    q = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = q.scalars().first()
    
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} belum terdaftar")
        
    worker.status = "ACTIVE"
    worker.last_heartbeat = now
    
    # Simpan metrik utilisasi ke DB
    metric_entry = Metric(
        worker_id=worker_id,
        ts=now,
        cpu_pct=req.cpu_pct,
        mem_pct=req.mem_pct
    )
    db.add(metric_entry)
    
    # Perpanjang lease task jika ada task aktif
    lease_extended = False
    if req.active_task_id:
        q_task = await db.execute(select(Task).where(Task.id == req.active_task_id))
        task = q_task.scalars().first()
        if task and task.status == "RUNNING" and task.worker_id == worker_id:
            task.leased_until = now + timedelta(seconds=LEASE_DURATION_SEC)
            lease_extended = True
            
    await db.commit()
    
    # Kirim update ke web UI secara berkala lewat SSE
    await sse_manager.broadcast("heartbeat", {
        "worker_id": worker_id,
        "cpu_pct": req.cpu_pct,
        "mem_pct": req.mem_pct,
        "status": "ACTIVE",
        "active_task_id": req.active_task_id
    })
    
    return WorkerHeartbeatResponse(
        acknowledged=True,
        lease_extended=lease_extended,
        server_time=now
    )

@router.get("")
async def list_workers(db: AsyncSession = Depends(get_db)):
    """Mengembalikan daftar seluruh Worker yang terdaftar beserta status terkininya."""
    q = await db.execute(select(Worker).order_by(Worker.id))
    workers = q.scalars().all()
    
    result = []
    for w in workers:
        result.append({
            "id": w.id,
            "hostname": w.hostname,
            "ip": w.ip,
            "os": w.os,
            "python_version": w.python_version,
            "cpu_model": w.cpu_model,
            "cores": w.cores,
            "ram_mb": w.ram_mb,
            "status": w.status,
            "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None
        })
    return result
