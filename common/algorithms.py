"""
Algoritma Data Mining Inti (J1 - J4) Pola Map-Reduce Stabil Numerik.
Digunakan secara identik oleh Sequential Baseline, Local Parallel, dan Distributed Worker.
"""

import math
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# J1: STATISTIK DESKRIPTIF (Chan-Welford Merge)
# ---------------------------------------------------------------------------

def j1_map_chunk(df: pd.DataFrame, numeric_cols: List[str]) -> Dict[str, Any]:
    """
    Menghitung statistik ringkasan per kolom untuk satu chunk.
    Mengembalikan: count, sum, min, max, mean, M2 (sum of squared deviations).
    """
    stats = {}
    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        n = len(series)
        if n == 0:
            continue
        vals = series.to_numpy(dtype=np.float64)
        c_min = float(np.min(vals))
        c_max = float(np.max(vals))
        c_sum = float(np.sum(vals))
        c_mean = float(np.mean(vals))
        # M2 = sum((x - mean)^2)
        c_m2 = float(np.sum((vals - c_mean) ** 2))
        
        stats[col] = {
            "count": n,
            "sum": c_sum,
            "min": c_min,
            "max": c_max,
            "mean": c_mean,
            "m2": c_m2
        }
    return stats

def merge_chan_welford(stat_a: Dict[str, Any], stat_b: Dict[str, Any]) -> Dict[str, Any]:
    """Menggabungkan dua statistik parsial menggunakan rumus stabil Chan/Welford."""
    na, nb = stat_a["count"], stat_b["count"]
    if na == 0:
        return stat_b
    if nb == 0:
        return stat_a
        
    nab = na + nb
    delta = stat_b["mean"] - stat_a["mean"]
    mean_ab = stat_a["mean"] + delta * (nb / nab)
    m2_ab = stat_a["m2"] + stat_b["m2"] + (delta ** 2) * (na * nb / nab)
    min_ab = min(stat_a["min"], stat_b["min"])
    max_ab = max(stat_a["max"], stat_b["max"])
    sum_ab = stat_a["sum"] + stat_b["sum"]
    
    return {
        "count": nab,
        "sum": sum_ab,
        "min": min_ab,
        "max": max_ab,
        "mean": mean_ab,
        "m2": m2_ab
    }

