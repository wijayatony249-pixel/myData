"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function BuatJobPage() {
  const router = useRouter();
  const [jobType, setJobType] = useState("J4_KMEANS");
  const [mode, setMode] = useState("DISTRIBUTED");
  const [lbMode, setLbMode] = useState("DYNAMIC");
  const [nWorkers, setNWorkers] = useState(9);
  const [kClusters, setKClusters] = useState(8);
  const [maxIter, setMaxIter] = useState(15);
  const [seed, setSeed] = useState(42);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      const payload: any = {
        type: jobType,
        mode: mode,
        lb_mode: lbMode,
        n_workers: Number(nWorkers),
        seed: Number(seed),
        params: {}
      };

      if (jobType === "J4_KMEANS") {
        payload.params = {
          k: Number(kClusters),
          max_iter: Number(maxIter)
        };
      }

      const res = await fetch("/api/master/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal membuat job");
      }

      const data = await res.json();
      router.push(`/job/${data.job_id}`);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 850 }} className="mx-auto">
      <div className="mb-4">
        <h2 className="fw-bold mb-1">
          <i className="ri-play-circle-line text-primary me-2"></i>
          Buat Job Data Mining Baru
        </h2>
        <p className="text-muted mb-0">
          Konfigurasi Algoritma Mining, Skema Distribusi, dan Mode Penyeimbangan Beban
        </p>
      </div>

      {errorMsg && (
        <div className="alert alert-danger alert-dismissible fade show">
          <i className="ri-error-warning-line me-2"></i> {errorMsg}
          <button type="button" className="btn-close" onClick={() => setErrorMsg("")}></button>
        </div>
      )}

      <div className="card shadow-sm border-0">
        <div className="card-body p-4">
          <form onSubmit={handleSubmit}>
            {/* 1. Jenis Analisis Data Mining */}
            <div className="mb-4">
              <label className="form-label fw-bold">1. Jenis Analisis Data Mining</label>
              <div className="row g-2">
                {[
                  {
                    id: "J4_KMEANS",
                    title: "J4: K-Means Clustering",
                    desc: "Beban komputasi utama CPU-bound (Buktian Speedup)",
                    badge: "Beban Berat (Rekomendasi)",
                    badgeColor: "bg-primary"
                  },
                  {
                    id: "J1_STATS",
                    title: "J1: Statistik Deskriptif",
                    desc: "Mean, Min, Max, Varians stabil numerik (Chan-Welford)",
                    badge: "I/O Bound",
                    badgeColor: "bg-secondary"
                  },
                  {
                    id: "J2_GROUPBY",
                    title: "J2: Agregasi Group-by",
                    desc: "Rata-rata tarif dan tip per jam, hari, dan zona lokasi",
                    badge: "I/O Bound",
                    badgeColor: "bg-secondary"
                  },
                  {
                    id: "J3_CORR",
                    title: "J3: Matriks Korelasi",
                    desc: "Korelasi Pearson terpusat (co-moments numerik stabil)",
                    badge: "I/O Bound",
                    badgeColor: "bg-secondary"
                  },
                ].map((item) => (
                  <div className="col-md-6" key={item.id}>
                    <div
                      className={`p-3 border rounded h-100 cursor-pointer ${
                        jobType === item.id ? "border-primary bg-light" : ""
                      }`}
                      style={{ cursor: "pointer" }}
                      onClick={() => setJobType(item.id)}
                    >
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="jobTypeRadio"
                          checked={jobType === item.id}
                          onChange={() => setJobType(item.id)}
                        />
                        <label className="form-check-label fw-bold d-flex justify-content-between align-items-center">
                          {item.title}
                          <span className={`badge ${item.badgeColor} small`}>{item.badge}</span>
                        </label>
                      </div>
                      <small className="text-muted d-block mt-2 ps-4">{item.desc}</small>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 2. Mode Eksekusi */}
            <div className="mb-4">
              <label className="form-label fw-bold">2. Mode Eksekusi Komputasi</label>
              <div className="row g-2">
                {[
                  { id: "DISTRIBUTED", title: "Terdistribusi", desc: "Didistribusikan ke klaster Worker fisik melalui jaringan" },
                  { id: "LOCAL_PARALLEL", title: "Paralel Lokal", desc: "Multiprocessing di 1 komputer tanpa overhead jaringan" },
                  { id: "SEQUENTIAL", title: "Sekuensial", desc: "Baseline 1 proses tunggal tanpa konkurensi (Ts)" },
                ].map((m) => (
                  <div className="col-md-4" key={m.id}>
                    <div
                      className={`p-3 border rounded h-100 ${mode === m.id ? "border-primary bg-light" : ""}`}
                      style={{ cursor: "pointer" }}
                      onClick={() => setMode(m.id)}
                    >
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="modeRadio"
                          checked={mode === m.id}
                          onChange={() => setMode(m.id)}
                        />
                        <label className="form-check-label fw-bold">{m.title}</label>
                      </div>
                      <small className="text-muted d-block mt-1 ps-4">{m.desc}</small>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 3. Mode Load Balancing (Hanya jika mode Distributed) */}
            {mode === "DISTRIBUTED" && (
              <div className="mb-4 p-3 bg-light rounded border">
                <label className="form-label fw-bold mb-2">3. Mode Load Balancing (Penyeimbangan Beban)</label>
                <div className="row g-2">
                  <div className="col-md-6">
                    <div
                      className={`p-3 border rounded bg-white ${lbMode === "DYNAMIC" ? "border-success" : ""}`}
                      style={{ cursor: "pointer" }}
                      onClick={() => setLbMode("DYNAMIC")}
                    >
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="lbRadio"
                          checked={lbMode === "DYNAMIC"}
                          onChange={() => setLbMode("DYNAMIC")}
                        />
                        <label className="form-check-label fw-bold text-success">
                          Mode Dinamis (Bawaan)
                        </label>
                      </div>
                      <small className="text-muted d-block ps-4 mt-1">
                        Pull-based: Worker cepat otomatis mengambil lebih banyak chunk sesuai kecepatan pemrosesan.
                      </small>
                    </div>
                  </div>
                  <div className="col-md-6">
                    <div
                      className={`p-3 border rounded bg-white ${lbMode === "STATIC" ? "border-warning" : ""}`}
                      style={{ cursor: "pointer" }}
                      onClick={() => setLbMode("STATIC")}
                    >
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="lbRadio"
                          checked={lbMode === "STATIC"}
                          onChange={() => setLbMode("STATIC")}
                        />
                        <label className="form-check-label fw-bold text-dark">
                          Mode Statis (Pembanding)
                        </label>
                      </div>
                      <small className="text-muted d-block ps-4 mt-1">
                        Round-Robin: Setiap task ditugaskan kaku ke Worker tertentu sejak awal job dibuat.
                      </small>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Parameter K-Means jika J4 dipilih */}
            {jobType === "J4_KMEANS" && (
              <div className="row g-3 mb-4 p-3 border rounded bg-white">
                <div className="col-md-4">
                  <label className="form-label fw-bold small">Jumlah Cluster (K)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={kClusters}
                    onChange={(e) => setKClusters(Number(e.target.value))}
                    min={2}
                    max={20}
                  />
                  <small className="text-muted">PRD Bawaan: K = 8</small>
                </div>
                <div className="col-md-4">
                  <label className="form-label fw-bold small">Maksimum Iterasi</label>
                  <input
                    type="number"
                    className="form-control"
                    value={maxIter}
                    onChange={(e) => setMaxIter(Number(e.target.value))}
                    min={1}
                    max={50}
                  />
                  <small className="text-muted">Konvergensi bila shift &lt; 1e-4</small>
                </div>
                <div className="col-md-4">
                  <label className="form-label fw-bold small">Seed Acak Deterministik</label>
                  <input
                    type="number"
                    className="form-control"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                  />
                  <small className="text-muted">PRD Bawaan: 42</small>
                </div>
              </div>
            )}

            <div className="d-grid mt-4">
              <button
                type="submit"
                className="btn btn-primary btn-lg fw-bold py-3 shadow-sm"
                disabled={loading}
              >
                <i className="ri-rocket-line me-2"></i>
                {loading ? "Menyiapkan Task..." : "Jalankan Pekerjaan Data Mining"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
