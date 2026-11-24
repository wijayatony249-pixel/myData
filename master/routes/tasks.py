"""
Endpoint Penugasan dan Penyerahan Hasil Task (Tasks Dispatch & Result).
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from common.schemas import TaskDispatchRequest, TaskDispatchResponse, TaskResultSubmit
from master.database import get_db
from master.scheduler import dispatch_next_task, record_task_result
from master.fault_monitor import pop_failure_detected_time
from master.sse_manager import sse_manager
from master.models import Event

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/next", response_model=TaskDispatchResponse)
async def get_next_task(req: TaskDispatchRequest, db: AsyncSession = Depends(get_db)):
    """Worker memanggil endpoint ini untuk mengambil task berikutnya (Pull-based)."""
    task_info = await dispatch_next_task(db, req.worker_id)
    if not task_info:
        return TaskDispatchResponse(has_task=False)
        
    await db.commit()
    await sse_manager.broadcast("task_dispatched", {
        "worker_id": req.worker_id,
        "task_id": task_info["task_id"],
        "chunk_id": task_info["chunk_id"],
        "iteration": task_info["iteration"]
    })
    
    return TaskDispatchResponse(**task_info)

@router.post("/{task_id}/result")
async def submit_task_result(task_id: int, res: TaskResultSubmit, db: AsyncSession = Depends(get_db)):
    """Worker mengirimkan hasil komputasi parsial task."""
    result = await record_task_result(db, res)
    
    # Hitung Recovery Time jika task ini sebelumnya pernah terdeteksi gagal
    detected_down_time = pop_failure_detected_time(task_id)
    if detected_down_time:
        recovery_time_s = (datetime.utcnow() - detected_down_time).total_seconds()
        ev = Event(
            job_id=res.job_id,
            task_id=task_id,
            worker_id=res.worker_id,
            type="TASK_RECOVERED",
            detail={
                "recovery_time_seconds": recovery_time_s,
                "completed_by_worker": res.worker_id,
                "attempt": res.attempt
            }
        )
        db.add(ev)
        await db.commit()
        await sse_manager.broadcast("task_recovered", {
            "task_id": task_id,
            "worker_id": res.worker_id,
            "recovery_time_s": recovery_time_s
        })
        
    await sse_manager.broadcast("task_completed", {
        "task_id": task_id,
        "worker_id": res.worker_id,
        "compute_ms": res.compute_ms,
        "transfer_ms": res.transfer_ms,
        "cache_hit": res.cache_hit
    })
    
    return result
