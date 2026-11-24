"""
Pydantic Schemas untuk Kontrak Data Komunikasi Master - Worker - Web.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

class JobType(str, Enum):
    J1_STATS = "J1_STATS"
    J2_GROUPBY = "J2_GROUPBY"
    J3_CORR = "J3_CORR"
    J4_KMEANS = "J4_KMEANS"

class JobMode(str, Enum):
    SEQUENTIAL = "SEQUENTIAL"
    LOCAL_PARALLEL = "LOCAL_PARALLEL"
    DISTRIBUTED = "DISTRIBUTED"

class LBMode(str, Enum):
    DYNAMIC = "DYNAMIC"
    STATIC = "STATIC"

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    REQUEUED = "REQUEUED"

class WorkerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BUSY = "BUSY"
    DOWN = "DOWN"

# --- Skema Registrasi & Heartbeat Worker ---
class WorkerRegisterRequest(BaseModel):
    id: str
    hostname: str
    ip: str
    os: str
    python_version: str
    cpu_model: str
    cores: int
    ram_mb: int

class WorkerRegisterResponse(BaseModel):
    status: str
    message: str
    cluster_token_valid: bool

class WorkerHeartbeatRequest(BaseModel):
    worker_id: str
    cpu_pct: float
    mem_pct: float
    active_task_id: Optional[int] = None

class WorkerHeartbeatResponse(BaseModel):
    acknowledged: bool
    lease_extended: bool = False
    server_time: datetime = Field(default_factory=datetime.utcnow)

# --- Skema Dispatch & Result Task ---
class TaskDispatchRequest(BaseModel):
    worker_id: str

class TaskDispatchResponse(BaseModel):
    has_task: bool
    task_id: Optional[int] = None
    job_id: Optional[int] = None
    job_type: Optional[JobType] = None
    chunk_id: Optional[int] = None
    chunk_download_url: Optional[str] = None
    checksum: Optional[str] = None
    iteration: int = 0
    attempt: int = 1
    params: Optional[Dict[str, Any]] = None
    lease_seconds: float = 30.0

class TaskResultSubmit(BaseModel):
    task_id: int
    job_id: int
    attempt: int
    worker_id: str
    iteration: int = 0
    compute_ms: float
    transfer_ms: float
    cache_hit: bool
    partial_result: Dict[str, Any]

# --- Skema Dataset ---
class DatasetPrepareRequest(BaseModel):
    name: str = "NYC Taxi Yellow"
    source_url: Optional[str] = None
    chunk_size: int = 200000

class DatasetInfo(BaseModel):
    id: int
    name: str
    source_url: Optional[str]
    total_rows_raw: int
    total_rows_clean: int
    chunk_count: int
    created_at: datetime

# --- Skema Job & Benchmark ---
class JobCreateRequest(BaseModel):
    type: JobType
    mode: JobMode = JobMode.DISTRIBUTED
    lb_mode: LBMode = LBMode.DYNAMIC
    dataset_id: Optional[int] = None
    n_workers: Optional[int] = None
    params: Optional[Dict[str, Any]] = None
    seed: int = 42

class TaskInfo(BaseModel):
    id: int
    chunk_id: int
    iteration: int
    status: TaskStatus
    attempt: int
    worker_id: Optional[str]
    duration_ms: Optional[float]
    compute_ms: Optional[float]
    transfer_ms: Optional[float]
    cache_hit: Optional[bool]

class JobResponse(BaseModel):
    id: int
    type: JobType
    mode: JobMode
    lb_mode: LBMode
    n_workers: Optional[int]
    status: str
    seed: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_s: Optional[float]
    result: Optional[Dict[str, Any]] = None
    tasks: Optional[List[TaskInfo]] = None

class BenchmarkRunRequest(BaseModel):
    scenario: str # A, B, C, D, E, F
    job_type: JobType = JobType.J4_KMEANS
    repetitions: int = 3
    n_workers: Optional[int] = None
    cold_cache: bool = False
