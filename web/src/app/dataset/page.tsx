"use client";

import { useEffect, useState } from "react";

export default function DatasetPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const [formRows, setFormRows] = useState(1000000);
  const [formChunkSize, setFormChunkSize] = useState(200000);

  const fetchDatasets = async () => {
    try {
      const res = await fetch("/api/master/datasets");
      if (res.ok) {
        const data = await res.json();
        setDatasets(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handlePrepareDataset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/master/datasets/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "NYC Yellow Taxi",
          chunk_size: Number(formChunkSize)
        }),
      });
      const data = await res.json();
      setMessage(data.message || "Proses penyiapan dataset dimulai.");
      setTimeout(fetchDatasets, 4000);
    } catch (err: any) {
      setMessage("Gagal menyiapkan dataset: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="fw-bold mb-1">
            <i className="ri-database-2-line text-primary me-2"></i>
            Pengelolaan Dataset & Chunking
          </h2>
          <p className="text-muted mb-0">
            Pembersihan Data Ketat & Pemecahan ke Format Parquet Terkompresi (Snappy)
          </p>
        </div>
      </div>

      {message && (
        <div className="alert alert-info alert-dismissible fade show">
          <i className="ri-information-line me-2"></i> {message}
          <button type="button" className="btn-close" onClick={() => setMessage("")}></button>
        </div>
      )}

      {/* Form Penyiapan Dataset */}
      <div className="card shadow-sm border-0 mb-4">
        <div className="card-header bg-white py-3">
          <h5 className="fw-bold mb-0">
            <i className="ri-play-list-add-line text-success me-2"></i>
            Siapkan Dataset Baru
          </h5>
        </div>
        <div className="card-body">
          <form onSubmit={handlePrepareDataset} className="row g-3">
            <div className="col-md-5">
              <label className="form-label fw-bold">Skala Baris Data Sintetis</label>
              <select
                className="form-select"
                value={formRows}
                onChange={(e) => setFormRows(Number(e.target.value))}
              >
                <option value={500000}>500.000 Baris (Pengujian Cepat)</option>
                <option value={1000000}>1.000.000 Baris (Standar Uji Mandiri)</option>
                <option value={5000000}>5.000.000 Baris (Uji Skala Besar)</option>
                <option value={10000000}>10.000.000 Baris (Target Penuh UAS)</option>
              </select>
            </div>
            <div className="col-md-4">
              <label className="form-label fw-bold">Ukuran per Chunk (Baris)</label>
              <select
                className="form-select"
                value={formChunkSize}
                onChange={(e) => setFormChunkSize(Number(e.target.value))}
              >
                <option value={100000}>100.000 baris / chunk</option>
                <option value={200000}>200.000 baris / chunk (Disarankan)</option>
                <option value={500000}>500.000 baris / chunk</option>
              </select>
            </div>
            <div className="col-md-3 d-flex align-items-end">
              <button
                type="submit"
                className="btn btn-primary w-100 py-2 fw-bold"
                disabled={loading}
              >
                <i className="ri-settings-4-line me-1"></i>
                {loading ? "Memproses..." : "Siapkan Dataset"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Ringkasan Dataset Aktif */}
      {datasets.map((ds) => {
        const raw = ds.total_rows_raw || 0;
        const clean = ds.total_rows_clean || 0;
        const pct = raw > 0 ? ((clean / raw) * 100).toFixed(2) : 0;

        return (
          <div className="card shadow-sm border-0 mb-4" key={ds.id}>
            <div className="card-header bg-white py-3 d-flex justify-content-between align-items-center">
              <div>
                <h5 className="fw-bold mb-0 text-primary">{ds.name}</h5>
                <small className="text-muted">Sumber: {ds.source_url} | Dibuat: {ds.created_at}</small>
              </div>
              <span className="badge bg-success fs-6">
                {ds.chunk_count} Chunk Parquet
              </span>
            </div>
            <div className="card-body">
              <div className="row text-center g-3 mb-4">
                <div className="col-md-4">
                  <div className="p-3 border rounded bg-light">
                    <span className="text-muted d-block small">BARIS SEBELUM BERSIH</span>
                    <h4 className="fw-bold text-secondary mb-0">{raw.toLocaleString()}</h4>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="p-3 border rounded bg-light">
                    <span className="text-muted d-block small">BARIS SESUDAH BERSIH</span>
                    <h4 className="fw-bold text-success mb-0">{clean.toLocaleString()}</h4>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="p-3 border rounded bg-light">
                    <span className="text-muted d-block small">PERSENTASE LOLOS ATURAN PRD</span>
                    <h4 className="fw-bold text-primary mb-0">{pct}%</h4>
                  </div>
                </div>
              </div>

              <h6 className="fw-bold mb-3">Daftar Chunk Parquet Terkompresi</h6>
              <div className="table-responsive">
                <table className="table table-hover table-bordered table-sm align-middle">
                  <thead className="table-light">
                    <tr>
                      <th style={{ width: 80 }}>Chunk</th>
                      <th>Rentang Baris</th>
                      <th>Ukuran Berkas</th>
                      <th>SHA-256 Checksum (Integritas Data)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ds.chunks?.map((c: any) => (
                      <tr key={c.id}>
                        <td className="fw-bold text-center">#{c.id}</td>
                        <td>Baris {c.row_start?.toLocaleString()} s/d {c.row_end?.toLocaleString()}</td>
                        <td>{(c.size_bytes / (1024 * 1024)).toFixed(2)} MB</td>
                        <td>
                          <code className="text-dark small">{c.checksum}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );
      })}

      {datasets.length === 0 && (
        <div className="alert alert-secondary text-center py-4">
          Belum ada dataset yang terdaftar. Gunakan formulir di atas untuk menyiapkan dataset.
        </div>
      )}
    </div>
  );
}
