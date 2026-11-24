"use client";

import { useEffect, useState } from "react";

export default function UjiKegagalanPage() {
  const [workers, setWorkers] = useState<any[]>([]);
  const [selectedWorker, setSelectedWorker] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [recoveryEvents, setRecoveryEvents] = useState<any[]>([]);

  const fetchWorkers = async () => {
    try {
      const res = await fetch("/api/master/workers");
      if (res.ok) {
        const data = await res.json();
        setWorkers(data);
        if (data.length > 0 && !selectedWorker) {
          setSelectedWorker(data[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 3000);

    const eventSource = new EventSource("/api/master/cluster/stream");
    eventSource.addEventListener("fault_injected", (e: any) => {
      const data = JSON.parse(e.data);
      setRecoveryEvents((prev) => [
        { time: new Date().toLocaleTimeString(), type: "INJEKSI", text: `Injeksi ${data.action.toUpperCase()} ke ${data.worker_id}` },
        ...prev
      ]);
    });

    eventSource.addEventListener("task_recovered", (e: any) => {
      const data = JSON.parse(e.data);
      setRecoveryEvents((prev) => [
        {
          time: new Date().toLocaleTimeString(),
          type: "RECOVERY",
          text: `Task #${data.task_id} berhasil dipulihkan di Worker ${data.worker_id} (Recovery Time: ${data.recovery_time_s.toFixed(2)} dtk)`
        },
        ...prev
      ]);
    });

    return () => {
      clearInterval(interval);
      eventSource.close();
    };
  }, []);

  const handleInjectFault = async (action: string) => {
    if (!selectedWorker) {
      alert("Pilih worker target terlebih dahulu!");
      return;
    }
    setActionLoading(true);
    setMsg("");
    try {
      const res = await fetch(`/api/master/faults/${action}/${selectedWorker}`, {
        method: "POST",
      });
      const data = await res.json();
      setMsg(`Aksi '${action.toUpperCase()}' berhasil dikirim ke ${selectedWorker}: ${data.detail}`);
      fetchWorkers();
    } catch (err: any) {
      setMsg("Gagal melakukan fault injection: " + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="fw-bold mb-1">
            <i className="ri-shield-flash-line text-danger me-2"></i>
            Uji Resiliensi & Fault Injection (Skenario E)
          </h2>
          <p className="text-muted mb-0">
            Penyuntikan Kegagalan Terencana, Pengujian Lease Re-queue, dan Pengukuran Recovery Time
          </p>
        </div>
      </div>

      {msg && (
        <div className="alert alert-warning alert-dismissible fade show">
          <i className="ri-alert-line me-2"></i> {msg}
          <button type="button" className="btn-close" onClick={() => setMsg("")}></button>
        </div>
      )}

      {/* Panel Suntik Kegagalan */}
      <div className="card shadow-sm border-0 mb-4 border-start border-danger border-4">
        <div className="card-header bg-white py-3">
          <h5 className="fw-bold mb-0 text-danger">
            <i className="ri-alarm-warning-line me-2"></i>
            Panel Kontrol Penyuntikan Kegagalan
          </h5>
        </div>
        <div className="card-body">
          <div className="row g-3 align-items-center">
            <div className="col-md-5">
              <label className="form-label fw-bold">Pilih Node Worker Target</label>
              <select
                className="form-select form-select-lg"
                value={selectedWorker}
                onChange={(e) => setSelectedWorker(e.target.value)}
              >
                {workers.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.id} - {w.hostname} ({w.ip}) [{w.status}]
                  </option>
                ))}
              </select>
            </div>
            <div className="col-md-7 d-flex gap-2 align-items-end pt-3">
              <button
                className="btn btn-danger btn-lg flex-grow-1 fw-bold"
                onClick={() => handleInjectFault("kill")}
                disabled={actionLoading}
              >
                <i className="ri-close-circle-line me-1"></i>
                Matikan Worker (Kill)
              </button>
              <button
                className="btn btn-warning btn-lg flex-grow-1 fw-bold text-dark"
                onClick={() => handleInjectFault("hang")}
                disabled={actionLoading}
              >
                <i className="ri-pause-circle-line me-1"></i>
                Buat Macet (Hang)
              </button>
              <button
                className="btn btn-secondary btn-lg flex-grow-1 fw-bold"
                onClick={() => handleInjectFault("mute")}
                disabled={actionLoading}
              >
                <i className="ri-wifi-off-line me-1"></i>
                Putus Jaringan (Mute)
              </button>
            </div>
          </div>
          <div className="mt-3 p-3 bg-light rounded small text-muted">
            <strong>Penjelasan Mekanisme Resiliensi:</strong>
            <ul className="mb-0 mt-1">
              <li><strong>Matikan Worker (Kill):</strong> Memanggil <code>psutil.Process().kill()</code> pada node. Supervisor Worker akan menghidupkannya kembali secara otomatis dalam beberapa detik.</li>
              <li><strong>Buat Macet (Hang):</strong> Mensimulasikan deadlock/CPU 100%. Thread komputasi berhenti, Master akan mendeteksi lease kedaluwarsa setelah 30 detik.</li>
              <li><strong>Putus Jaringan (Mute):</strong> Menghentikan pengiriman heartbeat. Setelah 6 detik tanpa heartbeat (3 siklus), Master otomatis menetapkan status Worker menjadi <code>DOWN</code> dan me-requeue task ke worker lain.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Log Peristiwa Pemulihan (Event Sourcing) */}
      <div className="card shadow-sm border-0 mb-4">
        <div className="card-header bg-white py-3 d-flex justify-content-between align-items-center">
          <h5 className="fw-bold mb-0">Log Peristiwa Deteksi Kegagalan & Pemulihan (Recovery)</h5>
          <span className="badge bg-primary">Jam Master Terpadu</span>
        </div>
        <div className="card-body p-0">
          <ul className="list-group list-group-flush">
            {recoveryEvents.map((ev, idx) => (
              <li className="list-group-item d-flex justify-content-between align-items-center py-3" key={idx}>
                <div>
                  <span className={`badge me-2 ${ev.type === "RECOVERY" ? "bg-success" : "bg-danger"}`}>
                    {ev.type}
                  </span>
                  <span>{ev.text}</span>
                </div>
                <small className="text-muted">{ev.time}</small>
              </li>
            ))}
            {recoveryEvents.length === 0 && (
              <li className="list-group-item text-center text-muted py-4">
                Belum ada aktivitas kegagalan yang tercatat. Coba klik tombol "Matikan Worker" saat pekerjaan sedang aktif berjalan.
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
