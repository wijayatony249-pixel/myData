"""
Endpoint Eksekusi Benchmark Otomatis Skenario A s/d F dan Ekspor Data (CSV/JSON).
"""

import io
import csv
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.schemas import BenchmarkRunRequest
from master.database import get_db, AsyncSessionLocal
from master.models import BenchmarkRun, Job
from benchmark.runner import run_scenario_benchmark

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])

@router.post("/run")
async def trigger_benchmark(req: BenchmarkRunRequest, background_tasks: BackgroundTasks):
    """Menjalankan skenario benchmark otomatis (A, B, C, D, E, F) dengan repetisi minimal 3x."""
    def _run_bg():
        run_scenario_benchmark(
            scenario=req.scenario,
            job_type=req.job_type.value,
            repetitions=req.repetitions,
            n_workers=req.n_workers,
            cold_cache=req.cold_cache
        )
    background_tasks.add_task(_run_bg)
    return {
        "status": "started",
        "scenario": req.scenario,
        "message": f"Benchmark Skenario {req.scenario} dimulai di latar belakang dengan {req.repetitions} repetisi."
    }

@router.get("")
async def list_benchmarks(db: AsyncSession = Depends(get_db)):
    """Mengambil riwayat seluruh run benchmark."""
    q = await db.execute(select(BenchmarkRun).order_by(BenchmarkRun.id.desc()))
    runs = q.scalars().all()
    return [
        {
            "id": r.id,
            "scenario": r.scenario,
            "job_id": r.job_id,
            "n_workers": r.n_workers,
            "repetition": r.repetition,
            "cold_cache": r.cold_cache,
            "exec_time_s": r.exec_time_s,
            "compute_time_s": r.compute_time_s,
            "transfer_time_s": r.transfer_time_s,
            "speedup": r.speedup,
            "efficiency": r.efficiency,
            "throughput": r.throughput,
            "recovery_time_s": r.recovery_time_s
        } for r in runs
    ]

@router.get("/{run_id}/export")
async def export_benchmark(run_id: int, format: str = "json", db: AsyncSession = Depends(get_db)):
    """Mengekspor data hasil benchmark ke CSV atau JSON untuk BAB IV laporan."""
    q = await db.execute(select(BenchmarkRun).where(BenchmarkRun.id == run_id))
    run = q.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Data benchmark tidak ditemukan")
        
    data = {
        "id": run.id,
        "scenario": run.scenario,
        "n_workers": run.n_workers,
        "repetition": run.repetition,
        "cold_cache": run.cold_cache,
        "exec_time_s": run.exec_time_s,
        "compute_time_s": run.compute_time_s,
        "transfer_time_s": run.transfer_time_s,
        "speedup": run.speedup,
        "efficiency": run.efficiency,
        "throughput": run.throughput,
        "recovery_time_s": run.recovery_time_s
    }
    
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data.keys())
        writer.writeheader()
        writer.writerow(data)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=benchmark_skenario_{run.scenario}_{run.id}.csv"}
        )
        
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=benchmark_skenario_{run.scenario}_{run.id}.json"}
    )
