"""
Supervisor Worker myData (Self-Healing Process Watchdog).
Menjalankan worker.py sebagai subproses dan secara otomatis menghidupkannya kembali
saat terbunuh (misalnya setelah /admin/kill), memungkinkan demonstrasi resiliensi tanpa systemd.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def run_supervised_worker(args_list):
    worker_script = ROOT_DIR / "worker" / "worker.py"
    cmd = [sys.executable, str(worker_script)] + args_list
    
    print("[*] ===========================================================")
    print("[*] myData Worker Supervisor Dimulai (Self-Healing Watchdog)")
    print(f"[*] Menjalankan perintah: {' '.join(cmd)}")
    print("[*] ===========================================================")
    
    restart_count = 0
    while True:
        try:
            print(f"\n[*] [Supervisor] Memulai proses worker (Run #{restart_count + 1})...")
            p = subprocess.Popen(cmd)
            p.wait()
            
            exit_code = p.returncode
            if exit_code == 0:
                print("[*] [Supervisor] Worker selesai secara normal.")
                break
            restart_count += 1
            print(f"\n[!] [Supervisor] Worker terhenti (Exit Code: {exit_code}).")
            print("[*] [Supervisor] Memulihkan Worker dalam 3 detik untuk demonstrasi self-healing...")
            time.sleep(3.0)
            
        except KeyboardInterrupt:
            print("\n[*] [Supervisor] Menerima sinyal keyboard interrupt. Menghentikan supervisor...")
            if p.poll() is None:
                p.terminate()
            break
        except Exception as e:
            print(f"[!] [Supervisor] Terjadi kesalahan: {e}")
            time.sleep(3.0)

if __name__ == "__main__":
    # Teruskan seluruh argumen CLI ke worker.py
    forwarded_args = sys.argv[1:]
    run_supervised_worker(forwarded_args)
