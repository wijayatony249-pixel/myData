"""
Agen Pekerja (Worker Agent) myData.
Menjalankan loop pengambilan task (pull-based), thread heartbeat terisolasi,
manajemen cache lokal, komputasi multiprocessing multicore, dan endpoint admin fault injection.
"""

import argparse
import asyncio
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional
import httpx
import numpy as np
import psutil
import uvicorn
from fastapi import FastAPI

# Tambahkan root proyek ke sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from common.config import (
    CLUSTER_TOKEN, HEARTBEAT_INTERVAL_SEC, CACHE_DIR,
    WORKER_PORT, MASTER_URL
)
from common.utils import get_node_hardware_info, get_system_metrics, Timer
try:
    from worker.cache_manager import WorkerCacheManager
    from worker.executor import WorkerExecutor
except (ModuleNotFoundError, ImportError):
    from cache_manager import WorkerCacheManager
    from executor import WorkerExecutor

# ---------------------------------------------------------------------------
# State Global Worker
# ---------------------------------------------------------------------------
app = FastAPI(title="myData Worker Agent")

worker_id = "worker-1"
master_base_url = MASTER_URL
worker_port = WORKER_PORT
throttle_delay_sec = 0.0

active_task_id: Optional[int] = None
is_muted = False
is_hanging = False
is_running = True

cache_mgr: WorkerCacheManager = None
executor: WorkerExecutor = None

# ---------------------------------------------------------------------------
# Endpoint Admin (Fault Injection)
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy" if not is_hanging else "hanging",
        "worker_id": worker_id,
        "active_task_id": active_task_id,
        "is_muted": is_muted
    }

@app.post("/admin/kill")
def admin_kill():
    """Mematikan proses worker seketika menggunakan psutil lintas OS."""
    print(f"[!] Perintah /admin/kill diterima. Menghentikan proses worker {worker_id}...")
    def _do_kill():
        time.sleep(0.2)
        p = psutil.Process(os.getpid())
        p.kill()
    threading.Thread(target=_do_kill, daemon=True).start()
    return {"message": f"Worker {worker_id} dimatikan via psutil."}

@app.post("/admin/hang")
def admin_hang():
    """Mensimulasikan proses macet/deadlock tak berujung."""
    global is_hanging
    is_hanging = True
    print(f"[!] Perintah /admin/hang diterima. Worker {worker_id} kini dalam status macet.")
    return {"message": f"Worker {worker_id} diset ke status HANG (simulasi deadlock)."}

@app.post("/admin/mute")
def admin_mute():
    """Mensimulasikan kabel putus / isolasi jaringan (menghentikan heartbeat dan request keluar)."""
    global is_muted
    is_muted = not is_muted
    status_str = "MUTED (Terisolasi dari jaringan)" if is_muted else "UNMUTED (Pulih kembali)"
    print(f"[!] Perintah /admin/mute diterima. Worker {worker_id} kini: {status_str}")
    return {"message": f"Worker {worker_id} status jaringan: {status_str}"}

# ---------------------------------------------------------------------------
# Background Threads: Heartbeat & Task Pulling
# ---------------------------------------------------------------------------

def heartbeat_loop():
    """Thread terisolasi untuk mengirim heartbeat berkala tanpa terblokir beban komputasi."""
    print(f"[*] Thread Heartbeat aktif (interval: {HEARTBEAT_INTERVAL_SEC}s)...")
    while is_running:
        if is_hanging:
            # Simulasi macet: thread tidak mengirim apa pun
            time.sleep(1.0)
            continue
            
        if not is_muted:
            metrics = get_system_metrics()
            payload = {
                "worker_id": worker_id,
                "cpu_pct": metrics["cpu_pct"],
                "mem_pct": metrics["mem_pct"],
                "active_task_id": active_task_id
            }
            try:
                with httpx.Client(timeout=3.0) as client:
                    client.post(
                        f"{master_base_url}/workers/{worker_id}/heartbeat",
                        json=payload,
                        headers={"X-Cluster-Token": CLUSTER_TOKEN}
                    )
            except Exception:
                pass
                
        time.sleep(HEARTBEAT_INTERVAL_SEC)

