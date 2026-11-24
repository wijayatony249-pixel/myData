# Panduan Praktikum & Pengujian Lab 10 Node (myData)

Panduan operasional langkah demi langkah untuk menjalankan pengujian klaster data mining terdistribusi di laboratorium jaringan.

---

## 1. Persiapan Node Master (Node N0: `192.168.1.10`)

1. **Pastikan IP Statis Terpasang:**
   * IP: `192.168.1.10` | Netmask: `255.255.255.0` | Gateway: `192.168.1.1`
2. **Klon / Buka Repositori myData:**
   ```powershell
   cd "E:\Projek KPT"
   ```
3. **Konfigurasi Environment `.env`:**
   Pastikan variabel `MASTER_HOST=192.168.1.10` atau `0.0.0.0` dan token bersama sesuai.
4. **Jalankan Skrip Instalasi Dependensi:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
   ```
5. **Siapkan Dataset (Generate atau Masukkan Parquet NYC Taxi):**
   ```powershell
   .\.venv\Scripts\python.exe scripts/prepare_dataset.py --rows 1000000 --chunk-size 200000
   ```
6. **Nyalakan Layanan Master API:**
   ```powershell
   .\.venv\Scripts\python.exe -m master.main
   ```
   *(Master API aktif pada `http://192.168.1.10:8000`)*
7. **Nyalakan Dashboard Web Next.js:**
   ```powershell
   cd web
   npm run dev
   ```
   *(Web Dashboard dapat diakses dari browser di `http://192.168.1.10:3000`)*

---

## 2. Persiapan Node Worker (Node N1 s/d N9)

Lakukan langkah ini pada masing-masing laptop/PC Worker:

1. **Hubungkan Kabel LAN / WiFi Klaster:**
   * Atur IP statis sesuai tabel topologi (`192.168.1.11` s/d `192.168.1.19`).
2. **Salin Folder Proyek myData ke Worker.**
3. **Jalankan Skrip Setup:**
   * **Untuk Windows:**
     ```powershell
     powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
     ```
   * **Untuk Linux:**
     ```bash
     chmod +x scripts/setup.sh
     ./scripts/setup.sh
     ```
4. **Jalankan Worker di Bawah Pengawasan Supervisor:**
   * **Windows:**
     ```powershell
     .\.venv\Scripts\python.exe worker/supervisor.py --master http://192.168.1.10:8000 --id worker-1 --port 9000
     ```
   * **Linux:**
     ```bash
     source .venv/bin/activate
     python worker/supervisor.py --master http://192.168.1.10:8000 --id worker-linux-3 --port 9000
     ```
   *(Ubah `--id worker-X` sesuai nomor urut node)*

---

## 3. Verifikasi & Diagnostik Sebelum Pengujian

Dari laptop Master, jalankan uji konektivitas seluruh node:
```powershell
.\.venv\Scripts\python.exe scripts/cek_konektivitas.py
```
*Pastikan seluruh port 8000 dan 9000 berstatus `[OK]` (100% lolos).*

---

## 4. Eksekusi Skenario Pengujian (A s/d F)

Pengujian dapat dijalankan langsung melalui web dashboard pada menu **Benchmark** atau melalui CLI:

* **Skenario A (Baseline Sequential):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s A --job J4_KMEANS -r 3
  ```
* **Skenario B (Local Parallel Multiprocessing):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s B --job J4_KMEANS -r 3
  ```
* **Skenario C (Distributed Komputasi):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s C --job J4_KMEANS -r 3
  ```
* **Skenario D (Load Balancing Dinamis vs Statis):**
  Jalankan job dengan toggle *Dinamis* kemudian *Statis* di halaman **Buat Job**, amati waktu penyelesaian antar-worker.
* **Skenario E (Uji Ketahanan & Fault Injection):**
  1. Buka halaman **Uji Kegagalan** di browser.
  2. Saat job J4 sedang berjalan, klik tombol **"Matikan Worker"** pada salah satu worker.
  3. Amati perubahan status worker menjadi `DOWN` dalam 6 detik, task di-requeue ke antrean depan, dan supervisor otomatis menghidupkan kembali worker tersebut.
* **Skenario F (Skalabilitas 1, 2, 4, 6, 9 Worker):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s F --job J4_KMEANS -r 3
  ```

---

## 5. Perekaman Video Demo (Maksimal 5 Menit)

Struktur durasi video demonstrasi untuk diserahkan sebagai tugas UAS:
1. **Menit 0:00 - 0:45:** Penjelasan ringkas topologi fisik 10 node dan arsitektur Master-Worker myData.
2. **Menit 0:45 - 2:00:** Menjalankan Job J4 K-Means terdistribusi, menunjukkan progress bar real-time, utilisasi CPU/RAM via SSE, dan validasi kebenaran hasil terhadap sequential.
3. **Menit 2:00 - 3:15:** Demonstrasi Fault Tolerance: menyuntikkan kegagalan (/admin/kill), memperlihatkan deteksi down, requeue task, dan pencatatan *Recovery Time*.
4. **Menit 3:15 - 4:30:** Memperlihatkan halaman Benchmark, perbandingan Speedup kurva Amdahl, dan perbandingan Load Balancing Dinamis vs Statis.
5. **Menit 4:30 - 5:00:** Penutup, ekspor data CSV/JSON, dan kesimpulan singkat.
