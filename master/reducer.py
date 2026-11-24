"""
Modul Reducer Master: Menggabungkan Hasil Parsial Worker untuk J1, J2, J3, dan Iterasi J4.
"""

from typing import Dict, Any, List, Tuple
import numpy as np

from common.algorithms import (
    j1_reduce,
    j2_reduce,
    j3_reduce,
    j4_reduce_iteration
)

def reduce_job_results(job_type: str, task_results: List[Dict[str, Any]], extra_params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Menggabungkan hasil parsial dari sekumpulan task sesuai tipe job."""
    if not task_results:
        return {"error": "Tidak ada hasil parsial untuk di-reduce"}
        
    if job_type == "J1_STATS":
        return j1_reduce(task_results)
        
    elif job_type == "J2_GROUPBY":
        return j2_reduce(task_results)
        
    elif job_type == "J3_CORR":
        target_cols = extra_params.get("target_cols", [
            "passenger_count", "trip_distance", "fare_amount", "tip_amount", "total_amount", "duration_minutes"
        ])
        return j3_reduce(task_results, target_cols)
        
    elif job_type == "J4_KMEANS":
        current_centroids = np.array(extra_params.get("centroids"), dtype=np.float64)
        new_centroids, shift, counts = j4_reduce_iteration(task_results, current_centroids)
        return {
            "new_centroids": new_centroids.tolist(),
            "shift": float(shift),
            "counts": counts
        }
        
    return {"error": f"Tipe job {job_type} tidak dikenali"}
