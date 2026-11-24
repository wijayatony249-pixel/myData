"""
Skrip Peluncur Klaster Lokal myData (Master + N Worker Lokal di 1 Komputer).
Memungkinkan pengujian penuh arsitektur Master-Worker, Load Balancing,
Fault Injection, dan Dashboard Web tanpa memerlukan laptop/PC fisik terpisah.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description="Jalankan Klaster myData Lengkap di 1 Komputer")
    parser.add_argument("-w", "--workers", type=int, default=3, help="Jumlah Worker lokal yang dijalankan (default: 3, maks: 9)")
    parser.add_argument("--master-port", type=int, default=8000, help="Port Master API (default: 8000)")
    
    args = parser.parse_args()
    num_workers = min(max(args.workers, 1), 9)
    
    processes = []
    
    python_exe = sys.executable
    master_script = ROOT_DIR / "master" / "main.py"
    worker_script = ROOT_DIR / "worker" / "worker.py"
    
    print("=================================================================")
    print("  myData: Peluncur Klaster Lokal (1 Komputer Mandiri)")
    print(f"  Konfigurasi: 1 Master + {num_workers} Worker Lokal")
    print("=================================================================")
    
    try:
        # Cek apakah Master sudah berjalan di port 8000
        master_already_running = False
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{args.master_port}/health", timeout=1.0)
            master_already_running = True
        except Exception:
            pass

        if master_already_running:
            print(f"\n[*] [1/2] Master API sudah aktif pada http://127.0.0.1:{args.master_port}.")
        else:
            print(f"\n[*] [1/2] Menyalakan Master API pada http://127.0.0.1:{args.master_port}...")
            p_master = subprocess.Popen(
                [python_exe, "-m", "master.main"],
                cwd=str(ROOT_DIR)
            )
            processes.append(("Master", p_master))
            time.sleep(2.0)
        
        # 2. Jalankan N Worker Lokal pada port terpisah
        print(f"[*] [2/2] Menyalakan {num_workers} Worker lokal...")
        for i in range(1, num_workers + 1):
            w_id = f"worker-{i}"
            w_port = 9000 + i
            print(f"    -> Menyalakan {w_id} (Port Admin: {w_port})...")
            p_worker = subprocess.Popen(
                [
                    python_exe,
                    str(worker_script),
                    "--master", f"http://127.0.0.1:{args.master_port}",
                    "--id", w_id,
                    "--port", str(w_port)
                ],
                cwd=str(ROOT_DIR)
            )
            processes.append((w_id, p_worker))
            time.sleep(0.5)
            
        print("\n[+] Seluruh klaster lokal berhasil aktif!")
        print("-----------------------------------------------------------------")
        print("  • Master API    : http://127.0.0.1:8000/docs")
        print("  • Web Dashboard : http://localhost:3000")
        print("-----------------------------------------------------------------")
        print("[*] Tekan Ctrl+C di terminal ini untuk mematikan seluruh klaster.\n")
        
        # Jaga proses tetap berjalan
        while True:
            time.sleep(1.0)
            for name, proc in processes:
                if proc.poll() is not None:
                    # Proses berhenti tidak terduga
                    pass
                    
    except KeyboardInterrupt:
        print("\n[*] Menerima sinyal berhenti (Ctrl+C). Menghentikan seluruh proses...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"    Menghentikan {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except Exception:
                    proc.kill()
        print("[+] Seluruh proses klaster telah dihentikan dengan aman.")

if __name__ == "__main__":
    main()
