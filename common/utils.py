"""
Fungsi Utilitas Bersama (Checksum SHA-256, Metrik Sistem, Info Perangkat Keras).
"""

import hashlib
import platform
import socket
import time
from pathlib import Path
from typing import Dict, Any
import psutil

def calculate_checksum(file_path: Path) -> str:
    """Menghitung SHA-256 checksum dari sebuah file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):  # 1MB buffer
            sha256.update(chunk)
    return sha256.hexdigest()

def get_system_metrics() -> Dict[str, float]:
    """Membaca utilisasi CPU dan RAM saat ini (non-blocking)."""
    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        return {
            "cpu_pct": float(cpu_pct),
            "mem_pct": float(mem.percent)
        }
    except Exception:
        return {"cpu_pct": 0.0, "mem_pct": 0.0}

def get_local_ip() -> str:
    """Mendapatkan alamat IP lokal node pada antarmuka jaringan utama."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Menghubungkan socket dummy ke gateway tanpa mengirim paket
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def get_node_hardware_info(worker_id: str) -> Dict[str, Any]:
    """Mengumpulkan spesifikasi fisik node (OS, CPU, RAM, Python)."""
    return {
        "id": worker_id,
        "hostname": platform.node(),
        "ip": get_local_ip(),
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "cpu_model": platform.processor() or "Unknown CPU",
        "cores": psutil.cpu_count(logical=True) or 1,
        "ram_mb": int(psutil.virtual_memory().total / (1024 * 1024))
    }

class Timer:
    """Utilitas pencatat waktu presisi tinggi berbasis time.perf_counter()."""
    def __init__(self):
        self.start_time = 0.0
        self.elapsed = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start_time
