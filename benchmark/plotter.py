"""
Pembuat Grafik Otomatis Matplotlib untuk Visualisasi Bab IV Laporan.
Menghasilkan grafik PNG: Speedup, Efisiensi Paralel, Estimasi Hukum Amdahl,
serta Rincian Overhead Jaringan (Transfer vs Komputasi).
"""

from pathlib import Path
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import numpy as np

# Konfigurasi gaya visualisasi profesional
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 14,
    "legend.fontsize": 10,
    "figure.titlesize": 16
})

def plot_speedup_and_efficiency(
    p_values: List[int],
    speedups: List[float],
    serial_fraction: float = 0.05,
    save_path: Path = None
):
    """Membuat grafik Speedup dan Efisiensi Paralel dengan garis Amdahl."""
    p_arr = np.array(p_values)
    s_arr = np.array(speedups)
    eff_arr = s_arr / p_arr
    
    # Hitung kurva teoritis Hukum Amdahl
    p_dense = np.linspace(1, max(p_values) * 1.1, 100)
    amdahl_speedup = 1.0 / (serial_fraction + (1.0 - serial_fraction) / p_dense)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    
    # 1. Grafik Speedup
    ax1.plot(p_dense, p_dense, "k--", label="Ideal Linear (S = p)", alpha=0.7)
    ax1.plot(p_dense, amdahl_speedup, "r-.", label=f"Hukum Amdahl (f={serial_fraction*100:.1f}%)", alpha=0.8)
    ax1.plot(p_arr, s_arr, "bo-", linewidth=2.2, markersize=7, label="Terukur (myData)")
    ax1.set_title("Percepatan (Speedup S) vs Jumlah Node/Proses")
    ax1.set_xlabel("Jumlah Node / Proses (p)")
    ax1.set_ylabel("Speedup (S = Ts / Tp)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)
    
    # 2. Grafik Efisiensi
    ax2.axhline(1.0, color="k", linestyle="--", label="Efisiensi Ideal (100%)", alpha=0.7)
    ax2.plot(p_arr, eff_arr * 100, "ms-", linewidth=2.2, markersize=7, label="Efisiensi Terukur")
    ax2.set_title("Efisiensi Paralel (E) vs Jumlah Node/Proses")
    ax2.set_xlabel("Jumlah Node / Proses (p)")
    ax2.set_ylabel("Efisiensi (%)")
    ax2.set_ylim(0, 110)
    ax2.legend()
    ax2.grid(True, linestyle="--", alpha=0.5)
    
    plt.tight_layout()
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300)
        print(f"[+] Grafik Speedup tersimpan di: {save_path}")
    plt.close()

def plot_network_overhead_breakdown(
    job_labels: List[str],
    compute_times: List[float],
    transfer_times: List[float],
    save_path: Path = None
):
    """Membuat stacked bar chart waktu transfer jaringan vs komputasi murni."""
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    x = np.arange(len(job_labels))
    width = 0.45
    
    ax.bar(x, compute_times, width, label="Waktu Komputasi Murni", color="#2b5c8f")
    ax.bar(x, transfer_times, width, bottom=compute_times, label="Overhead Transfer Jaringan", color="#d95f02")
    
    ax.set_ylabel("Durasi Rata-rata (detik)")
    ax.set_title("Analisis Overhead Jaringan: Komputasi vs Transfer Data")
    ax.set_xticks(x)
    ax.set_xticklabels(job_labels)
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    
    plt.tight_layout()
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300)
        print(f"[+] Grafik Overhead tersimpan di: {save_path}")
    plt.close()

def plot_lb_comparison(
    worker_names: List[str],
    static_times: List[float],
    dynamic_times: List[float],
    save_path: Path = None
):
    """Membuat perbandingan waktu penyelesaian antar-worker pada Mode Statis vs Dinamis."""
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    x = np.arange(len(worker_names))
    width = 0.35
    
    ax.bar(x - width/2, static_times, width, label="Mode Statis (Round-Robin)", color="#e41a1c")
    ax.bar(x + width/2, dynamic_times, width, label="Mode Dinamis (Pull/Adaptive)", color="#4daf4a")
    
    ax.set_ylabel("Waktu Selesai (detik)")
    ax.set_title("Perbandingan Load Balancing: Statis vs Dinamis (Worker Heterogen)")
    ax.set_xticks(x)
    ax.set_xticklabels(worker_names)
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    
    plt.tight_layout()
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300)
        print(f"[+] Grafik Load Balancing tersimpan di: {save_path}")
    plt.close()
