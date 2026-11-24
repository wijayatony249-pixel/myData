"""
Endpoint Injeksi Kegagalan (Fault Injection: Kill, Hang, Mute) untuk Pengujian Resiliensi.
"""

from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import WORKER_PORT
from master.database import get_db
from master.models import Worker, Event
from master.sse_manager import sse_manager

router = APIRouter(prefix="/faults", tags=["Faults"])

@router.post("/{action}/{worker_id}")
async def inject_fault(action: str, worker_id: str, db: AsyncSession = Depends(get_db)):
    """
    Menyuntikkan kegagalan ke Worker:
    - kill: mematikan proses worker seketika menggunakan psutil
    - hang: mensimulasikan freeze/deadlock tak berujung
    - mute: mematikan heartbeat dan request keluar (simulasi putus jaringan)
    """
    if action not in ["kill", "hang", "mute"]:
        raise HTTPException(status_code=400, detail=f"Aksi kegagalan '{action}' tidak valid (pilihan: kill, hang, mute)")
        
    q = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = q.scalars().first()
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker #{worker_id} tidak ditemukan")
        
    worker_url = f"http://{worker.ip}:{WORKER_PORT}/admin/{action}"
    
    # Catat event fault injection
    ev = Event(
        worker_id=worker_id,
        type="FAULT_INJECTED",
        detail={"action": action, "target_url": worker_url}
    )
    db.add(ev)
    await db.commit()
    
    # Kirim perintah ke Worker melalui HTTP
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(worker_url)
            msg = resp.json().get("message", "Perintah berhasil dieksekusi")
    except Exception as e:
        msg = f"Perintah dikirim (Worker mungkin langsung offline): {e}"
        
    await sse_manager.broadcast("fault_injected", {
        "worker_id": worker_id,
        "action": action,
        "detail": msg
    })
    
    return {
        "status": "injected",
        "action": action,
        "worker_id": worker_id,
        "detail": msg
    }
