"""
Manajer Cache Berkas Parquet Lokal di Sisi Worker.
Mendukung verifikasi checksum SHA-256, pengukuran durasi transfer jaringan,
dan in-memory caching untuk iterasi cepat K-Means.
"""

import time
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import httpx
import pandas as pd
import numpy as np

from common.utils import calculate_checksum

class WorkerCacheManager:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # In-memory DataFrame cache untuk mempercepat iterasi berulang K-Means (J4)
        self._memory_cache: Dict[int, pd.DataFrame] = {}
        self._feature_cache: Dict[int, np.ndarray] = {}

    def get_or_download_chunk(
        self,
        chunk_id: int,
        download_url: str,
        expected_checksum: Optional[str] = None
    ) -> Tuple[Path, float, bool]:
        """
        Mengambil berkas chunk dari cache lokal atau mengunduhnya dari Master jika belum ada.
        Mengembalikan: (path_berkas, transfer_ms, cache_hit)
        """
        cached_file = self.cache_dir / f"chunk_{chunk_id:04d}.parquet"
        
        # 1. Cek apakah berkas ada di cache dan valid checksum-nya
        if cached_file.exists():
            if expected_checksum:
                actual_checksum = calculate_checksum(cached_file)
                if actual_checksum == expected_checksum:
                    return cached_file, 0.0, True
            else:
                return cached_file, 0.0, True

        # 2. Unduh dari Master melalui HTTP Binary Stream
        t0 = time.perf_counter()
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(download_url)
            resp.raise_for_status()
            content = resp.content

        transfer_ms = (time.perf_counter() - t0) * 1000.0

        # Tulis ke disk lokal
        with open(cached_file, "wb") as f:
            f.write(content)

        # Verifikasi integritas checksum
        if expected_checksum:
            actual_checksum = calculate_checksum(cached_file)
            if actual_checksum != expected_checksum:
                cached_file.unlink(missing_ok=True)
                raise ValueError(f"Checksum mismatch pada chunk #{chunk_id}: {actual_checksum} != {expected_checksum}")

        return cached_file, transfer_ms, False

    def get_memory_features(self, chunk_id: int) -> Optional[np.ndarray]:
        """Mengambil fitur array NumPy yang sudah tersimpan di RAM untuk J4."""
        return self._feature_cache.get(chunk_id)

    def set_memory_features(self, chunk_id: int, features: np.ndarray):
        """Menyimpan fitur array NumPy di RAM untuk menghindari parsing ulang pada iterasi berikutnya."""
        self._feature_cache[chunk_id] = features

    def clear_memory_cache(self):
        """Membersihkan cache memori saat job berganti."""
        self._memory_cache.clear()
        self._feature_cache.clear()
