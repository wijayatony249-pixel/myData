"""
Skrip Diagnostik Jaringan & Konektivitas 10 Node myData.
Menguji konektivitas ping, soket port TCP (8000 Master, 9000 Worker),
serta mengukur latensi round-trip (RTT) antarnode sebelum pengujian lab dimulai.
"""

import argparse
import socket
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple
import httpx

# Topologi IP bawaan sesuai PRD
DEFAULT_NODES = {
    "N0 (Master)": {"ip": "192.168.1.10", "ports": [8000, 3000, 5432]},
    "N1 (Worker-1)": {"ip": "192.168.1.11", "ports": [9000]},
    "N2 (Worker-2)": {"ip": "192.168.1.12", "ports": [9000]},
    "N3 (Worker-3)": {"ip": "192.168.1.13", "ports": [9000]},
    "N4 (Worker-4)": {"ip": "192.168.1.14", "ports": [9000]},
    "N5 (Worker-5)": {"ip": "192.168.1.15", "ports": [9000]},
    "N6 (Worker-6)": {"ip": "192.168.1.16", "ports": [9000]},
    "N7 (Worker-7)": {"ip": "192.168.1.17", "ports": [9000]},
    "N8 (Worker-8)": {"ip": "192.168.1.18", "ports": [9000]},
    "N9 (Worker-9)": {"ip": "192.168.1.19", "ports": [9000]},
}

def check_tcp_port(ip: str, port: int, timeout: float = 1.5) -> Tuple[bool, float]:
    """Mencoba koneksi socket TCP dan menghitung latensi (ms)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        s.connect((ip, port))
        latency_ms = (time.perf_counter() - t0) * 1000.0
        s.close()
        return True, latency_ms
    except Exception:
        return False, 0.0

def run_diagnostics(target_nodes: Dict[str, Any]):
    print("=================================================================")
    print(" Uji Konektivitas Jaringan Klaster myData (10 Node Fisik)")
    print("=================================================================")
    
    total_ports = 0
    passed_ports = 0
    
    for name, node in target_nodes.items():
        ip = node["ip"]
        ports = node["ports"]
        print(f"\n[*] Memeriksa {name} ({ip}):")
        
        for p in ports:
            total_ports += 1
            ok, lat = check_tcp_port(ip, p)
            if ok:
                passed_ports += 1
                print(f"    [OK] Port {p} Terbuka | Latensi RTT: {lat:.2f} ms")
            else:
                print(f"    [FAIL] Port {p} Tertutup / Tidak Dapat Dijangkau (Periksa Firewall / Kabel)")
                
    pct = (passed_ports / total_ports * 100.0) if total_ports > 0 else 0
    print("\n-----------------------------------------------------------------")
    print(f"Hasil Diagnostik: {passed_ports}/{total_ports} port aktif ({pct:.1f}% lolos)")
    if pct == 100:
        print("[+] Seluruh node siap untuk pengujian klaster terdistribusi!")
    else:
        print("[!] Beberapa node belum siap. Pastikan port sudah dibuka dan kabel LAN terpasang.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostik Konektivitas Node myData")
    parser.add_argument("--local", action="store_true", help="Uji konektivitas localhost (127.0.0.1)")
    args = parser.parse_args()
    
    nodes = DEFAULT_NODES
    if args.local:
        nodes = {
            "Master Lokal": {"ip": "127.0.0.1", "ports": [8000]},
            "Worker Lokal": {"ip": "127.0.0.1", "ports": [9000]}
        }
    run_diagnostics(nodes)
