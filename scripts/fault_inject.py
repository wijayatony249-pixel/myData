"""
Alat Bantu CLI Fault Injector myData.
Mengirim perintah /admin/kill, /admin/hang, atau /admin/mute ke Worker via Master API.
"""

import argparse
import sys
import httpx

from common.config import MASTER_URL

def inject_fault(action: str, worker_id: str, master_url: str = MASTER_URL):
    url = f"{master_url}/faults/{action}/{worker_id}"
    print(f"[*] Mengirim permintaan suntik kegagalan: {action.upper()} ke {worker_id}...")
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url)
            print(f"[+] Status HTTP: {resp.status_code}")
            print(f"[+] Respons: {resp.json()}")
    except Exception as e:
        print(f"[!] Gagal menghubungi Master: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Fault Injector myData")
    parser.add_argument("action", choices=["kill", "hang", "mute"], help="Jenis kegagalan")
    parser.add_argument("worker_id", help="ID Worker target (contoh: worker-1)")
    parser.add_argument("--master", default=MASTER_URL, help="URL Master")
    
    args = parser.parse_args()
    inject_fault(args.action, args.worker_id, args.master)
