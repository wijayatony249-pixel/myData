"""
Aplikasi Utama Master FastAPI myData.
Mengelola Scheduler, Fault Monitor, REST API, dan Real-time Server-Sent Events (SSE).
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from common.config import MASTER_HOST, MASTER_PORT
from master.database import init_db
from master.fault_monitor import run_fault_monitor_loop
from master.sse_manager import sse_manager
from master.routes import (
    workers,
    tasks,
    chunks,
    datasets,
    jobs,
    benchmarks,
    faults
)

_monitor_task: asyncio.Task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inisialisasi DB dan jalankan Fault Monitor di latar belakang
    print("[*] Menginisialisasi basis data Master...")
    await init_db()
    
    print("[*] Menjalankan Fault Monitor background service...")
    global _monitor_task
    _monitor_task = asyncio.create_task(run_fault_monitor_loop(poll_interval=1.0))
    
    yield
    
    # Shutdown: Hentikan background tasks
    if _monitor_task:
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    print("[*] Master service dihentikan dengan aman.")

app = FastAPI(
    title="myData Master API",
    description="Platform Data Mining Terdistribusi - Node Master FastAPI",
    version="1.0.0",
    lifespan=lifespan
)

# Izinkan CORS untuk dashboard Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan Router
app.include_router(workers.router)
app.include_router(tasks.router)
app.include_router(chunks.router)
app.include_router(datasets.router)
app.include_router(jobs.router)
app.include_router(benchmarks.router)
app.include_router(faults.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "role": "master", "service": "myData"}

@app.get("/cluster/stream")
async def cluster_stream(request: Request):
    """Streaming pembaruan status klaster, utilisasi worker, dan progres job melalui SSE."""
    queue = await sse_manager.subscribe()
    
    async def event_generator():
        try:
            # Kirim pesan sambutan awal
            yield "event: connected\ndata: {\"message\": \"Terhubung ke stream SSE myData Master\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield payload
                except asyncio.TimeoutError:
                    # Kirim heartbeat ping untuk menjaga koneksi tetap hidup
                    yield "event: ping\ndata: {}\n\n"
        finally:
            sse_manager.unsubscribe(queue)
            
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("master.main:app", host=MASTER_HOST, port=MASTER_PORT, reload=False)
