"""
Endpoint Pengelolaan Dataset (Prepare, Daftar, dan Status Chunk).
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.schemas import DatasetPrepareRequest, DatasetInfo
from master.database import get_db, AsyncSessionLocal
from master.models import Dataset, Chunk
from scripts.prepare_dataset import prepare_and_chunk_dataset
from common.config import CHUNK_SIZE

router = APIRouter(prefix="/datasets", tags=["Datasets"])

@router.post("/prepare")
async def prepare_dataset(req: DatasetPrepareRequest, background_tasks: BackgroundTasks):
    """Menyiapkan dataset: pembersihan dan chunking ke format Parquet."""
    def _run_preparation():
        meta = prepare_and_chunk_dataset(chunk_size=req.chunk_size)
        # Catat ke database
        import asyncio
        async def _save():
            async with AsyncSessionLocal() as db:
                ds = Dataset(
                    name=req.name,
                    source_url=req.source_url or "Synthetic NYC Taxi",
                    total_rows_raw=meta["total_rows_raw"],
                    total_rows_clean=meta["total_rows_clean"],
                    chunk_count=meta["chunk_count"]
                )
                db.add(ds)
                await db.flush()
                
                for c in meta["chunks"]:
                    chunk_entry = Chunk(
                        dataset_id=ds.id,
                        row_start=c["row_start"],
                        row_end=c["row_end"],
                        path=c["path"],
                        size_bytes=c["size_bytes"],
                        checksum=c["checksum"]
                    )
                    db.add(chunk_entry)
                await db.commit()
        asyncio.run(_save())

    background_tasks.add_task(_run_preparation)
    return {"status": "processing", "message": "Proses persiapan dataset dimulai di latar belakang"}

@router.get("")
async def list_datasets(db: AsyncSession = Depends(get_db)):
    """Mengembalikan daftar seluruh dataset yang tersedia di klaster."""
    q = await db.execute(select(Dataset).order_by(Dataset.id.desc()))
    datasets = q.scalars().all()
    
    result = []
    for d in datasets:
        q_chunks = await db.execute(select(Chunk).where(Chunk.dataset_id == d.id).order_by(Chunk.id))
        chunks = q_chunks.scalars().all()
        result.append({
            "id": d.id,
            "name": d.name,
            "source_url": d.source_url,
            "total_rows_raw": d.total_rows_raw,
            "total_rows_clean": d.total_rows_clean,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "chunks": [
                {
                    "id": c.id,
                    "row_start": c.row_start,
                    "row_end": c.row_end,
                    "size_bytes": c.size_bytes,
                    "checksum": c.checksum
                } for c in chunks
            ]
        })
    return result