def j1_reduce(partial_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Menggabungkan seluruh hasil parsial J1 dari semua chunk."""
    combined = {}
    for part in partial_results:
        for col, stat in part.items():
            if col not in combined:
                combined[col] = stat
            else:
                combined[col] = merge_chan_welford(combined[col], stat)
                
    # Hitung varians dan simpangan baku akhir
    final_output = {}
    for col, stat in combined.items():
        n = stat["count"]
        variance = (stat["m2"] / (n - 1)) if n > 1 else 0.0
        std = math.sqrt(variance)
        final_output[col] = {
            "count": int(n),
            "sum": float(stat["sum"]),
            "min": float(stat["min"]),
            "max": float(stat["max"]),
            "mean": float(stat["mean"]),
            "variance": float(variance),
            "std": float(std)
        }
    return final_output

# ---------------------------------------------------------------------------
# J2: AGREGASI GROUP-BY
# ---------------------------------------------------------------------------

def j2_map_chunk(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Menghitung akumulasi tarif dan tip berdasarkan:
    1. Jam penjemputan (0 - 23)
    2. Hari penjemputan (0 - 6)
    3. PULocationID
    4. DOLocationID
    """
    res = {
        "by_hour": {},
        "by_day": {},
        "by_pulocation": {},
        "by_dolocation": {}
    }
    
    if "tpep_pickup_datetime" in df.columns:
        dt = pd.to_datetime(df["tpep_pickup_datetime"])
        hours = dt.dt.hour.to_numpy()
        days = dt.dt.dayofweek.to_numpy()
        fares = df["fare_amount"].to_numpy(dtype=np.float64)
        tips = df["tip_amount"].to_numpy(dtype=np.float64)
        
        # Agregasi per Jam
        for h in np.unique(hours):
            mask = (hours == h)
            res["by_hour"][int(h)] = {
                "count": int(np.sum(mask)),
                "fare_sum": float(np.sum(fares[mask])),
                "tip_sum": float(np.sum(tips[mask]))
            }
            
        # Agregasi per Hari
        for d in np.unique(days):
            mask = (days == d)
            res["by_day"][int(d)] = {
                "count": int(np.sum(mask)),
                "fare_sum": float(np.sum(fares[mask])),
                "tip_sum": float(np.sum(tips[mask]))
            }
            
    if "PULocationID" in df.columns:
        pu_ids = df["PULocationID"].to_numpy(dtype=np.int32)
        fares = df["fare_amount"].to_numpy(dtype=np.float64)
        tips = df["tip_amount"].to_numpy(dtype=np.float64)
        for pu in np.unique(pu_ids):
            mask = (pu_ids == pu)
            res["by_pulocation"][int(pu)] = {
                "count": int(np.sum(mask)),
                "fare_sum": float(np.sum(fares[mask])),
                "tip_sum": float(np.sum(tips[mask]))
            }
            
    if "DOLocationID" in df.columns:
        do_ids = df["DOLocationID"].to_numpy(dtype=np.int32)
        fares = df["fare_amount"].to_numpy(dtype=np.float64)
        tips = df["tip_amount"].to_numpy(dtype=np.float64)
        for do in np.unique(do_ids):
            mask = (do_ids == do)
            res["by_dolocation"][int(do)] = {
                "count": int(np.sum(mask)),
                "fare_sum": float(np.sum(fares[mask])),
                "tip_sum": float(np.sum(tips[mask]))
            }
            
    return res

def j2_reduce(partial_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Menggabungkan seluruh agregasi group-by dan menghitung rata-rata."""
    merged = {
        "by_hour": {},
        "by_day": {},
        "by_pulocation": {},
        "by_dolocation": {}
    }
    
    for part in partial_results:
        for group_name in ["by_hour", "by_day", "by_pulocation", "by_dolocation"]:
            part_group = part.get(group_name, {})
            target_group = merged[group_name]
            for key, val in part_group.items():
                k = int(key)
                if k not in target_group:
                    target_group[k] = {"count": val["count"], "fare_sum": val["fare_sum"], "tip_sum": val["tip_sum"]}
                else:
                    target_group[k]["count"] += val["count"]
                    target_group[k]["fare_sum"] += val["fare_sum"]
                    target_group[k]["tip_sum"] += val["tip_sum"]
                    
    # Hitung rata-rata
    output = {}
    for group_name, group_data in merged.items():
        output[group_name] = {}
        for key, val in group_data.items():
            n = val["count"]
            output[group_name][key] = {
                "count": n,
                "fare_sum": val["fare_sum"],
                "tip_sum": val["tip_sum"],
                "avg_fare": (val["fare_sum"] / n) if n > 0 else 0.0,
                "avg_tip": (val["tip_sum"] / n) if n > 0 else 0.0
            }
    return output

# ---------------------------------------------------------------------------
# J3: MATRIKS KORELASI PEARSON (Co-Moments Merge)
# ---------------------------------------------------------------------------

def j3_map_chunk(df: pd.DataFrame, target_cols: List[str]) -> Dict[str, Any]:
    """
    Menghitung co-moments terpusat per chunk untuk setiap pasangan kolom (x, y):
    (count, mean_x, mean_y, Sxx, Syy, Sxy)
    """
    pairs = {}
    # Hitung durasi perjalanan jika belum ada
    local_df = df.copy()
    if "duration_minutes" not in local_df.columns:
        if "tpep_pickup_datetime" in local_df.columns and "tpep_dropoff_datetime" in local_df.columns:
            p = pd.to_datetime(local_df["tpep_pickup_datetime"])
            d = pd.to_datetime(local_df["tpep_dropoff_datetime"])
            local_df["duration_minutes"] = (d - p).dt.total_seconds() / 60.0

    valid_cols = [c for c in target_cols if c in local_df.columns]
    n = len(local_df)
    if n < 2:
        return pairs

    for i in range(len(valid_cols)):
        for j in range(i, len(valid_cols)):
            c1, c2 = valid_cols[i], valid_cols[j]
            x = local_df[c1].to_numpy(dtype=np.float64)
            y = local_df[c2].to_numpy(dtype=np.float64)
            mx = float(np.mean(x))
            my = float(np.mean(y))
            dx = x - mx
            dy = y - my
            sxx = float(np.sum(dx * dx))
            syy = float(np.sum(dy * dy))
            sxy = float(np.sum(dx * dy))
            
            pairs[f"{c1}__{c2}"] = {
                "n": n,
                "mean_x": mx,
                "mean_y": my,
                "sxx": sxx,
                "syy": syy,
                "sxy": sxy
            }
    return pairs

def merge_co_moments(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Menggabungkan dua co-moment statistik secara numerik stabil."""
    na, nb = a["n"], b["n"]
    if na == 0:
        return b
    if nb == 0:
        return a
        
    nab = na + nb
    del_x = b["mean_x"] - a["mean_x"]
    del_y = b["mean_y"] - a["mean_y"]
    
    mean_x = a["mean_x"] + del_x * (nb / nab)
    mean_y = a["mean_y"] + del_y * (nb / nab)
    
    weight = (na * nb) / nab
    sxx = a["sxx"] + b["sxx"] + (del_x ** 2) * weight
    syy = a["syy"] + b["syy"] + (del_y ** 2) * weight
    sxy = a["sxy"] + b["sxy"] + (del_x * del_y) * weight
    
    return {
        "n": nab,
        "mean_x": mean_x,
        "mean_y": mean_y,
        "sxx": sxx,
        "syy": syy,
        "sxy": sxy
    }

def j3_reduce(partial_results: List[Dict[str, Any]], target_cols: List[str]) -> Dict[str, Any]:
    """Menggabungkan seluruh co-moments dan menghasilkan matriks korelasi Pearson."""
    merged_pairs = {}
    for part in partial_results:
        for pair_key, val in part.items():
            if pair_key not in merged_pairs:
                merged_pairs[pair_key] = val
            else:
                merged_pairs[pair_key] = merge_co_moments(merged_pairs[pair_key], val)
                
    # Hitung matriks korelasi Pearson
    matrix = {}
    for c1 in target_cols:
        matrix[c1] = {}
        for c2 in target_cols:
            if f"{c1}__{c2}" in merged_pairs:
                data = merged_pairs[f"{c1}__{c2}"]
            elif f"{c2}__{c1}" in merged_pairs:
                data = merged_pairs[f"{c2}__{c1}"]
            else:
                matrix[c1][c2] = 0.0
                continue
                
            denom = math.sqrt(data["sxx"] * data["syy"])
            r = (data["sxy"] / denom) if denom > 1e-12 else (1.0 if c1 == c2 else 0.0)
            # Batasi rentang [-1.0, 1.0]
            r = max(-1.0, min(1.0, r))
            matrix[c1][c2] = float(r)
            
    return matrix

# ---------------------------------------------------------------------------
# J4: K-MEANS CLUSTERING (Map-Reduce Berbasis Iterasi)
# ---------------------------------------------------------------------------

KMEANS_FEATURES = ["trip_distance", "fare_amount", "tip_amount", "duration_minutes"]

def prepare_kmeans_features(df: pd.DataFrame, norm_params: Dict[str, Dict[str, float]]) -> np.ndarray:
    """Mengekstrak dan menstandarisasi fitur (z-score) sesuai hasil J1."""
    local_df = df.copy()
    if "duration_minutes" not in local_df.columns:
        p = pd.to_datetime(local_df["tpep_pickup_datetime"])
        d = pd.to_datetime(local_df["tpep_dropoff_datetime"])
        local_df["duration_minutes"] = (d - p).dt.total_seconds() / 60.0

    features = []
    for col in KMEANS_FEATURES:
        vals = local_df[col].to_numpy(dtype=np.float64)
        m = norm_params.get(col, {}).get("mean", 0.0)
        s = norm_params.get(col, {}).get("std", 1.0)
        s = s if s > 1e-6 else 1.0
        z = (vals - m) / s
        features.append(z)
        
    return np.column_stack(features)

def init_kmeans_plus_plus(sample_data: np.ndarray, k: int = 8, seed: int = 42) -> np.ndarray:
    """Inisialisasi Centroid K-Means++ deterministik dengan seed tetap."""
    rng = np.random.RandomState(seed)
    n_samples, n_features = sample_data.shape
    centroids = np.empty((k, n_features), dtype=np.float64)
    
    # 1. Pilih centroid pertama secara acak dari sampel
    first_idx = rng.randint(0, n_samples)
    centroids[0] = sample_data[first_idx]
    
    # 2. Pilih sisa centroid dengan probabilitas proporsional terhadap jarak kuadrat D(x)^2
    closest_dist_sq = np.sum((sample_data - centroids[0]) ** 2, axis=1)
    
    for c_idx in range(1, k):
        total_dist_sq = np.sum(closest_dist_sq)
        if total_dist_sq == 0:
            probs = np.ones(n_samples) / n_samples
        else:
            probs = closest_dist_sq / total_dist_sq
            
        chosen_idx = rng.choice(n_samples, p=probs)
        centroids[c_idx] = sample_data[chosen_idx]
        
        # Perbarui jarak terdekat
        new_dist_sq = np.sum((sample_data - centroids[c_idx]) ** 2, axis=1)
        closest_dist_sq = np.minimum(closest_dist_sq, new_dist_sq)
        
    return centroids

def j4_map_chunk(features: np.ndarray, centroids: np.ndarray) -> Dict[str, Any]:
    """
    Map Worker untuk K-Means:
    Assign setiap titik ke centroid terdekat menggunakan jarak Euclidean kuadrat,
    lalu mengakumulasikan sum of points dan count per cluster.
    """
    k = centroids.shape[0]
    n_features = features.shape[1]
    
    # Jarak kuadrat: ||X - C||^2 = ||X||^2 - 2 X C^T + ||C||^2
    # Dioptimasi dengan matriks NumPy
    x_sq = np.sum(features ** 2, axis=1, keepdims=True)
    c_sq = np.sum(centroids ** 2, axis=1, keepdims=True).T
    cross = np.dot(features, centroids.T)
    dist_sq = x_sq - 2 * cross + c_sq
    
    assignments = np.argmin(dist_sq, axis=1)
    
    cluster_counts = np.zeros(k, dtype=np.int64)
    cluster_sums = np.zeros((k, n_features), dtype=np.float64)
    
    for c in range(k):
        mask = (assignments == c)
        count_c = int(np.sum(mask))
        cluster_counts[c] = count_c
        if count_c > 0:
            cluster_sums[c] = np.sum(features[mask], axis=0)
            
    return {
        "counts": cluster_counts.tolist(),
        "sums": cluster_sums.tolist()
    }

def j4_reduce_iteration(
    partial_results: List[Dict[str, Any]],
    current_centroids: np.ndarray
) -> Tuple[np.ndarray, float, List[int]]:
    """
    Reduce Master per iterasi K-Means:
    Menjumlahkan akumulasi count dan sum dari semua Worker,
    memperbarui lokasi centroid, dan menghitung pergeseran maksimum centroid (shift).
    """
    k, n_features = current_centroids.shape
    total_counts = np.zeros(k, dtype=np.int64)
    total_sums = np.zeros((k, n_features), dtype=np.float64)
    
    for part in partial_results:
        total_counts += np.array(part["counts"], dtype=np.int64)
        total_sums += np.array(part["sums"], dtype=np.float64)
        
    new_centroids = np.copy(current_centroids)
    for c in range(k):
        if total_counts[c] > 0:
            new_centroids[c] = total_sums[c] / total_counts[c]
        else:
            # Cluster kosong mempertahankan posisi centroid lama
            new_centroids[c] = current_centroids[c]
            
    # Hitung pergeseran maksimum (L2-norm)
    shifts = np.linalg.norm(new_centroids - current_centroids, axis=1)
    max_shift = float(np.max(shifts))
    
    return new_centroids, max_shift, total_counts.tolist()
