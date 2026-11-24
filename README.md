# myData: Platform Data Mining Terdistribusi (Arsitektur Master–Worker)

Proyek ini dibangun untuk memenuhi **UAS Komputasi Paralel dan Sistem Terdistribusi** (Tema #5: Distributed Data Mining). Sistem dirancang menggunakan arsitektur **Master–Worker** (1 Node Master + 9 Node Worker fisik = 10 node fisik pada subnet `192.168.1.0/24`) dengan dukungan penuh lintas platform (Windows dan Linux).

---

## 1. Pemenuhan 6 Kewajiban Utama UAS

1. **Task Decomposition:** Dataset skala jutaan baris (NYC TLC Yellow Taxi) dibersihkan dan dipecah menjadi chunk Parquet terkompresi (200.000–500.000 baris/chunk). 1 Task = 1 Chunk + 1 Operasi (+ nomor iterasi untuk K-Means). Pola Map-Reduce.
2. **Parallel Processing:** Memanfaatkan multicore pada tiap Worker menggunakan `ProcessPoolExecutor` metode `spawn`. Chunk di-subchunk langsung dari disk/memori lokal untuk menghindari serialisasi pickle DataFrame antarproses.
3. **Distributed Processing:** Komunikasi Master–Worker lintas 10 node fisik melalui protokol HTTP/JSON (kontrol dan penugasan) serta HTTP Binary Stream (transfer file chunk Parquet dengan verifikasi integritas SHA-256).
4. **Dynamic Load Balancing:** 
   - **Mode Dinamis (Bawaan):** Worker menarik tugas (*pull-based*) sesuai kecepatan pemrosesan, sehingga worker cepat otomatis memproses lebih banyak chunk.
   - **Mode Statis (Pembanding):** Task dibagikan secara *round-robin* saat job dibuat.
5. **Fault Tolerance & Self-Healing:**
   - Detak jantung (*heartbeat*) terisolasi tiap 2 detik (timeout 6 detik $\rightarrow$ status `DOWN`).
   - Sistem *lease* task (30 detik, otomatis diperpanjang saat task aktif).
   - *Re-queue* task otomatis ke antrean depan dengan batas percobaan (*max 3 retry*).
   - Idempotensi hasil task menggunakan kunci `(task_id, attempt)`.
   - Supervisor Worker (`supervisor.py`) untuk pemulihan otomatis (*self-healing*) tanpa systemd.
   - Fault injection API: `/admin/kill`, `/admin/hang`, `/admin/mute`.
6. **Performance Evaluation:** Pengujian otomatis Skenario A sampai F: Execution Time ($T_s, T_p$), Speedup ($S = T_s / T_p$), Efisiensi ($E = S / p$), Throughput (baris/detik), analisis overhead jaringan (transfer vs komputasi), *cold cache* vs *warm cache*, serta verifikasi Hukum Amdahl.

---

## 2. Struktur Repositori

```text
mydata/
├── master/         # FastAPI: scheduler, load_balancer, fault_monitor, reducer, db, api
├── worker/         # agent, supervisor, executor (multiprocessing spawn), tasks, cache
├── common/         # schema, protokol, aturan cleaning, util chunk, merge statistik (Chan/Welford)
├── baseline/       # skrip Sequential (Ts) dan Local Parallel (multiprocessing tanpa jaringan)
├── benchmark/      # runner skenario A-F, validator toleransi numerik, export CSV/JSON/PNG
├── web/            # Next.js + React + Bootstrap 5 + Recharts (BFF, SSE status klaster)
├── scripts/        # prepare_dataset, setup.ps1, setup.sh, cek_konektivitas, fault_inject
└── docs/           # topologi 10 node, panduan lab, spesifikasi hardware
```

---

## 3. Panduan Cepat Menjalankan Sistem

### A. Persiapan Lingkungan & Dependensi
* **Windows:**
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
  ```
* **Linux:**
  ```bash
  chmod +x scripts/setup.sh
  ./scripts/setup.sh
  ```

### B. Menyiapkan Dataset Parquet
Jalankan skrip persiapan dataset (membersihkan dan memecah ke Parquet terkompresi):
```powershell
.\.venv\Scripts\python.exe scripts/prepare_dataset.py --rows 1000000 --chunk-size 200000
```

### C. Menjalankan Node Master (Node N0)
Nyalakan layanan Master API (FastAPI) pada port 8000:
```powershell
.\.venv\Scripts\python.exe -m master.main
```

### D. Menjalankan Node Worker (Node N1 s/d N9)
Nyalakan agen Worker di bawah pengawasan supervisor *self-healing*:
```powershell
.\.venv\Scripts\python.exe worker/supervisor.py --master http://192.168.1.10:8000 --id worker-1 --port 9000
```

### E. Menjalankan Dashboard Web Next.js
Buka direktori `web` dan jalankan server pengembangan:
```bash
cd web
npm run dev
```
Buka browser pada: `http://localhost:3000` (atau IP Master: `http://192.168.1.10:3000`).

---

## 4. Eksekusi Pengujian Skenario (A s/d F)

Pengujian dapat dijalankan dari menu **Benchmark** di web dashboard atau melalui antarmuka terminal:

* **Skenario A (Sequential Baseline):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s A --job J4_KMEANS -r 3
  ```
* **Skenario B (Local Parallel 1 PC):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s B --job J4_KMEANS -r 3
  ```
* **Skenario C (Distributed Komputasi):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s C --job J4_KMEANS -r 3
  ```
* **Skenario D (Load Balancing Statis vs Dinamis):**
  Jalankan job dengan toggle Dinamis lalu Statis pada form Buat Job.
* **Skenario E (Fault Tolerance):**
  Gunakan halaman **Uji Kegagalan** di browser atau panggil:
  ```powershell
  .\.venv\Scripts\python.exe scripts/fault_inject.py kill worker-1
  ```
* **Skenario F (Skalabilitas 1, 2, 4, 6, 9 Worker):**
  ```powershell
  .\.venv\Scripts\python.exe benchmark/runner.py -s F --job J4_KMEANS -r 3
  ```

---

## 5. Validasi Kebenaran Hasil (Kebutuhan F15)

Hasil terdistribusi divalidasi terhadap baseline sekuensial:
* **J1 s/d J3:** Batas toleransi relatif `rtol = 1e-9`.
* **J4 (Centroid K-Means):** Batas toleransi pergeseran centroid `1e-6` (toleransi perbedaan urutan penjumlahan floating-point).
