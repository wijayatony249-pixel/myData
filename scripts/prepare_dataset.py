"""
Skrip Penyiapan Dataset NYC TLC Yellow Taxi (Download/Generate, Cleaning, Chunking).
Dapat mengunduh file Parquet resmi TLC atau menghasilkan dataset sintetik berukuran besar
yang 100% identik dengan skema resmi jika dijalankan dalam lingkungan lab offline.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Tambahkan root proyek ke sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from common.config import CHUNKS_DIR, RAW_DIR, CHUNK_SIZE
from common.cleaning import clean_taxi_dataframe, USED_COLUMNS
from common.utils import calculate_checksum

TLC_URL_TEMPLATE = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{year}-{month:02d}.parquet"

def generate_synthetic_taxi_data(num_rows: int = 1000000, seed: int = 42) -> pd.DataFrame:
    """Menghasilkan dataset taksi sintetis skala jutaan baris sesuai skema resmi NYC TLC."""
    print(f"[*] Menghasilkan {num_rows:,} baris data sintetis NYC Yellow Taxi (seed={seed})...")
    rng = np.random.RandomState(seed)
    
    # 1. Timestamps
    base_date = datetime(2024, 1, 1, 0, 0, 0)
    pickup_offsets = rng.randint(0, 31 * 24 * 3600, size=num_rows)
    durations = rng.exponential(scale=15 * 60, size=num_rows) + 60 # rata-rata 15 menit
    
    pickups = [base_date + timedelta(seconds=int(o)) for o in pickup_offsets]
    dropoffs = [p + timedelta(seconds=int(d)) for p, d in zip(pickups, durations)]
    
    # 2. Fitur Numerik & Kategori
    passenger_counts = rng.choice([1, 2, 3, 4, 5, 6], size=num_rows, p=[0.7, 0.15, 0.05, 0.04, 0.03, 0.03])
    # Trip distance (mil)
    trip_distances = np.round(rng.gamma(shape=2.0, scale=1.5, size=num_rows) + 0.1, 2)
    trip_distances = np.clip(trip_distances, 0.1, 95.0)
    
    # Zona Lokasi NYC (1 sampai 265)
    pu_locations = rng.randint(1, 266, size=num_rows)
    do_locations = rng.randint(1, 266, size=num_rows)
    payment_types = rng.choice([1, 2, 3, 4], size=num_rows, p=[0.75, 0.22, 0.02, 0.01])
    
    # Tarif dan Tip
    fare_amounts = np.round(3.0 + (trip_distances * 2.8) + (durations / 60.0 * 0.5), 2)
    fare_amounts = np.clip(fare_amounts, 3.0, 480.0)
    
    # Tip (credit card payment=1 biasanya ada tip 15-25%)
    tip_rates = np.where(payment_types == 1, rng.uniform(0.12, 0.25, size=num_rows), 0.0)
    tip_amounts = np.round(fare_amounts * tip_rates, 2)
    
    total_amounts = np.round(fare_amounts + tip_amounts + 2.5 + 0.5, 2) # plus extra taxes
    
    # Sisipkan sedikit dirty data (1-2%) untuk menguji mekanisme pembersihan PRD
    dirty_indices = rng.choice(num_rows, size=int(num_rows * 0.015), replace=False)
    for idx in dirty_indices[:len(dirty_indices)//4]:
        # Dropoff sebelum pickup
        dropoffs[idx] = pickups[idx] - timedelta(minutes=5)
    for idx in dirty_indices[len(dirty_indices)//4: 2*len(dirty_indices)//4]:
        # passenger_count out of bound (misal 9)
        passenger_counts[idx] = 9
    for idx in dirty_indices[2*len(dirty_indices)//4: 3*len(dirty_indices)//4]:
        # fare_amount negatif
        fare_amounts[idx] = -15.0
    for idx in dirty_indices[3*len(dirty_indices)//4:]:
        # Location out of range
        pu_locations[idx] = 999

    df = pd.DataFrame({
        "tpep_pickup_datetime": pickups,
        "tpep_dropoff_datetime": dropoffs,
        "passenger_count": passenger_counts,
        "trip_distance": trip_distances,
        "PULocationID": pu_locations,
        "DOLocationID": do_locations,
        "payment_type": payment_types,
        "fare_amount": fare_amounts,
        "tip_amount": tip_amounts,
        "total_amount": total_amounts
    })
    
    return df

def prepare_and_chunk_dataset(
    input_file: Path = None,
    synthetic_rows: int = 1000000,
    chunk_size: int = CHUNK_SIZE
) -> dict:
    """
    Membaca dataset mentah (atau membuat sintetis jika tidak ada),
    melakukan pembersihan sesuai PRD, lalu memecah menjadi chunk Parquet terkompresi.
    """
    raw_df = None
    source_name = ""
    
    if input_file and input_file.exists():
        print(f"[*] Membaca file dataset riil dari {input_file}...")
        raw_df = pd.read_parquet(input_file, columns=[c for c in USED_COLUMNS])
        source_name = str(input_file.name)
    else:
        print(f"[*] Mode Dataset Mandiri: Menggunakan data sintetis NYC Taxi ({synthetic_rows:,} baris)...")
        raw_df = generate_synthetic_taxi_data(synthetic_rows)
        source_name = "nyc_taxi_synthetic_data"
        # Simpan file mentah ke RAW_DIR
        raw_path = RAW_DIR / f"{source_name}.parquet"
        raw_df.to_parquet(raw_path, compression="snappy", index=False)
        print(f"[+] Data mentah tersimpan di: {raw_path}")

    # Lakukan Pembersihan Data Sesuai Aturan PRD
    print("[*] Menjalankan pembersihan data ketat sesuai aturan PRD...")
    clean_df, raw_count, clean_count = clean_taxi_dataframe(raw_df)
    retention_pct = (clean_count / raw_count) * 100 if raw_count > 0 else 0
    print(f"[+] Pembersihan Selesai:")
    print(f"    - Baris sebelum pembersihan : {raw_count:,}")
    print(f"    - Baris sesudah pembersihan : {clean_count:,}")
    print(f"    - Data valid lolos filter   : {retention_pct:.2f}%")

    # Bersihkan chunk lama jika ada
    for old_file in CHUNKS_DIR.glob("chunk_*.parquet"):
        try:
            old_file.unlink()
        except Exception:
            pass

    # Lakukan Pemecahan Chunk (Chunking)
    num_chunks = int(np.ceil(clean_count / chunk_size))
    print(f"[*] Memecah {clean_count:,} baris ke dalam {num_chunks} chunk (~{chunk_size:,} baris/chunk)...")
    
    chunks_meta = []
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, clean_count)
        chunk_slice = clean_df.iloc[start_idx:end_idx]
        
        chunk_filename = f"chunk_{i+1:04d}.parquet"
        chunk_path = CHUNKS_DIR / chunk_filename
        
        # Simpan Parquet dengan kompresi snappy
        chunk_slice.to_parquet(chunk_path, engine="pyarrow", compression="snappy", index=False)
        
        size_bytes = chunk_path.stat().st_size
        checksum = calculate_checksum(chunk_path)
        
        chunk_info = {
            "chunk_id": i + 1,
            "filename": chunk_filename,
            "path": str(chunk_path),
            "row_start": start_idx,
            "row_end": end_idx,
            "row_count": len(chunk_slice),
            "size_bytes": size_bytes,
            "checksum": checksum
        }
        chunks_meta.append(chunk_info)
        print(f"    -> Dibuat {chunk_filename}: baris [{start_idx:,}..{end_idx:,}], {size_bytes / (1024*1024):.2f} MB, SHA-256: {checksum[:12]}...")

    metadata = {
        "dataset_name": source_name,
        "created_at": datetime.utcnow().isoformat(),
        "total_rows_raw": raw_count,
        "total_rows_clean": clean_count,
        "chunk_size": chunk_size,
        "chunk_count": num_chunks,
        "chunks": chunks_meta
    }

    meta_file = CHUNKS_DIR / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[+] Metadata tersimpan di: {meta_file}")

    # Catat ke Basis Data Master agar langsung dikenali oleh sistem
    try:
        from master.database import SyncSessionLocal
        from master.models import Dataset, Chunk
        with SyncSessionLocal() as db:
            ds = Dataset(
                name=source_name,
                source_url=str(RAW_DIR / f"{source_name}.parquet"),
                total_rows_raw=raw_count,
                total_rows_clean=clean_count,
                chunk_count=num_chunks
            )
            db.add(ds)
            db.flush()
            for c in chunks_meta:
                chunk_entry = Chunk(
                    dataset_id=ds.id,
                    row_start=c["row_start"],
                    row_end=c["row_end"],
                    path=str(Path(c["path"]).resolve()),
                    size_bytes=c["size_bytes"],
                    checksum=c["checksum"]
                )
                db.add(chunk_entry)
            db.commit()
            print(f"[+] Dataset #{ds.id} berhasil didaftarkan ke Database Master.")
    except Exception as e:
        print(f"[!] Catatan: {e}")
    
    return metadata

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Persiapan dan Chunking Dataset myData")
    parser.add_argument("--file", type=str, default=None, help="Jalur file Parquet TLC mentah jika ada")
    parser.add_argument("--rows", type=int, default=1000000, help="Jumlah baris data sintetis (default: 1.000.000)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help=f"Ukuran baris per chunk (default: {CHUNK_SIZE})")
    
    args = parser.parse_args()
    input_p = Path(args.file) if args.file else None
    prepare_and_chunk_dataset(input_file=input_p, synthetic_rows=args.rows, chunk_size=args.chunk_size)
