"""
Aturan dan Pembersihan Dataset NYC TLC Yellow Taxi.
Aturan ini identik dan diterapkan konsisten di semua node dan mode eksekusi.
"""

from typing import Tuple, Optional
import pandas as pd
import numpy as np

USED_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "total_amount"
]

NUMERIC_COLUMNS = [
    "passenger_count",
    "trip_distance",
    "fare_amount",
    "tip_amount",
    "total_amount"
]

def clean_taxi_dataframe(
    df: pd.DataFrame,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None
) -> Tuple[pd.DataFrame, int, int]:
    """
    Membersihkan DataFrame sesuai aturan spesifikasi PRD myData:
    1. Hanya membaca dan memproses 10 kolom target.
    2. Waktu jemput dan antar tidak kosong, waktu antar > waktu jemput.
    3. Rentang tanggal jemput valid jika min_date / max_date ditentukan.
    4. passenger_count bernilai 1 s/d 6.
    5. trip_distance > 0 dan <= 100 mil.
    6. fare_amount > 0 dan <= 500.
    7. tip_amount >= 0 (tidak negatif).
    8. total_amount > 0.
    9. PULocationID dan DOLocationID bernilai 1 s/d 265.
    
    Mengembalikan: (df_bersih, jumlah_baris_mentah, jumlah_baris_bersih)
    """
    raw_count = len(df)
    
    # Ambil hanya kolom yang digunakan jika kolom tersebut ada
    cols_to_use = [c for c in USED_COLUMNS if c in df.columns]
    df = df[cols_to_use].copy()
    
    # Pastikan tipe data datetime
    if "tpep_pickup_datetime" in df.columns:
        df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"], errors="coerce")
    if "tpep_dropoff_datetime" in df.columns:
        df["tpep_dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"], errors="coerce")
        
    # Filter 1: Waktu jemput & antar tidak kosong dan antar > jemput
    valid_mask = (
        df["tpep_pickup_datetime"].notna() &
        df["tpep_dropoff_datetime"].notna() &
        (df["tpep_dropoff_datetime"] > df["tpep_pickup_datetime"])
    )
    
    # Filter rentang tanggal opsional
    if min_date is not None:
        valid_mask &= (df["tpep_pickup_datetime"] >= pd.to_datetime(min_date))
    if max_date is not None:
        valid_mask &= (df["tpep_pickup_datetime"] <= pd.to_datetime(max_date))
        
    # Normalisasi tipe numerik
    df["passenger_count"] = pd.to_numeric(df["passenger_count"], errors="coerce").fillna(0).astype(int)
    df["trip_distance"] = pd.to_numeric(df["trip_distance"], errors="coerce").fillna(0.0).astype(float)
    df["PULocationID"] = pd.to_numeric(df["PULocationID"], errors="coerce").fillna(0).astype(int)
    df["DOLocationID"] = pd.to_numeric(df["DOLocationID"], errors="coerce").fillna(0).astype(int)
    df["payment_type"] = pd.to_numeric(df["payment_type"], errors="coerce").fillna(0).astype(int)
    df["fare_amount"] = pd.to_numeric(df["fare_amount"], errors="coerce").fillna(0.0).astype(float)
    df["tip_amount"] = pd.to_numeric(df["tip_amount"], errors="coerce").fillna(0.0).astype(float)
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0.0).astype(float)
    
    # Filter 2: Aturan batasan nilai PRD
    rule_mask = (
        (df["passenger_count"] >= 1) & (df["passenger_count"] <= 6) &
        (df["trip_distance"] > 0.0) & (df["trip_distance"] <= 100.0) &
        (df["fare_amount"] > 0.0) & (df["fare_amount"] <= 500.0) &
        (df["tip_amount"] >= 0.0) &
        (df["total_amount"] > 0.0) &
        (df["PULocationID"] >= 1) & (df["PULocationID"] <= 265) &
        (df["DOLocationID"] >= 1) & (df["DOLocationID"] <= 265)
    )
    
    df_clean = df[valid_mask & rule_mask].copy().reset_index(drop=True)
    clean_count = len(df_clean)
    
    return df_clean, raw_count, clean_count
