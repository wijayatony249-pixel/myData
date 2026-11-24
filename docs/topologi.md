# Topologi & Spesifikasi 10 Node Fisik Klaster myData

Dokumen ini memuat perincian topologi jaringan fisik dan spesifikasi setiap node yang digunakan untuk pengujian UAS Komputasi Paralel dan Sistem Terdistribusi (Tema #5 Distributed Data Mining).

---

## 1. Topologi Jaringan Lokal (Subnet: `192.168.1.0/24`)

* **Medium Jaringan:** Gigabit Ethernet Switch 16-Port (Cat6) / Router WiFi 6
* **Alamat Gateway:** `192.168.1.1`
* **Subnet Mask:** `255.255.255.0`
* **DNS:** `8.8.8.8` / Local

```
                  ┌─────────────────────────────┐
                  │ Gigabit Switch / Router LAN │
                  └──────────────┬──────────────┘
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
┌────┴─────────────────┐ ┌───────┴──────────────┐   ┌───────┴──────────────┐
│ N0: Master + DB + UI │ │ N1: Worker-1         │...│ N9: Worker-9         │
│ IP: 192.168.1.10     │ │ IP: 192.168.1.11     │   │ IP: 192.168.1.19     │
│ Ports: 8000,3000,5432│ │ Port: 9000           │   │ Port: 9000           │
└──────────────────────┘ └──────────────────────┘   └──────────────────────┘
```

---

## 2. Tabel Rincian Node Klaster

| ID Node | Peran | Alamat IP | Port Layanan | Sistem Operasi | Model CPU | Core (L/P) | RAM (GB) | Versi Python |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **N0** | Master + Web + DB | `192.168.1.10` | 8000, 3000, 5432 | Windows 11 / Linux | Intel Core i7 / Ryzen 7 | 8C / 16T | 16 GB | 3.11.9 |
| **N1** | Worker-1 | `192.168.1.11` | 9000 | Windows 11 | Intel Core i5 / AMD Ryzen | 6C / 12T | 8 GB | 3.11.9 |
| **N2** | Worker-2 | `192.168.1.12` | 9000 | Windows 10 | Intel Core i5 | 4C / 8T | 8 GB | 3.11.9 |
| **N3** | Worker-3 | `192.168.1.13` | 9000 | Ubuntu 22.04 LTS | AMD Ryzen 5 | 6C / 12T | 16 GB | 3.11.9 |
| **N4** | Worker-4 | `192.168.1.14` | 9000 | Windows 11 | Intel Core i7 | 8C / 16T | 16 GB | 3.11.9 |
| **N5** | Worker-5 | `192.168.1.15` | 9000 | Ubuntu 24.04 LTS | Intel Core i3 | 4C / 4T | 8 GB | 3.11.9 |
| **N6** | Worker-6 | `192.168.1.16` | 9000 | Windows 11 | AMD Ryzen 3 | 4C / 8T | 8 GB | 3.11.9 |
| **N7** | Worker-7 | `192.168.1.17` | 9000 | Windows 10 | Intel Core i5 | 4C / 8T | 8 GB | 3.11.9 |
| **N8** | Worker-8 | `192.168.1.18` | 9000 | Linux Mint / Fedora | AMD Ryzen 7 | 8C / 16T | 16 GB | 3.11.9 |
| **N9** | Worker-9 | `192.168.1.19` | 9000 | Windows 11 | Intel Core i5 | 6C / 12T | 8 GB | 3.11.9 |

> [!NOTE]
> Perbedaan sistem operasi (Windows dan Linux) serta variasi jumlah core CPU dimanfaatkan secara sengaja untuk menguji keunggulan **Dynamic Load Balancing (Pull-based)** terhadap **Static Load Balancing** pada Skenario D.

---

## 3. Alokasi Port dan Firewall

* **TCP 8000:** Master FastAPI REST API & SSE (`/cluster/stream`). Wajib dibuka pada Node N0.
* **TCP 3000:** Web Dashboard Next.js. Wajib dibuka pada Node N0.
* **TCP 5432:** PostgreSQL Server. Wajib menerima koneksi lokal/LAN dari Node N0.
* **TCP 9000:** Worker Admin Endpoint (`/admin/kill`, `/admin/hang`, `/admin/mute`). Wajib dibuka pada semua Node N1 s/d N9.
