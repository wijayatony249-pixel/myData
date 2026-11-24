"""
Endpoint Pengunduhan Data Chunk Parquet secara Biner (HTTP Binary Transfer).
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from master.database import get_db
from master.models import Chunk

router = APIRouter(prefix="/chunks", tags=["Chunks"])

@router.get("/{chunk_id}")
async def download_chunk(chunk_id: int, db: AsyncSession = Depends(get_db)):
    """Mengirimkan file biner chunk Parquet terkompresi dengan checksum di header."""
    q = await db.execute(select(Chunk).where(Chunk.id == chunk_id))
    chunk = q.scalars().first()
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk #{chunk_id} tidak ditemukan")
        
    chunk_path = Path(chunk.path)
    if not chunk_path.exists():
        raise HTTPException(status_code=404, detail=f"Berkas fisik chunk tidak ditemukan di {chunk_path}")
        
    headers = {
        "X-Checksum-SHA256": chunk.checksum,
        "X-Row-Start": str(chunk.row_start),
        "X-Row-End": str(chunk.row_end)
    }
    
    return FileResponse(
        path=chunk_path,
        media_type="application/octet-stream",
        filename=chunk_path.name,
        headers=headers
    )
