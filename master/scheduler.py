"""
Scheduler & Load Balancer Master myData.
Mengelola antrean task (Dynamic pull-based vs Static round-robin), lease waktu, retry, dan barrier iterasi K-Means.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json
import numpy as np
import pandas as pd
from sqlalchemy import select, and_, or_, update
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import LEASE_DURATION_SEC, MAX_TASK_ATTEMPTS
from common.algorithms import (
    prepare_kmeans_features, init_kmeans_plus_plus,
    j1_reduce, j2_reduce, j3_reduce, j4_reduce_iteration
)
from master.models import Job, Task, Chunk, Worker, Event, Dataset
from master.sse_manager import sse_manager

# Penyimpanan hasil parsial task di memori selama job aktif
_PARTIAL_RESULTS_STORE: Dict[int, Dict[int, Dict[str, Any]]] = {} # {job_id: {task_id: partial_result}}

async def create_job_tasks(db: AsyncSession, job: Job, dataset_id: int):
    """Membuat gelombang task pertama untuk job baru."""
    # Ambil seluruh chunk dari dataset
    q_chunks = await db.execute(select(Chunk).where(Chunk.dataset_id == dataset_id).order_by(Chunk.id))
    chunks = q_chunks.scalars().all()
    if not chunks:
        raise ValueError("Dataset tidak memiliki chunk. Harap siapkan dataset terlebih dahulu.")
        
    # Ambil worker aktif jika mode STATIC round-robin
    active_workers = []
    if job.lb_mode == "STATIC":
        q_workers = await db.execute(select(Worker).where(Worker.status == "ACTIVE").order_by(Worker.id))
        active_workers = q_workers.scalars().all()
        if not active_workers:
            # Fallback jika belum ada worker terdaftar
            q_any = await db.execute(select(Worker).order_by(Worker.id))
            active_workers = q_any.scalars().all()

    # Inisialisasi K-Means jika J4
    if job.type == "J4_KMEANS":
        params = dict(job.params or {})
        k = params.get("k", 8)
        seed = job.seed
        
        # Sampling dari chunk pertama untuk K-Means++
        first_chunk_path = chunks[0].path
        df_sample = pd.read_parquet(first_chunk_path)
        sample_subset = df_sample.sample(n=min(10000, len(df_sample)), random_state=seed)
        
        # Ekstrak fitur standar sederhana
        norm_params = params.get("norm_params", {})
        feat_sample = prepare_kmeans_features(sample_subset, norm_params)
        centroids = init_kmeans_plus_plus(feat_sample, k=k, seed=seed)
        
        params["centroids"] = centroids.tolist()
        params["iteration"] = 0
        params["k"] = k
        job.params = params

    # Buat entri task untuk setiap chunk
    for idx, c in enumerate(chunks):
        assigned_worker = None
        if job.lb_mode == "STATIC" and active_workers:
            assigned_worker = active_workers[idx % len(active_workers)].id
            
        task = Task(
            job_id=job.id,
            chunk_id=c.id,
            iteration=0,
            status="PENDING",
            attempt=1,
            assigned_worker_id=assigned_worker
        )
        db.add(task)
        
    _PARTIAL_RESULTS_STORE[job.id] = {}
    await db.flush()

async def dispatch_next_task(db: AsyncSession, worker_id: str) -> Optional[Dict[str, Any]]:
    """
    Mengalokasikan task berikutnya ke Worker (Pull-based).
    Mendukung Dynamic Load Balancing dan Static Assigned Task.
    """
    now = datetime.utcnow()
    
    # 1. Pastikan ada Job berstatus RUNNING atau PENDING
    q_job = await db.execute(
        select(Job).where(Job.status.in_(["RUNNING", "PENDING"])).order_by(Job.id).limit(1)
    )
    job = q_job.scalars().first()
    if not job:
        return None
        
    if job.status == "PENDING":
        job.status = "RUNNING"
        job.started_at = now
        await db.flush()
        
    # 2. Cari task berstatus PENDING atau REQUEUED untuk job ini
    conditions = [
        Task.job_id == job.id,
        Task.status.in_(["PENDING", "REQUEUED"])
    ]
    
    # Jika mode statis, worker hanya boleh mengambil task miliknya
    if job.lb_mode == "STATIC":
        conditions.append(Task.assigned_worker_id == worker_id)
        
    q_task = await db.execute(
        select(Task).where(and_(*conditions)).order_by(Task.attempt.desc(), Task.id).limit(1)
    )
    task = q_task.scalars().first()
    
    # Fallback mode statis jika task milik worker yang mati perlu di-requeue ke worker ini
    if not task and job.lb_mode == "STATIC":
        q_requeued = await db.execute(
            select(Task).where(
                and_(Task.job_id == job.id, Task.status == "REQUEUED")
            ).order_by(Task.id).limit(1)
        )
        task = q_requeued.scalars().first()
        if task:
            # Re-assign ke worker ini dan catat event
            task.assigned_worker_id = worker_id
            ev = Event(
                job_id=job.id,
                task_id=task.id,
                worker_id=worker_id,
                type="STATIC_TASK_REASSIGNED",
                detail={"reason": "Worker sebelumnya down, dialihkan ke worker aktif"}
            )
            db.add(ev)

    if not task:
        return None
        
    # 3. Berikan lease pada task
    task.status = "RUNNING"
    task.worker_id = worker_id
    task.started_at = now
    task.leased_until = now + timedelta(seconds=LEASE_DURATION_SEC)
    
    # Ambil info chunk
    q_chunk = await db.execute(select(Chunk).where(Chunk.id == task.chunk_id))
    chunk = q_chunk.scalars().first()
    
    await db.flush()
    
    return {
        "has_task": True,
        "task_id": task.id,
        "job_id": job.id,
        "job_type": job.type,
        "chunk_id": chunk.id,
        "chunk_download_url": f"/chunks/{chunk.id}",
        "checksum": chunk.checksum,
        "iteration": task.iteration,
        "attempt": task.attempt,
        "params": job.params,
        "lease_seconds": LEASE_DURATION_SEC
    }

async def record_task_result(db: AsyncSession, submit_data: Any) -> Dict[str, Any]:
    """
    Menyimpan hasil parsial task.
    Menerapkan idempotensi hasil (abaikan jika attempt lama atau task sudah selesai).
    """
    q_task = await db.execute(select(Task).where(Task.id == submit_data.task_id))
    task = q_task.scalars().first()
    if not task:
        return {"status": "error", "message": "Task tidak ditemukan"}
        
    # Pemeriksaan Idempotensi
    if task.status == "DONE":
        return {"status": "ignored", "message": "Task sudah selesai sebelumnya"}
    if submit_data.attempt < task.attempt:
        return {"status": "ignored", "message": "Attempt kadaluarsa ditolak"}
        
    now = datetime.utcnow()
    task.status = "DONE"
    task.finished_at = now
    task.compute_ms = submit_data.compute_ms
    task.transfer_ms = submit_data.transfer_ms
    task.cache_hit = submit_data.cache_hit
    task.result = submit_data.partial_result
    task.duration_ms = (now - task.started_at).total_seconds() * 1000.0 if task.started_at else submit_data.compute_ms
    
    # Simpan hasil parsial di memory store
    if submit_data.job_id not in _PARTIAL_RESULTS_STORE:
        _PARTIAL_RESULTS_STORE[submit_data.job_id] = {}
    _PARTIAL_RESULTS_STORE[submit_data.job_id][task.id] = submit_data.partial_result
    
    # Flush status task agar query unfinished mendeteksi task yang baru selesai
    await db.flush()
    
    # Periksa apakah semua task pada gelombang/iterasi ini sudah selesai
    q_job = await db.execute(select(Job).where(Job.id == submit_data.job_id))
    job = q_job.scalars().first()
    
    q_unfinished = await db.execute(
        select(Task).where(
            and_(Task.job_id == job.id, Task.status != "DONE")
        )
    )
    unfinished = q_unfinished.scalars().all()
    
    if len(unfinished) == 0:
        # Seluruh task iterasi saat ini selesai! Panggil Reduce Barrier
        await _handle_barrier_completion(db, job)
        
    await db.commit()
    return {"status": "success", "message": "Hasil task berhasil dicatat"}

async def _handle_barrier_completion(db: AsyncSession, job: Job):
    """Menangani penggabungan hasil saat barrier iterasi tercapai."""
    params = dict(job.params or {})
    current_iter = params.get("iteration", 0)
    
    # Ambil partial results dari DB
    q_tasks = await db.execute(
        select(Task).where(
            and_(Task.job_id == job.id, Task.iteration == current_iter, Task.status == "DONE")
        )
    )
    iter_tasks = q_tasks.scalars().all()
    partial_results = [t.result for t in iter_tasks if t.result is not None]
    if not partial_results:
        job_store = _PARTIAL_RESULTS_STORE.get(job.id, {})
        partial_results = list(job_store.values())
    
    if job.type in ["J1_STATS", "J2_GROUPBY", "J3_CORR"]:
        # Job satu putaran (non-iteratif)
        if job.type == "J1_STATS":
            final_res = j1_reduce(partial_results)
        elif job.type == "J2_GROUPBY":
            final_res = j2_reduce(partial_results)
        else:
            target_cols = ["passenger_count", "trip_distance", "fare_amount", "tip_amount", "total_amount", "duration_minutes"]
            final_res = j3_reduce(partial_results, target_cols)
            
        job.status = "COMPLETED"
        job.finished_at = datetime.utcnow()
        job.result = final_res
        flag_modified(job, "result")
        _PARTIAL_RESULTS_STORE.pop(job.id, None)
        await sse_manager.broadcast("job_completed", {"job_id": job.id, "status": "COMPLETED"})
        
    elif job.type == "J4_KMEANS":
        # Barrier iterasi K-Means
        current_centroids = np.array(params["centroids"], dtype=np.float64)
        new_centroids, shift, counts = j4_reduce_iteration(partial_results, current_centroids)
        
        iteration = current_iter + 1
        max_iter = params.get("max_iter", 15)
        
        # Cek kriteria konvergensi (shift < 1e-4) atau batas iterasi
        if shift < 1e-4 or iteration >= max_iter:
            job.status = "COMPLETED"
            job.finished_at = datetime.utcnow()
            job.result = {
                "k": params.get("k", 8),
                "iterations": iteration,
                "final_shift": shift,
                "cluster_counts": counts,
                "centroids": new_centroids.tolist()
            }
            flag_modified(job, "result")
            _PARTIAL_RESULTS_STORE.pop(job.id, None)
            await sse_manager.broadcast("job_completed", {"job_id": job.id, "status": "COMPLETED"})
        else:
            # Lanjut ke iterasi berikutnya
            params["centroids"] = new_centroids.tolist()
            params["iteration"] = iteration
            job.params = params
            flag_modified(job, "params")
            
            # Reset memory store untuk iterasi baru
            _PARTIAL_RESULTS_STORE[job.id] = {}
            
            # Buat gelombang task berikutnya untuk iterasi baru
            q_chunks = await db.execute(select(Chunk).where(Chunk.dataset_id == job.params.get("dataset_id", 1)).order_by(Chunk.id))
            chunks = q_chunks.scalars().all()
            for c in chunks:
                new_task = Task(
                    job_id=job.id,
                    chunk_id=c.id,
                    iteration=iteration,
                    status="PENDING",
                    attempt=1
                )
                db.add(new_task)
