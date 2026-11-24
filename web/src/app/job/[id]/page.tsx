"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

export default function DetailJobPage() {
  const { id } = useParams();
  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchJob = async () => {
    try {
      const res = await fetch(`/api/master/jobs/${id}`);
      if (res.ok) {
        const data = await res.json();
        setJob(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJob();
    const interval = setInterval(fetchJob, 1500); // Polling progres job
    return () => clearInterval(interval);
  }, [id]);

  const handleCancel = async () => {
    if (!confirm("Batalkan job ini?")) return;
    try {
      await fetch(`/api/master/jobs/${id}/cancel`, { method: "POST" });
      fetchJob();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading && !job) {
    return <div className="text-center py-5">Memuat data job #{id}...</div>;
  }

  if (!job) {
    return (
      <div className="alert alert-danger">
        Job #{id} tidak ditemukan. <Link href="/">Kembali ke Dashboard</Link>
      </div>
    );
  }

  const isFinished = job.status === "COMPLETED" || job.status === "CANCELLED" || job.status === "FAILED";

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <div className="d-flex align-items-center gap-2 mb-1">
            <h2 className="fw-bold mb-0">Detail Job #{job.id}</h2>
            <span className={`badge fs-6 ${
              job.status === "COMPLETED" ? "bg-success" :
              job.status === "RUNNING" ? "bg-primary" :
              job.status === "CANCELLED" ? "bg-secondary" : "bg-warning text-dark"
            }`}>
              {job.status}
            </span>
          </div>
          <p className="text-muted mb-0">
            Jenis: <strong className="text-primary">{job.type}</strong> | Mode: <strong>{job.mode}</strong> | Load Balancing: <strong>{job.lb_mode}</strong>
          </p>
        </div>
        <div>
          {!isFinished && (
            <button className="btn btn-outline-danger" onClick={handleCancel}>
              <i className="ri-stop-circle-line me-1"></i> Batalkan Job
            </button>
          )}
          <Link href="/" className="btn btn-outline-secondary ms-2">
            Kembali
          </Link>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="card shadow-sm border-0 mb-4">
        <div className="card-body">
          <div className="d-flex justify-content-between mb-2">
            <span className="fw-bold">
              Kemajuan Komputasi ({job.done_tasks} / {job.total_tasks} Task Selesai)
            </span>
            <span className="fw-bold text-primary">{job.progress_pct}%</span>
          </div>
          <div className="progress" style={{ height: 16 }}>
            <div
              className={`progress-bar progress-bar-striped ${job.status === "RUNNING" ? "progress-bar-animated" : ""} bg-primary`}
              style={{ width: `${job.progress_pct}%` }}
            ></div>
          </div>
          <div className="d-flex justify-content-between small text-muted mt-2">
            <span>Dimulai: {job.started_at || "-"}</span>
            <span>Durasi: {job.duration_s ? `${job.duration_s.toFixed(2)} detik` : "Berjalan..."}</span>
          </div>
        </div>
      </div>

      {/* Hasil Akhir Komputasi jika Selesai */}
      {job.result && (
        <div className="card shadow-sm border-0 mb-4 border-start border-success border-4">
          <div className="card-header bg-white py-3">
            <h5 className="fw-bold mb-0 text-success">
              <i className="ri-checkbox-circle-line me-2"></i>
              Hasil Akhir Komputasi Terdistribusi
            </h5>
          </div>
          <div className="card-body">
            {job.type === "J4_KMEANS" && (
              <div>
                <div className="row g-2 mb-3">
                  <div className="col-md-4">
                    <div className="p-2 border rounded bg-light">
                      <small className="text-muted d-block">Jumlah Iterasi Konvergensi</small>
                      <strong className="fs-5">{job.result.iterations} Iterasi</strong>
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className="p-2 border rounded bg-light">
                      <small className="text-muted d-block">Pergeseran Centroid Akhir</small>
                      <strong className="fs-5">{job.result.final_shift?.toExponential(4)}</strong>
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className="p-2 border rounded bg-light">
                      <small className="text-muted d-block">Kriteria Konvergensi</small>
                      <strong className="fs-5 text-success">&lt; 1e-4 (Konvergen)</strong>
                    </div>
                  </div>
                </div>

                <h6 className="fw-bold mb-2">Koordinat Centroid Akhir (Z-Score):</h6>
                <div className="table-responsive">
                  <table className="table table-sm table-bordered">
                    <thead className="table-light">
                      <tr>
                        <th>Cluster</th>
                        <th>Trip Distance</th>
                        <th>Fare Amount</th>
                        <th>Tip Amount</th>
                        <th>Trip Duration</th>
                        <th>Jumlah Titik Data</th>
                      </tr>
                    </thead>
                    <tbody>
                      {job.result.centroids?.map((c: number[], idx: number) => (
                        <tr key={idx}>
                          <td className="fw-bold">Cluster #{idx + 1}</td>
                          <td>{c[0]?.toFixed(4)}</td>
                          <td>{c[1]?.toFixed(4)}</td>
                          <td>{c[2]?.toFixed(4)}</td>
                          <td>{c[3]?.toFixed(4)}</td>
                          <td className="fw-bold text-primary">
                            {job.result.cluster_counts?.[idx]?.toLocaleString() || 0}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {job.type === "J1_STATS" && (
              <div className="table-responsive">
                <table className="table table-sm table-bordered">
                  <thead className="table-light">
                    <tr>
                      <th>Kolom Fitur</th>
                      <th>Count</th>
                      <th>Mean</th>
                      <th>Std Dev</th>
                      <th>Min</th>
                      <th>Max</th>
                      <th>Sum</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(job.result).map(([col, stats]: [string, any]) => (
                      <tr key={col}>
                        <td className="fw-bold">{col}</td>
                        <td>{stats.count?.toLocaleString()}</td>
                        <td>{stats.mean?.toFixed(4)}</td>
                        <td>{stats.std?.toFixed(4)}</td>
                        <td>{stats.min?.toFixed(2)}</td>
                        <td>{stats.max?.toFixed(2)}</td>
                        <td>{stats.sum?.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tabel Rincian Task Per Chunk */}
      <div className="card shadow-sm border-0 mb-4">
        <div className="card-header bg-white py-3">
          <h5 className="fw-bold mb-0">Rincian Task Komputasi per Chunk</h5>
        </div>
        <div className="card-body p-0">
          <div className="table-responsive">
            <table className="table table-hover table-striped mb-0 align-middle">
              <thead className="table-light">
                <tr>
                  <th>Task ID</th>
                  <th>Chunk</th>
                  <th>Iterasi</th>
                  <th>Status</th>
                  <th>Attempt</th>
                  <th>Worker</th>
                  <th>Waktu Transfer</th>
                  <th>Waktu Komputasi</th>
                  <th>Cache Hit</th>
                </tr>
              </thead>
              <tbody>
                {job.tasks?.map((t: any) => (
                  <tr key={t.id}>
                    <td className="fw-bold">#{t.id}</td>
                    <td>Chunk #{t.chunk_id}</td>
                    <td>{t.iteration}</td>
                    <td>
                      <span className={`badge ${
                        t.status === "DONE" ? "bg-success" :
                        t.status === "RUNNING" ? "bg-primary" :
                        t.status === "REQUEUED" ? "bg-warning text-dark" : "bg-secondary"
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td>{t.attempt}</td>
                    <td>
                      <span className="badge bg-light text-dark border">
                        {t.worker_id || "-"}
                      </span>
                    </td>
                    <td>{t.transfer_ms ? `${t.transfer_ms.toFixed(1)} ms` : "-"}</td>
                    <td>{t.compute_ms ? `${t.compute_ms.toFixed(1)} ms` : "-"}</td>
                    <td>
                      {t.cache_hit ? (
                        <span className="text-success"><i className="ri-check-line"></i> Ya</span>
                      ) : (
                        <span className="text-muted">Tidak</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
