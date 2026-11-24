"""
Eksekutor Multiprocessing Lokal di Sisi Worker (ProcessPoolExecutor, spawn).
Membagi chunk besar menjadi sub-chunk per rentang baris agar setiap proses membaca bagiannya
sendiri langsung dari file lokal tanpa serialisasi (pickling) DataFrame besar antarproses.
"""

import concurrent.futures
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
import pyarrow.parquet as pq

from common.cleaning import NUMERIC_COLUMNS
from common.algorithms import (
    j1_map_chunk, j1_reduce,
    j2_map_chunk, j2_reduce,
    j3_map_chunk, j3_reduce,
    prepare_kmeans_features,
    j4_map_chunk
)

# ---------------------------------------------------------------------------
# Fungsi Pekerja Tingkat Modul (Module-Level Functions agar Picklable oleh Spawn)
# ---------------------------------------------------------------------------

def _subchunk_j1_worker(args: Tuple[str, int, int]) -> Dict[str, Any]:
    file_path, row_start, row_count = args
    # Baca rentang baris spesifik menggunakan PyArrow
    table = pq.read_table(file_path)
    sub_table = table.slice(row_start, row_count)
    df = sub_table.to_pandas()
    return j1_map_chunk(df, NUMERIC_COLUMNS)

def _subchunk_j2_worker(args: Tuple[str, int, int]) -> Dict[str, Any]:
    file_path, row_start, row_count = args
    table = pq.read_table(file_path)
    sub_table = table.slice(row_start, row_count)
    df = sub_table.to_pandas()
    return j2_map_chunk(df)

def _subchunk_j3_worker(args: Tuple[str, int, int, List[str]]) -> Dict[str, Any]:
    file_path, row_start, row_count, target_cols = args
    table = pq.read_table(file_path)
    sub_table = table.slice(row_start, row_count)
    df = sub_table.to_pandas()
    return j3_map_chunk(df, target_cols)

def _subchunk_j4_worker(args: Tuple[str, int, int, Dict[str, Any], np.ndarray]) -> Dict[str, Any]:
    file_path, row_start, row_count, norm_params, centroids = args
    table = pq.read_table(file_path)
    sub_table = table.slice(row_start, row_count)
    df = sub_table.to_pandas()
    features = prepare_kmeans_features(df, norm_params)
    return j4_map_chunk(features, centroids)

class WorkerExecutor:
    def __init__(self, num_processes: int = 0):
        # 0 = gunakan seluruh core fisik
        if num_processes <= 0:
            num_processes = mp.cpu_count()
        self.num_processes = num_processes
        
        ctx = mp.get_context("spawn")
        self.pool = concurrent.futures.ProcessPoolExecutor(
            max_workers=self.num_processes,
            mp_context=ctx
        )

    def close(self):
        self.pool.shutdown(wait=True)

    def _split_row_ranges(self, total_rows: int) -> List[Tuple[int, int]]:
        """Membagi baris menjadi sub-chunk seimbang sesuai jumlah proses pool."""
        if total_rows <= 0:
            return []
        p = min(self.num_processes, max(1, total_rows // 10000))
        chunk_len = int(np.ceil(total_rows / p))
        ranges = []
        for i in range(p):
            start = i * chunk_len
            count = min(chunk_len, total_rows - start)
            if count > 0:
                ranges.append((start, count))
        return ranges

    def execute_j1(self, file_path: Path) -> Dict[str, Any]:
        meta = pq.read_metadata(str(file_path))
        total_rows = meta.num_rows
        ranges = self._split_row_ranges(total_rows)
        
        if len(ranges) <= 1:
            df = pd.read_parquet(file_path)
            return j1_map_chunk(df, NUMERIC_COLUMNS)
            
        args = [(str(file_path), r[0], r[1]) for r in ranges]
        sub_results = list(self.pool.map(_subchunk_j1_worker, args))
        return j1_reduce(sub_results)

    def execute_j2(self, file_path: Path) -> Dict[str, Any]:
        meta = pq.read_metadata(str(file_path))
        total_rows = meta.num_rows
        ranges = self._split_row_ranges(total_rows)
        
        if len(ranges) <= 1:
            df = pd.read_parquet(file_path)
            return j2_map_chunk(df)
            
        args = [(str(file_path), r[0], r[1]) for r in ranges]
        sub_results = list(self.pool.map(_subchunk_j2_worker, args))
        return j2_reduce(sub_results)

    def execute_j3(self, file_path: Path, target_cols: List[str]) -> Dict[str, Any]:
        meta = pq.read_metadata(str(file_path))
        total_rows = meta.num_rows
        ranges = self._split_row_ranges(total_rows)
        
        if len(ranges) <= 1:
            df = pd.read_parquet(file_path)
            return j3_map_chunk(df, target_cols)
            
        args = [(str(file_path), r[0], r[1], target_cols) for r in ranges]
        sub_results = list(self.pool.map(_subchunk_j3_worker, args))
        return j3_reduce(sub_results, target_cols)

    def execute_j4(
        self,
        file_path: Path,
        norm_params: Dict[str, Any],
        centroids: np.ndarray,
        cached_features: np.ndarray = None
    ) -> Tuple[Dict[str, Any], np.ndarray]:
        """Eksekusi K-Means Map dengan dukungan in-memory cached features jika tersedia."""
        if cached_features is not None:
            # Fitur sudah ada di RAM (iterasi ke-2 dst)
            res = j4_map_chunk(cached_features, centroids)
            return res, cached_features
            
        # Iterasi pertama: ekstrak fitur dari berkas
        df = pd.read_parquet(file_path)
        features = prepare_kmeans_features(df, norm_params)
        res = j4_map_chunk(features, centroids)
        return res, features
