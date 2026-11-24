"""
Konfigurasi terpusat untuk Master dan Worker myData.
Membaca environment variable dengan fallback default yang aman.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Temukan file .env dari root proyek
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# Token Bersama Keamanan Antar-Node
CLUSTER_TOKEN = os.getenv("CLUSTER_TOKEN", "mydata-token-uas-kpt-2026")

# Konfigurasi Jaringan Master & Worker
MASTER_HOST = os.getenv("MASTER_HOST", "0.0.0.0")
MASTER_PORT = int(os.getenv("MASTER_PORT", "8000"))
MASTER_URL = os.getenv("MASTER_URL", f"http://127.0.0.1:{MASTER_PORT}")
WORKER_PORT = int(os.getenv("WORKER_PORT", "9000"))

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{ROOT_DIR / 'data' / 'mydata.db'}"
)

# Konfigurasi Data & Direktori
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT_DIR / "data")))
CHUNKS_DIR = DATA_DIR / "chunks"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(DATA_DIR / "cache")))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "200000"))

# Pastikan folder esensial ada
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Fault Tolerance & Heartbeat Parameters
HEARTBEAT_INTERVAL_SEC = float(os.getenv("HEARTBEAT_INTERVAL_SEC", "2.0"))
HEARTBEAT_TIMEOUT_SEC = float(os.getenv("HEARTBEAT_TIMEOUT_SEC", "6.0"))
LEASE_DURATION_SEC = float(os.getenv("LEASE_DURATION_SEC", "30.0"))
MAX_TASK_ATTEMPTS = int(os.getenv("MAX_TASK_ATTEMPTS", "3"))

# Multiprocessing
WORKER_PROCESSES = int(os.getenv("WORKER_PROCESSES", "0"))
