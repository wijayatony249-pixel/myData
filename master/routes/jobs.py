"""
Endpoint Pembuatan, Monitoring, dan Pembatalan Pekerjaan Data Mining (Jobs).
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from common.schemas import JobCreateRequest, JobResponse
from master.database import get_db, AsyncSessionLocal
from master.models import Job, Task, Dataset, Chunk
from master.scheduler import create_job_tasks
from master.sse_manager import sse_manager
from baseline.sequential_runner import (
    load_all_chunks, run_j1_sequential, run_j2_sequential, run_j3_sequential, run_j4_sequential
)
from baseline.local_parallel_runner import (
    run_j1_parallel, run_j2_parallel, run_j3_parallel, run_j4_parallel
)
import concurrent.futures
import multiprocessing as mp
from common.config import CHUNKS_DIR

router = APIRouter(prefix="/jobs", tags=["Jobs"])

def _execute_local_job(job_id: int, mode: str, job_type: str, params: dict, seed: int, n_proc: int):
    """Menjalankan job mode Sequential atau Paralel Lokal secara mandiri di Master."""
    import asyncio
    async def _runner():
        async with AsyncSessionLocal() as db:
            q_job = await db.execute(select(Job).where(Job.id == job_id))
            job = q_job.scalars().first()
            if not job:
                return
            job.status = "RUNNING"
            job.started_at = datetime.utcnow()
            await db.commit()

        try:
            res = {}
            if mode == "SEQUENTIAL":
                chunks = load_all_chunks()
                if job_type == "J1_STATS":
                    res = run_j1_sequential(chunks)
                elif job_type == "J2_GROUPBY":
                    res = run_j2_sequential(chunks)
                elif job_type == "J3_CORR":
                    res = run_j3_sequential(chunks)
                elif job_type == "J4_KMEANS":
                    k = params.get("k", 8)
                    max_iter = params.get("max_iter", 15)
                    res = run_j4_sequential(chunks, k=k, max_iter=max_iter, seed=seed)
            else:
                # LOCAL_PARALLEL
                chunk_files = sorted([str(p) for p in CHUNKS_DIR.glob("chunk_*.parquet")])
                ctx = mp.get_context("spawn")
                workers_count = n_proc if n_proc > 0 else mp.cpu_count()
                with concurrent.futures.ProcessPoolExecutor(max_workers=workers_count, mp_context=ctx) as pool:
                    if job_type == "J1_STATS":
                        res = run_j1_parallel(chunk_files, pool)
                    elif job_type == "J2_GROUPBY":
                        res = run_j2_parallel(chunk_files, pool)
                    elif job_type == "J3_CORR":
                        res = run_j3_parallel(chunk_files, pool)
                    elif job_type == "J4_KMEANS":
                        k = params.get("k", 8)
                        max_iter = params.get("max_iter", 15)
                        res = run_j4_parallel(chunk_files, pool, k=k, max_iter=max_iter, seed=seed)

            async with AsyncSessionLocal() as db:
                q_job = await db.execute(select(Job).where(Job.id == job_id))
                job = q_job.scalars().first()
                if job:
                    job.status = "COMPLETED"
                    job.finished_at = datetime.utcnow()
                    job.result = res
                    # Tandai task dummy selesai
                    q_tasks = await db.execute(select(Task).where(Task.job_id == job_id))
                    for t in q_tasks.scalars().all():
                        t.status = "DONE"
                    await db.commit()
                    
            await sse_manager.broadcast("job_completed", {"job_id": job_id, "status": "COMPLETED"})
        except Exception as e:
            async with AsyncSessionLocal() as db:
                q_job = await db.execute(select(Job).where(Job.id == job_id))
                job = q_job.scalars().first()
                if job:
                    job.status = "FAILED"
                    job.finished_at = datetime.utcnow()
                    job.result = {"error": str(e)}
                    await db.commit()

    asyncio.run(_runner())

@router.post("")
async def create_job(req: JobCreateRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Membuat job data mining baru.
    Aturan PRD: Hanya satu job aktif pada satu waktu.
    Jika mode SEQUENTIAL atau LOCAL_PARALLEL, Master mengeksekusi langsung tanpa butuh Worker jaringan.
    """
    # Periksa apakah ada job yang masih RUNNING
    q_active = await db.execute(
        select(Job).where(Job.status.in_(["RUNNING"]))
    )
    if q_active.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="Terdapat job lain yang sedang berjalan aktif. Tunggu hingga klaster idle."
        )
        
    # Ambil dataset target (default ke dataset pertama jika tidak dispesifikasikan)
    ds_id = req.dataset_id
    if not ds_id:
        q_ds = await db.execute(select(Dataset).order_by(Dataset.id.desc()).limit(1))
        ds = q_ds.scalars().first()
        if not ds:
            raise HTTPException(status_code=400, detail="Tidak ada dataset. Siapkan dataset terlebih dahulu.")
        ds_id = ds.id
        
    job = Job(
        type=req.type.value,
        mode=req.mode.value,
        lb_mode=req.lb_mode.value,
        n_workers=req.n_workers,
        params=req.params or {"dataset_id": ds_id},
        seed=req.seed,
        status="PENDING",
        started_at=datetime.utcnow()
    )
    db.add(job)
    await db.flush()
    
    # Buat entri task
    await create_job_tasks(db, job, dataset_id=ds_id)
    await db.commit()
    
    await sse_manager.broadcast("job_created", {
        "job_id": job.id,
        "type": job.type,
        "mode": job.mode,
        "lb_mode": job.lb_mode
    })
    
    # Jika mode Sequential atau Paralel Lokal, Master jalankan sendiri di background
    if job.mode in ["SEQUENTIAL", "LOCAL_PARALLEL"]:
        background_tasks.add_task(
            _execute_local_job,
            job.id,
            job.mode,
            job.type,
            job.params or {},
            job.seed,
            job.n_workers or 0
        )
    
    return {"status": "created", "job_id": job.id, "message": f"Job #{job.id} ({job.type}) siap dieksekusi"}

