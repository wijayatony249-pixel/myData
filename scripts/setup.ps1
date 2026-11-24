# ==============================================================================
# Skrip Otomatisasi Instalasi & Firewall Node Windows (myData Platform)
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Memulai Instalasi Lingkungan myData (Windows Node)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Periksa Python 3.11
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[!] Python tidak ditemukan di PATH. Harap instal Python 3.11." -ForegroundColor Red
    exit 1
}

$pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "[*] Terdeteksi Python Versi: $pyVer" -ForegroundColor Green

# 2. Buat Virtual Environment jika belum ada
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Membuat virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

# 3. Pasang Dependensi Ter-pin
Write-Host "[*] Memasang dependensi dari requirements.txt..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt

# 4. Buka Port Firewall Windows (Port 8000 Master, Port 9000 Worker, Port 3000 Web)
Write-Host "[*] Mengonfigurasi Windows Firewall untuk myData..." -ForegroundColor Yellow
try {
    netsh advfirewall firewall add rule name="myData Master API" dir=in action=allow protocol=TCP localport=8000
    netsh advfirewall firewall add rule name="myData Worker Agent" dir=in action=allow protocol=TCP localport=9000
    netsh advfirewall firewall add rule name="myData Web UI" dir=in action=allow protocol=TCP localport=3000
    Write-Host "[+] Aturan firewall berhasil ditambahkan." -ForegroundColor Green
} catch {
    Write-Host "[!] Membutuhkan hak akses Administrator untuk konfigurasi firewall." -ForegroundColor Magenta
}

# 5. Standarisasi UTF-8
$env:PYTHONUTF8 = "1"

Write-Host "`n[+] Setup Selesai! Jalankan Worker dengan:" -ForegroundColor Cyan
Write-Host "    .\.venv\Scripts\python.exe worker/worker.py --master http://192.168.1.10:8000 --id worker-1" -ForegroundColor White