def task_pull_loop():
    """Thread penarik task secara terus-menerus (Pull-based Worker)."""
    global active_task_id
    print("[*] Loop Task Pulling aktif menunggu penugasan dari Master...")
    
    while is_running:
        if is_hanging or is_muted:
            time.sleep(1.0)
            continue
            
        task_data = None
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{master_base_url}/tasks/next",
                    json={"worker_id": worker_id},
                    headers={"X-Cluster-Token": CLUSTER_TOKEN}
                )
                if resp.status_code == 200:
                    task_data = resp.json()
        except Exception:
            time.sleep(1.0)
            continue
            
        if not task_data or not task_data.get("has_task"):
            # Tidak ada task antre, tidur sejenak
            time.sleep(0.5)
            continue
            
        t_id = task_data["task_id"]
        j_id = task_data["job_id"]
        j_type = task_data["job_type"]
        c_id = task_data["chunk_id"]
        attempt = task_data.get("attempt", 1)
        iteration = task_data.get("iteration", 0)
        expected_checksum = task_data.get("checksum")
        params = task_data.get("params") or {}
        
        active_task_id = t_id
        print(f"\n[+] Menerima Task #{t_id} (Job #{j_id} - {j_type}, Chunk #{c_id}, Iterasi #{iteration}, Attempt #{attempt})")
        
        try:
            # 1. Unduh atau ambil chunk dari cache lokal
            chunk_dl_url = f"{master_base_url}{task_data['chunk_download_url']}"
            chunk_file, transfer_ms, cache_hit = cache_mgr.get_or_download_chunk(
                chunk_id=c_id,
                download_url=chunk_dl_url,
                expected_checksum=expected_checksum
            )
            
            # Simulasi throttle buatan jika disetel (untuk skenario D Worker heterogen)
            if throttle_delay_sec > 0:
                time.sleep(throttle_delay_sec)
                
            # 2. Eksekusi Komputasi menggunakan Multiprocessing
            with Timer() as t_comp:
                partial_res = {}
                if j_type == "J1_STATS":
                    partial_res = executor.execute_j1(chunk_file)
                elif j_type == "J2_GROUPBY":
                    partial_res = executor.execute_j2(chunk_file)
                elif j_type == "J3_CORR":
                    target_cols = [
                        "passenger_count", "trip_distance", "fare_amount",
                        "tip_amount", "total_amount", "duration_minutes"
                    ]
                    partial_res = executor.execute_j3(chunk_file, target_cols)
                elif j_type == "J4_KMEANS":
                    norm_params = params.get("norm_params", {})
                    centroids = np.array(params["centroids"], dtype=np.float64)
                    
                    # Cek cache memori untuk iterasi ke-2 dst
                    cached_feat = cache_mgr.get_memory_features(c_id)
                    partial_res, new_feat = executor.execute_j4(
                        chunk_file, norm_params, centroids, cached_features=cached_feat
                    )
                    if cached_feat is None:
                        cache_mgr.set_memory_features(c_id, new_feat)
                        
            compute_ms = t_comp.elapsed * 1000.0
            print(f"    -> Selesai: Compute = {compute_ms:.1f}ms | Transfer = {transfer_ms:.1f}ms | Cache Hit = {cache_hit}")
            
            # 3. Kirimkan Hasil Parsial ke Master
            submit_payload = {
                "task_id": t_id,
                "job_id": j_id,
                "attempt": attempt,
                "worker_id": worker_id,
                "iteration": iteration,
                "compute_ms": compute_ms,
                "transfer_ms": transfer_ms,
                "cache_hit": cache_hit,
                "partial_result": partial_res
            }
            
            with httpx.Client(timeout=15.0) as client:
                client.post(
                    f"{master_base_url}/tasks/{t_id}/result",
                    json=submit_payload,
                    headers={"X-Cluster-Token": CLUSTER_TOKEN}
                )
                
        except Exception as e:
            print(f"[!] Gagal mengeksekusi task #{t_id}: {e}")
        finally:
            active_task_id = None

# ---------------------------------------------------------------------------
# Registrasi & Startup Worker
# ---------------------------------------------------------------------------

def register_to_master():
    """Mendaftarkan spesifikasi perangkat keras ke Master."""
    hw_info = get_node_hardware_info(worker_id)
    print(f"[*] Mendaftarkan Worker {worker_id} ke Master ({master_base_url})...")
    print(f"    OS: {hw_info['os']} | CPU: {hw_info['cpu_model']} | Core: {hw_info['cores']} | RAM: {hw_info['ram_mb']}MB")
    
    max_retries = 10
    for r in range(max_retries):
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{master_base_url}/workers/register",
                    json=hw_info,
                    headers={"X-Cluster-Token": CLUSTER_TOKEN}
                )
                if resp.status_code == 200:
                    print(f"[+] Worker {worker_id} sukses terdaftar di Master!")
                    return True
        except Exception:
            print(f"    Menunggu Master di {master_base_url}... (Percobaan {r+1}/{max_retries})")
            time.sleep(2.0)
            
    print("[!] Tidak dapat terhubung ke Master. Melanjutkan mode lokal mandiri.")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker Node myData")
    parser.add_argument("--master", type=str, default=MASTER_URL, help="URL Master (contoh: http://192.168.1.10:8000)")
    parser.add_argument("--id", type=str, default="worker-1", help="ID unik worker (contoh: worker-1)")
    parser.add_argument("--port", type=int, default=WORKER_PORT, help="Port HTTP admin worker")
    parser.add_argument("--processes", type=int, default=0, help="Jumlah proses multiprocessing (0 = auto)")
    parser.add_argument("--throttle", type=float, default=0.0, help="Faktor delay buatan dalam detik (untuk uji heterogen)")
    
    args = parser.parse_args()
    
    worker_id = args.id
    master_base_url = args.master
    worker_port = args.port
    throttle_delay_sec = args.throttle
    
    # Inisialisasi Cache & Executor
    worker_cache_path = CACHE_DIR / worker_id
    cache_mgr = WorkerCacheManager(worker_cache_path)
    executor = WorkerExecutor(num_processes=args.processes)
    
    # Registrasi ke Master
    register_to_master()
    
    # Jalankan background threads
    t_hb = threading.Thread(target=heartbeat_loop, daemon=True)
    t_hb.start()
    
    t_pull = threading.Thread(target=task_pull_loop, daemon=True)
    t_pull.start()
    
    # Jalankan HTTP server FastAPI untuk admin endpoint
    print(f"[*] Worker Admin server menyala pada port {worker_port}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=worker_port, log_level="warning")
    finally:
        is_running = False
        executor.close()