@router.get("/{job_id}")
async def get_job_detail(job_id: int, db: AsyncSession = Depends(get_db)):
    """Mengambil detail, progres task, dan hasil akhir job."""
    q_job = await db.execute(select(Job).where(Job.id == job_id))
    job = q_job.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job #{job_id} tidak ditemukan")
        
    q_tasks = await db.execute(select(Task).where(Task.job_id == job_id).order_by(Task.id))
    tasks = q_tasks.scalars().all()
    
    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t.status == "DONE")
    progress_pct = (done_tasks / total_tasks * 100.0) if total_tasks > 0 else 0.0
    
    duration_s = None
    if job.started_at:
        end_time = job.finished_at or datetime.utcnow()
        duration_s = (end_time - job.started_at).total_seconds()
        
    return {
        "id": job.id,
        "type": job.type,
        "mode": job.mode,
        "lb_mode": job.lb_mode,
        "n_workers": job.n_workers,
        "status": job.status,
        "seed": job.seed,
        "progress_pct": round(progress_pct, 1),
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "duration_s": duration_s,
        "result": job.result,
        "tasks": [
            {
                "id": t.id,
                "chunk_id": t.chunk_id,
                "iteration": t.iteration,
                "status": t.status,
                "attempt": t.attempt,
                "worker_id": t.worker_id,
                "duration_ms": t.duration_ms,
                "compute_ms": t.compute_ms,
                "transfer_ms": t.transfer_ms,
                "cache_hit": t.cache_hit
            } for t in tasks
        ]
    }

@router.post("/{job_id}/cancel")
async def cancel_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Membatalkan job yang sedang berjalan."""
    q_job = await db.execute(select(Job).where(Job.id == job_id))
    job = q_job.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
        
    job.status = "CANCELLED"
    job.finished_at = datetime.utcnow()
    await db.commit()
    
    await sse_manager.broadcast("job_cancelled", {"job_id": job_id})
    return {"status": "cancelled", "message": f"Job #{job_id} berhasil dibatalkan"}

@router.get("")
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """Mengembalikan daftar semua pekerjaan."""
    q = await db.execute(select(Job).order_by(Job.id.desc()))
    jobs = q.scalars().all()
    return [
        {
            "id": j.id,
            "type": j.type,
            "mode": j.mode,
            "lb_mode": j.lb_mode,
            "status": j.status,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None
        } for j in jobs
    ]
