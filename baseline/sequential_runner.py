"""
Baseline Sequential (Skenario A): 1 Komputer, 1 Proses, Tanpa Jaringan.
Menggunakan fungsi Map-Reduce yang sama persis dengan Worker untuk menjamin nilai Ts adil.
"""

import argparse
import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, List
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
    j4_map_chunk, j4_reduce_iteration, KMEANS_FEATURES
)

def load_all_chunks() -> List[pd.DataFrame]:
    """Membaca semua file chunk Parquet secara lokal."""
    chunk_files = sorted(list(CHUNKS_DIR.glob("chunk_*.parquet")))
    if not chunk_files:
        raise FileNotFoundError(f"Tidak ada file chunk di {CHUNKS_DIR}. Jalankan scripts/prepare_dataset.py terlebih dahulu.")
    
    dfs = []
    for cf in chunk_files:
        dfs.append(pd.read_parquet(cf))
    return dfs

def run_j1_sequential(chunks: List[pd.DataFrame]) -> Dict[str, Any]:
    """Eksekusi Sekuensial J1: Statistik Deskriptif."""
    partials = []
    for df in chunks:
        partials.append(j1_map_chunk(df, NUMERIC_COLUMNS))
    return j1_reduce(partials)

def run_j2_sequential(chunks: List[pd.DataFrame]) -> Dict[str, Any]:
    """Eksekusi Sekuensial J2: Agregasi Group-By."""
    partials = []
    for df in chunks:
        partials.append(j2_map_chunk(df))
    return j2_reduce(partials)

def run_j3_sequential(chunks: List[pd.DataFrame]) -> Dict[str, Any]:
    """Eksekusi Sekuensial J3: Korelasi Pearson."""
    target_cols = ["passenger_count", "trip_distance", "fare_amount", "tip_amount", "total_amount", "duration_minutes"]
    partials = []
    for df in chunks:
        partials.append(j3_map_chunk(df, target_cols))
    return j3_reduce(partials, target_cols)

def run_j4_sequential(chunks: List[pd.DataFrame], k: int = 8, max_iter: int = 15, seed: int = 42) -> Dict[str, Any]:
    """Eksekusi Sekuensial J4: K-Means Clustering."""
    # 1. Hitung parameter z-score dari J1
    j1_stats = run_j1_sequential(chunks)
    
    # 2. Ambil sampel 10.000 baris untuk inisialisasi centroid k-means++
    sample_df = chunks[0] if len(chunks[0]) >= 10000 else pd.concat(chunks, ignore_index=True)
    sample_subset = sample_df.sample(n=min(10000, len(sample_df)), random_state=seed)
    sample_feat = prepare_kmeans_features(sample_subset, j1_stats)
    
    centroids = init_kmeans_plus_plus(sample_feat, k=k, seed=seed)
    
    # Pre-extract fitur untuk setiap chunk agar tidak redundan per iterasi
    chunk_features = [prepare_kmeans_features(df, j1_stats) for df in chunks]
    
    total_iterations = 0
    final_shift = 0.0
    cluster_counts = []
    
    for it in range(max_iter):
        total_iterations += 1
        partials = []
        for feat in chunk_features:
            partials.append(j4_map_chunk(feat, centroids))
            
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

def run_benchmark_sequential(job_type: str = "J4", repetitions: int = 3) -> Dict[str, Any]:
    """Menjalankan pengujian berulang dengan membuang 1 run pemanasan (warm-up)."""
    print(f"[*] Memuat chunk data untuk Baseline Sequential ({job_type})...")
    chunks = load_all_chunks()
    total_rows = sum(len(c) for c in chunks)
    print(f"[+] Total data: {total_rows:,} baris dalam {len(chunks)} chunk.")
    
    # Warm-up run (tidak dihitung dalam rata-rata)
    print("[*] Menjalankan pemanasan (warm-up run)...")
    if job_type == "J1":
        _ = run_j1_sequential(chunks)
    elif job_type == "J2":
        _ = run_j2_sequential(chunks)
    elif job_type == "J3":
        _ = run_j3_sequential(chunks)
    else:
        _ = run_j4_sequential(chunks)
        
    durations = []
    result = None
    print(f"[*] Menjalankan {repetitions} kali repetisi benchmark sekuensial murni...")
    for r in range(repetitions):
        t0 = time.perf_counter()
        if job_type == "J1":
            result = run_j1_sequential(chunks)
        elif job_type == "J2":
            result = run_j2_sequential(chunks)
        elif job_type == "J3":
            result = run_j3_sequential(chunks)
        else:
            result = run_j4_sequential(chunks)
        elapsed = time.perf_counter() - t0
        durations.append(elapsed)
        print(f"    - Repetisi #{r+1}: {elapsed:.4f} detik")
        
    mean_time = float(np.mean(durations))
    std_time = float(np.std(durations))
    throughput = total_rows / mean_time if mean_time > 0 else 0
    
    summary = {
        "mode": "SEQUENTIAL",
        "job_type": job_type,
        "total_rows": total_rows,
        "chunk_count": len(chunks),
        "repetitions": repetitions,
        "durations": durations,
        "ts_mean_seconds": mean_time,
        "ts_std_seconds": std_time,
        "throughput_rows_per_sec": throughput,
        "sample_result": result
    }
    
    print(f"\n[+] Hasil Baseline Sequential ({job_type}):")
    print(f"    Ts = {mean_time:.4f} ± {std_time:.4f} detik | Throughput = {throughput:,.1f} baris/detik")
    
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baseline Sequential myData")
    parser.add_argument("--job", type=str, default="J4", choices=["J1", "J2", "J3", "J4"], help="Jenis job mining")
    parser.add_argument("--reps", type=int, default=3, help="Jumlah repetisi benchmark")
    
    args = parser.parse_args()
    run_benchmark_sequential(job_type=args.job, repetitions=args.reps)
