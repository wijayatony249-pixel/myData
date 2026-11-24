#!/usr/bin/env bash
# ==============================================================================
# Skrip Otomatisasi Instalasi & Firewall Node Linux (myData Platform)
# ==============================================================================

set -e

echo "=========================================================="
echo " Memulai Instalasi Lingkungan myData (Linux Node)"
echo "=========================================================="

# 1. Periksa Python 3.11
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 tidak ditemukan. Harap pasang python3 dan python3-venv."
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[*] Terdeteksi Python: $PY_VER"

# 2. Buat Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[*] Membuat virtual environment (.venv)..."
    python3 -m venv .venv
fi

# 3. Pasang Dependensi Ter-pin
echo "[*] Memasang dependensi dari requirements.txt..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Buka Port Firewall (ufw jika aktif)
if command -v ufw &> /dev/null; then
    echo "[*] Mengonfigurasi firewall ufw..."
    sudo ufw allow 8000/tcp comment 'myData Master API' || true
    sudo ufw allow 9000/tcp comment 'myData Worker Agent' || true
    sudo ufw allow 3000/tcp comment 'myData Web UI' || true
fi

export PYTHONUTF8=1

echo ""
echo "[+] Setup Linux Selesai! Jalankan Worker dengan:"
echo "    source .venv/bin/activate"
echo "    python worker/worker.py --master http://192.168.1.10:8000 --id worker-linux-1"
