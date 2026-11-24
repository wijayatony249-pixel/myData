"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from "recharts";

interface WorkerData {
  id: string;
  hostname: string;
  ip: string;
  os: string;
  cpu_model: string;
  cores: number;
  ram_mb: number;
  status: "ACTIVE" | "BUSY" | "DOWN";
  cpu_pct?: number;
  mem_pct?: number;
  active_task_id?: number | null;
}

export default function DashboardClusterPage() {
  const [workers, setWorkers] = useState<WorkerData[]>([]);
  const [metricsHistory, setMetricsHistory] = useState<any[]>([]);
  const [activeJob, setActiveJob] = useState<any>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  // Ambil daftar awal Worker
  const fetchWorkers = async () => {
    try {
      const res = await fetch("/api/master/workers");
      if (res.ok) {
        const data = await res.json();
        setWorkers(data);
      }
    } catch (e) {
      console.error("Gagal mengambil data worker", e);
    }
  };

  const handleDeleteWorker = async (workerId: string) => {
    if (!confirm(`Hapus ${workerId} dari daftar klaster?`)) return;
    try {
      await fetch(`/api/master/workers/${workerId}`, { method: "DELETE" });
      fetchWorkers();
    } catch (e) {
      console.error(e);
    }
  };

  const handleClearDownWorkers = async () => {
    if (!confirm("Bersihkan seluruh worker yang sedang DOWN?")) return;
    try {
      await fetch("/api/master/workers?status=DOWN", { method: "DELETE" });
      fetchWorkers();
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 4000);

    // Hubungkan ke SSE stream
    const eventSource = new EventSource("/api/master/cluster/stream");

    eventSource.onopen = () => setIsConnected(true);
    eventSource.onerror = () => setIsConnected(false);

    eventSource.addEventListener("heartbeat", (event: any) => {
      const data = JSON.parse(event.data);
      setWorkers((prev) =>
        prev.map((w) =>
          w.id === data.worker_id
            ? { ...w, cpu_pct: data.cpu_pct, mem_pct: data.mem_pct, active_task_id: data.active_task_id, status: "ACTIVE" }
            : w
        )
      );

      // Simpan riwayat grafik metrik
      setMetricsHistory((prev) => {
        const now = new Date().toLocaleTimeString();
        const next = [...prev, { time: now, [data.worker_id]: data.cpu_pct }];
        return next.slice(-20); // Batasi 20 titik waktu terakhir
      });
    });

    return () => {
      clearInterval(interval);
      eventSource.close();
    };
  }, []);

  const totalWorkers = workers.length;
  const activeWorkers = workers.filter((w) => w.status === "ACTIVE").length;
  const downWorkers = workers.filter((w) => w.status === "DOWN").length;

  return (
    <div className="dashboard-page">
      <div className="d-flex justify-content-between align-items-center mb-4 dashboard-heading">
        <div>
          <div className="eyebrow mb-2"><span className="live-dot" /> PUSAT KENDALI · CLUSTER MYDATA</div>
          <h2 className="fw-bold mb-1">
            <i className="ri-dashboard-3-line text-primary me-2"></i>
            Dashboard Pemantauan Klaster
          </h2>
          <p className="text-muted mb-0">
            Arsitektur Master–Worker 10 Node Fisik (1 Master + 9 Worker)
          </p>
        </div>
        <div className="d-flex align-items-center gap-2">
          <span className={`connection-pill ${isConnected ? "connected" : "disconnected"}`}>
            <i className={`ri-radio-button-line me-1 ${isConnected ? "text-white" : ""}`}></i>
            {isConnected ? "SSE Real-Time Terhubung" : "Koneksi Terputus"}
          </span>
          <Link href="/buat-job" className="btn btn-primary">
            <i className="ri-add-line me-1"></i> Buat Job Baru
          </Link>
        </div>
      </div>

      {/* Ringkasan Statistik Kartu */}
      <div className="row g-3 mb-4">
        <div className="col-md-3">
          <div className="card stat-card stat-violet">
            <div className="card-body">
              <span className="text-muted small fw-bold">TOTAL NODE WORKER</span>
              <h3 className="fw-bold mb-0 mt-1">{totalWorkers} / 9</h3>
              <small className="text-muted">Target kapasitas 9 Worker</small>
            </div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card stat-card stat-green">
            <div className="card-body">
              <span className="text-muted small fw-bold">WORKER AKTIF</span>
              <h3 className="fw-bold text-success mb-0 mt-1">{activeWorkers}</h3>
              <small className="text-success">Siap menerima penugasan komputasi</small>
            </div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card stat-card stat-orange">
            <div className="card-body">
              <span className="text-muted small fw-bold">WORKER DOWN / MACET</span>
              <h3 className="fw-bold text-danger mb-0 mt-1">{downWorkers}</h3>
              <small className="text-muted">Timeout heartbeat &gt; 6 detik</small>
            </div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card stat-card stat-blue">
            <div className="card-body">
              <span className="text-muted small fw-bold">MODE LOAD BALANCING</span>
              <h3 className="fw-bold text-info mb-0 mt-1">Dinamis</h3>
              <small className="text-muted">Pull-based adaptif (Default)</small>
            </div>
          </div>
        </div>
      </div>

      {/* Grafik Beban CPU Real-Time */}
      <div className="card panel-card mb-4">
        <div className="card-header py-3 d-flex justify-content-between align-items-center">
          <h5 className="fw-bold mb-0">
            <i className="ri-pulse-line text-danger me-2"></i>
            Beban CPU Real-Time Tiap Node Worker (%)
          </h5>
          <span className="badge bg-light text-dark border">Update Tiap 2 Detik</span>
        </div>
        <div className="card-body chart-body" style={{ height: 260 }}>
          {metricsHistory.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metricsHistory}>
                <XAxis dataKey="time" stroke="#888" fontSize={11} />
                <YAxis domain={[0, 100]} stroke="#888" fontSize={11} />
                <Tooltip />
                <Legend />
                {workers.map((w, idx) => (
                  <Line
                    key={w.id}
                    type="monotone"
                    dataKey={w.id}
                    stroke={`hsl(${(idx * 360) / 9}, 70%, 45%)`}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-100 d-flex align-items-center justify-content-center text-muted">
              Menunggu transmisi denyut heartbeat dari Worker...
            </div>
          )}
        </div>
      </div>

      {/* Daftar Kartu Node Worker */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="fw-bold mb-0 section-heading">
          <i className="ri-server-line text-primary me-2"></i>
          Status Node Worker Klaster
        </h5>
        {downWorkers > 0 && (
          <button
            className="btn btn-sm btn-outline-danger"
            onClick={handleClearDownWorkers}
          >
            <i className="ri-delete-bin-line me-1"></i> Bersihkan Worker DOWN ({downWorkers})
          </button>
        )}
      </div>
      <div className="row g-3">
        {workers.map((w) => {
          const isDown = w.status === "DOWN";
          return (
            <div className="col-md-4" key={w.id}>
              <div className={`card worker-card h-100 ${isDown ? "worker-down" : ""}`}>
                <div className="card-header d-flex justify-content-between align-items-center">
                  <span className="fw-bold text-uppercase">{w.id}</span>
                  <div className="d-flex align-items-center gap-2">
                    <span className={`worker-status ${isDown ? "down" : "up"}`}>
                      {isDown ? "DOWN" : "AKTIF"}
                    </span>
                    {isDown && (
                      <button
                        className="btn btn-sm btn-outline-danger py-0 px-2"
                        style={{ fontSize: 11 }}
                        title="Hapus Worker dari daftar"
                        onClick={() => handleDeleteWorker(w.id)}
                      >
                        <i className="ri-delete-bin-line"></i>
                      </button>
                    )}
                  </div>
                </div>
                <div className="card-body">
                  <div className="small text-muted mb-2">
                    <i className="ri-computer-line me-1"></i> {w.hostname} ({w.ip})
                  </div>
                  <div className="small text-muted mb-3">
                    <i className="ri-window-line me-1"></i> {w.os} | Python {w.python_version}
                  </div>
                  
                  <div className="row text-center mb-3 g-2">
                    <div className="col-6">
                      <div className="p-2 border rounded bg-light">
                        <small className="text-muted d-block">Core CPU</small>
                        <span className="fw-bold">{w.cores} Cores</span>
                      </div>
                    </div>
                    <div className="col-6">
                      <div className="p-2 border rounded bg-light">
                        <small className="text-muted d-block">RAM Fisik</small>
                        <span className="fw-bold">{Math.round(w.ram_mb / 1024)} GB</span>
                      </div>
                    </div>
                  </div>

                  {/* Utilisasi CPU & RAM */}
                  <div className="mb-2">
                    <div className="d-flex justify-content-between small mb-1">
                      <span>Utilisasi CPU</span>
                      <span className="fw-bold">{w.cpu_pct ?? 0}%</span>
                    </div>
                    <div className="progress" style={{ height: 6 }}>
                      <div
                        className={`progress-bar ${(w.cpu_pct ?? 0) > 85 ? "bg-danger" : "bg-primary"}`}
                        style={{ width: `${w.cpu_pct ?? 0}%` }}
                      ></div>
                    </div>
                  </div>

                  <div>
                    <div className="d-flex justify-content-between small mb-1">
                      <span>Memori RAM</span>
                      <span className="fw-bold">{w.mem_pct ?? 0}%</span>
                    </div>
                    <div className="progress" style={{ height: 6 }}>
                      <div
                        className="progress-bar bg-info"
                        style={{ width: `${w.mem_pct ?? 0}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="mt-3 pt-2 border-top small text-muted d-flex justify-content-between">
                    <span>Task Berjalan:</span>
                    <span className="fw-bold">{w.active_task_id ? `#${w.active_task_id}` : "Idle"}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {workers.length === 0 && (
          <div className="col-12">
            <div className="alert alert-warning py-4 text-center">
              <i className="ri-information-line fs-4 d-block mb-2"></i>
              Belum ada Worker yang terdaftar. Jalankan agen Worker pada node:
              <pre className="mt-2 bg-dark text-white p-2 rounded text-start mx-auto" style={{ maxWidth: 600 }}>
                python worker/worker.py --master http://192.168.1.10:8000 --id worker-1
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
