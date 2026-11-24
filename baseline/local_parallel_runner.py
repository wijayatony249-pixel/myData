"""
Baseline Local Parallel (Skenario B): Multiprocessing 1 Komputer (1, 2, 4, ... proses).
Menggunakan ProcessPoolExecutor dengan metode 'spawn' untuk kompatibilitas lintas Windows & Linux.
"""

import argparse
import concurrent.futures
import multiprocessing as mp
import time
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

# Tambahkan root proyek ke sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from common.config import CHUNKS_DIR
from common.cleaning import NUMERIC_COLUMNS
from common.algorithms import (
    j1_map_chunk, j1_reduce,
    j2_map_chunk, j2_reduce,
    j3_map_chunk, j3_reduce,
    prepare_kmeans_features, init_kmeans_plus_plus,
    j4_map_chunk, j4_reduce_iteration
)

# ---------------------------------------------------------------------------
# Fungsi Pekerja Tingkat Modul (Module-Level Functions agar Picklable oleh Spawn)
# ---------------------------------------------------------------------------

def _worker_j1_map(chunk_path: str) -> Dict[str, Any]:
    df = pd.read_parquet(chunk_path)
    return j1_map_chunk(df, NUMERIC_COLUMNS)

def _worker_j2_map(chunk_path: str) -> Dict[str, Any]:
    df = pd.read_parquet(chunk_path)
    return j2_map_chunk(df)

def _worker_j3_map(args: Tuple[str, List[str]]) -> Dict[str, Any]:
    chunk_path, target_cols = args
    df = pd.read_parquet(chunk_path)
    return j3_map_chunk(df, target_cols)

def _worker_j4_map(args: Tuple[str, Dict[str, Dict[str, float]], np.ndarray]) -> Dict[str, Any]:
    chunk_path, norm_params, centroids = args
    df = pd.read_parquet(chunk_path)
    feat = prepare_kmeans_features(df, norm_params)
    return j4_map_chunk(feat, centroids)

# ---------------------------------------------------------------------------
# Eksekutor Paralel Lokal
# ---------------------------------------------------------------------------

def run_j1_parallel(chunk_paths: List[str], pool: concurrent.futures.ProcessPoolExecutor) -> Dict[str, Any]:
    results = list(pool.map(_worker_j1_map, chunk_paths))
    return j1_reduce(results)

def run_j2_parallel(chunk_paths: List[str], pool: concurrent.futures.ProcessPoolExecutor) -> Dict[str, Any]:
    results = list(pool.map(_worker_j2_map, chunk_paths))
    return j2_reduce(results)

def run_j3_parallel(chunk_paths: List[str], pool: concurrent.futures.ProcessPoolExecutor) -> Dict[str, Any]:
    target_cols = ["passenger_count", "trip_distance", "fare_amount", "tip_amount", "total_amount", "duration_minutes"]
    args = [(p, target_cols) for p in chunk_paths]
    results = list(pool.map(_worker_j3_map, args))
    return j3_reduce(results, target_cols)

def run_j4_parallel(
    chunk_paths: List[str],
    pool: concurrent.futures.ProcessPoolExecutor,
    k: int = 8,
    max_iter: int = 15,
    seed: int = 42
) -> Dict[str, Any]:
    # 1. Parameter normalisasi z-score dari J1
    j1_stats = run_j1_parallel(chunk_paths, pool)
    
    # 2. Inisialisasi K-Means++ pada sampel lokal
    sample_df = pd.read_parquet(chunk_paths[0])
    sample_subset = sample_df.sample(n=min(10000, len(sample_df)), random_state=seed)
    sample_feat = prepare_kmeans_features(sample_subset, j1_stats)
    centroids = init_kmeans_plus_plus(sample_feat, k=k, seed=seed)
    
    total_iterations = 0
    final_shift = 0.0
    cluster_counts = []
    
    for it in range(max_iter):
        total_iterations += 1
        args = [(p, j1_stats, centroids) for p in chunk_paths]
        partials = list(pool.map(_worker_j4_map, args))
        
        new_centroids, shift, counts = j4_reduce_iteration(partials, centroids)
        final_shift = shift
        cluster_counts = counts
        centroids = new_centroids
        
        if shift < 1e-4:
            break
            
    return {
        "k": k,
        "iterations": total_iterations,
        "final_shift": final_shift,
        "cluster_counts": cluster_counts,
        "centroids": centroids.tolist()
    }

def run_benchmark_local_parallel(
    num_processes: int = 4,
    job_type: str = "J4",
    repetitions: int = 3,
    ts_baseline: float = None
) -> Dict[str, Any]:
    chunk_files = sorted([str(p) for p in CHUNKS_DIR.glob("chunk_*.parquet")])
    if not chunk_files:
        raise FileNotFoundError(f"Tidak ada file chunk di {CHUNKS_DIR}.")

    ctx = mp.get_context("spawn")
    print(f"[*] Menyiapkan ProcessPool ({num_processes} proses, start_method='spawn')...")
    
    durations = []
    result = None
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_processes, mp_context=ctx) as pool:
        # Pemanasan
        print(f"[*] Pemanasan lokal paralel dengan {num_processes} proses...")
        if job_type == "J1":
            _ = run_j1_parallel(chunk_files, pool)
        elif job_type == "J2":
            _ = run_j2_parallel(chunk_files, pool)
        elif job_type == "J3":
            _ = run_j3_parallel(chunk_files, pool)
        else:
            _ = run_j4_parallel(chunk_files, pool)
            
        print(f"[*] Menjalankan {repetitions} repetisi benchmark lokal paralel...")
        for r in range(repetitions):
            t0 = time.perf_counter()
            if job_type == "J1":
                result = run_j1_parallel(chunk_files, pool)
            elif job_type == "J2":
                result = run_j2_parallel(chunk_files, pool)
            elif job_type == "J3":
                result = run_j3_parallel(chunk_files, pool)
            else:
                result = run_j4_parallel(chunk_files, pool)
            elapsed = time.perf_counter() - t0
            durations.append(elapsed)
            print(f"    - Repetisi #{r+1}: {elapsed:.4f} detik")
            
    mean_tp = float(np.mean(durations))
    std_tp = float(np.std(durations))
    
    speedup = (ts_baseline / mean_tp) if ts_baseline and mean_tp > 0 else 0.0
    efficiency = (speedup / num_processes) if num_processes > 0 else 0.0
    
    summary = {
        "mode": "LOCAL_PARALLEL",
        "num_processes": num_processes,
        "job_type": job_type,
        "tp_mean_seconds": mean_tp,
        "tp_std_seconds": std_tp,
        "speedup": speedup,
        "efficiency": efficiency,
        "durations": durations,
        "sample_result": result
    }
    
    print(f"\n[+] Hasil Local Parallel ({num_processes} Proses):")
    print(f"    Tp = {mean_tp:.4f} ± {std_tp:.4f} dtk | Speedup = {speedup:.2f}x | Efisiensi = {efficiency*100:.1f}%")
    
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baseline Local Parallel myData")
    parser.add_argument("-p", "--processes", type=int, default=4, help="Jumlah proses pool")
    parser.add_argument("--job", type=str, default="J4", choices=["J1", "J2", "J3", "J4"], help="Jenis job mining")
    parser.add_argument("--reps", type=int, default=3, help="Jumlah repetisi")
    parser.add_argument("--ts", type=float, default=None, help="Baseline Ts jika sudah diketahui")
    
    args = parser.parse_args()
    run_benchmark_local_parallel(num_processes=args.processes, job_type=args.job, repetitions=args.reps, ts_baseline=args.ts)
