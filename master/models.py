"""
Model Data SQLAlchemy ORM untuk Master Database (Sesuai Bagian 10 PRD).
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, Float, Boolean,
    DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Dataset(Base):
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=True)
    total_rows_raw = Column(BigInteger, default=0)
    total_rows_clean = Column(BigInteger, default=0)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chunks = relationship("Chunk", back_populates="dataset", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"))
    row_start = Column(BigInteger, nullable=False)
    row_end = Column(BigInteger, nullable=False)
    path = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, default=0)
    checksum = Column(String(64), nullable=False)
    
    dataset = relationship("Dataset", back_populates="chunks")
    tasks = relationship("Task", back_populates="chunk")

class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(String(50), primary_key=True)
    hostname = Column(String(100), nullable=False)
    ip = Column(String(45), nullable=False)
    os = Column(String(50), nullable=False)
    python_version = Column(String(20), nullable=False)
    cpu_model = Column(String(100), nullable=False)
    cores = Column(Integer, default=1)
    ram_mb = Column(Integer, default=1024)
    status = Column(String(20), default="ACTIVE") # ACTIVE, BUSY, DOWN
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    
    tasks = relationship("Task", foreign_keys="[Task.worker_id]", back_populates="worker")
    metrics = relationship("Metric", back_populates="worker", cascade="all, delete-orphan")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False) # J1_STATS, J2_GROUPBY, J3_CORR, J4_KMEANS
    mode = Column(String(20), nullable=False) # SEQUENTIAL, LOCAL_PARALLEL, DISTRIBUTED
    lb_mode = Column(String(20), default="DYNAMIC") # DYNAMIC, STATIC
    n_workers = Column(Integer, nullable=True)
    params = Column(JSON, nullable=True)
    seed = Column(Integer, default=42)
    status = Column(String(20), default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    
    tasks = relationship("Task", back_populates="job", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"))
    chunk_id = Column(Integer, ForeignKey("chunks.id"))
    iteration = Column(Integer, default=0)
    status = Column(String(20), default="PENDING") # PENDING, ASSIGNED, RUNNING, DONE, FAILED, REQUEUED
    attempt = Column(Integer, default=1)
    worker_id = Column(String(50), ForeignKey("workers.id"), nullable=True)
    assigned_worker_id = Column(String(50), ForeignKey("workers.id"), nullable=True)
    leased_until = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)
    compute_ms = Column(Float, nullable=True)
    transfer_ms = Column(Float, nullable=True)
    cache_hit = Column(Boolean, default=False)
    result = Column(JSON, nullable=True)
    
    job = relationship("Job", back_populates="tasks")
    chunk = relationship("Chunk", back_populates="tasks")
    worker = relationship("Worker", foreign_keys=[worker_id], back_populates="tasks")

class Metric(Base):
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String(50), ForeignKey("workers.id", ondelete="CASCADE"))
    ts = Column(DateTime, default=datetime.utcnow)
    cpu_pct = Column(Float, nullable=False)
    mem_pct = Column(Float, nullable=False)
    
    worker = relationship("Worker", back_populates="metrics")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.utcnow)
    job_id = Column(Integer, nullable=True)
    task_id = Column(Integer, nullable=True)
    worker_id = Column(String(50), nullable=True)
    type = Column(String(50), nullable=False) # WORKER_DOWN, TASK_REQUEUED, dll.
    detail = Column(JSON, nullable=True)

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario = Column(String(5), nullable=False) # A, B, C, D, E, F
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    n_workers = Column(Integer, nullable=True)
    repetition = Column(Integer, default=1)
    cold_cache = Column(Boolean, default=False)
    exec_time_s = Column(Float, nullable=True)
    compute_time_s = Column(Float, nullable=True)
    transfer_time_s = Column(Float, nullable=True)
    speedup = Column(Float, nullable=True)
    efficiency = Column(Float, nullable=True)
    throughput = Column(Float, nullable=True)
    recovery_time_s = Column(Float, nullable=True)
