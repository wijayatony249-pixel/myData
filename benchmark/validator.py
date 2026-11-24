"""
Validator Hasil Komputasi (Kebutuhan F15 PRD).
Membandingkan output terdistribusi dengan baseline sequential dalam batas toleransi numerik ketat:
- rtol = 1e-9 untuk J1, J2, J3
- toleransi 1e-6 untuk pergeseran centroid J4 (akibat perbedaan urutan penjumlahan floating point).
"""

from typing import Dict, Any, Tuple
import numpy as np

def validate_j1(dist_result: Dict[str, Any], seq_result: Dict[str, Any], rtol: float = 1e-9) -> Tuple[bool, float, str]:
    """Validasi J1: Statistik Deskriptif."""
    max_diff = 0.0
    for col, seq_stats in seq_result.items():
        if col not in dist_result:
            return False, 1.0, f"Kolom '{col}' tidak ditemukan di hasil terdistribusi"
        dist_stats = dist_result[col]
        for metric in ["count", "sum", "min", "max", "mean", "std"]:
            val_seq = float(seq_stats[metric])
            val_dist = float(dist_stats[metric])
            denom = max(abs(val_seq), 1.0)
            diff = abs(val_dist - val_seq) / denom
            max_diff = max(max_diff, diff)
            if diff > rtol:
                return False, max_diff, f"Nilai '{metric}' kolom '{col}' tidak cocok: dist={val_dist}, seq={val_seq}, diff={diff}"
    return True, max_diff, f"Validasi J1 Sukses (Max rel diff: {max_diff:.2e} <= {rtol:.2e})"

def validate_j2(dist_result: Dict[str, Any], seq_result: Dict[str, Any], rtol: float = 1e-9) -> Tuple[bool, float, str]:
    """Validasi J2: Agregasi Group-By."""
    max_diff = 0.0
    for group_name in ["by_hour", "by_day", "by_pulocation", "by_dolocation"]:
        seq_grp = seq_result.get(group_name, {})
        dist_grp = dist_result.get(group_name, {})
        for key, seq_val in seq_grp.items():
            k_str = str(key)
            if k_str not in dist_grp and int(k_str) not in dist_grp:
                return False, 1.0, f"Key {key} tidak ada di grup {group_name}"
            dist_val = dist_grp.get(k_str) or dist_grp.get(int(k_str))
            for m in ["count", "fare_sum", "tip_sum", "avg_fare", "avg_tip"]:
                v_s = float(seq_val[m])
                v_d = float(dist_val[m])
                denom = max(abs(v_s), 1.0)
                diff = abs(v_d - v_s) / denom
                max_diff = max(max_diff, diff)
                if diff > rtol:
                    return False, max_diff, f"Group {group_name} [{key}] '{m}' selisih: {diff} > {rtol}"
    return True, max_diff, f"Validasi J2 Sukses (Max rel diff: {max_diff:.2e} <= {rtol:.2e})"

def validate_j3(dist_matrix: Dict[str, Dict[str, float]], seq_matrix: Dict[str, Dict[str, float]], rtol: float = 1e-9) -> Tuple[bool, float, str]:
    """Validasi J3: Matriks Korelasi Pearson."""
    max_diff = 0.0
    for c1, row in seq_matrix.items():
        for c2, val_s in row.items():
            val_d = dist_matrix.get(c1, {}).get(c2, 0.0)
            diff = abs(val_d - val_s)
            max_diff = max(max_diff, diff)
            if diff > rtol:
                return False, max_diff, f"Korelasi ({c1}, {c2}) selisih: dist={val_d}, seq={val_s}, diff={diff}"
    return True, max_diff, f"Validasi J3 Sukses (Max diff: {max_diff:.2e} <= {rtol:.2e})"

def validate_j4(dist_result: Dict[str, Any], seq_result: Dict[str, Any], tol: float = 1e-6) -> Tuple[bool, float, str]:
    """Validasi J4: Centroid K-Means (toleransi 1e-6 karena permutasi/urutan float addition)."""
    c_dist = np.array(dist_result["centroids"], dtype=np.float64)
    c_seq = np.array(seq_result["centroids"], dtype=np.float64)
    
    # Cocokkan pasangan centroid terdekat
    from scipy.spatial.distance import cdist
    dists = cdist(c_dist, c_seq)
    min_dists = np.min(dists, axis=1)
    max_shift = float(np.max(min_dists))
    
    if max_shift > tol:
        return False, max_shift, f"Centroid J4 tidak cocok (Pergeseran max: {max_shift:.2e} > toleransi {tol:.2e})"
    return True, max_shift, f"Validasi J4 Sukses (Max centroid shift: {max_shift:.2e} <= {tol:.2e})"
