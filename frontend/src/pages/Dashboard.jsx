import React, { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Ctx } from "../App.jsx";
import { api, inr } from "../api.js";
import { EINVOICE_LABEL, badgeClass, periodPretty, indianDate } from "../labels.js";

function filingClass(status, meta) {
  if (status === "FILED") return "ok";
  if (!meta) return "info";
  if (meta.state === "overdue") return "bad";
  if (meta.state === "due_soon") return "warn";
  return "info";
}

function dueText(meta, fallback) {
  if (!meta) return fallback;
  if (meta.state === "overdue") return `${meta.label} · ${Math.abs(meta.days)} days overdue`;
  if (meta.days === 0) return `${meta.label} · due today`;
  return `${meta.label} · in ${meta.days} days`;
}

export default function Dashboard() {
  const { gstinId } = useContext(Ctx);
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busyId, setBusyId] = useState(null);

  function load() {
    const qs = gstinId ? "?gstin_id=" + gstinId : "";
    api("/api/dashboard" + qs).then(setD).catch((e) => setErr(e.message));
  }
  useEffect(() => { load(); }, [gstinId]);

  async function generateIrn(id) {
    setErr(""); setMsg(""); setBusyId(id);
    try {
      const r = await api("/api/invoices/" + id + "/einvoice", { method: "POST" });
      setMsg("Sandbox IRN generated: " + (r.irn || "").slice(0, 16) + "...");
      load();
    } catch (e) { setErr(e.message); }
    finally { setBusyId(null); }
  }

  if (err && !d) return <div className="error">{err}</div>;
  if (!d) return <div>Loading...</div>;
  const g1 = d.due_dates?.gstr1_meta;
  const g3 = d.due_dates?.gstr3b_meta;
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Compliance dashboard</h2>
      <p className="hint" style={{ marginTop: -8 }}>{d.today_in} · {d.period_label || periodPretty(d.period)} · FY {d.fy}</p>
      {err && <div className="error">{err}</div>}
      {msg && <div className="okmsg">{msg}</div>}
      {d.einvoice_warning && (
        <div className="card warn" style={{ marginBottom: 12 }}>
          AATO is {inr(d.aato)}, at or above the Rs 5 Cr e-invoicing threshold. B2B tax invoices must carry IRN and QR.
          {d.pending_irn_count > 0 && <> {d.pending_irn_count} invoice{d.pending_irn_count === 1 ? "" : "s"} in this period still need IRN.</>}
        </div>
      )}
      <div className="cards">
        <div className="card"><h3>This period outward</h3><div className="kpi">{inr(d.outward_taxable)}</div></div>
        <div className="card"><h3>Tax liability</h3><div className="kpi">{inr(d.tax_liability)}</div></div>
        <div className="card"><h3>ITC available</h3><div className="kpi">{inr(d.itc)}</div></div>
        <div className="card"><h3>Net payable</h3><div className="kpi">{inr(d.net_payable)}</div></div>
        <div className="card"><h3>FY turnover</h3><div className="kpi">{inr(d.fy_turnover)}</div></div>
        <div className="card"><h3>Invoices this period</h3><div className="kpi">{d.invoice_count}</div></div>
      </div>
      <div className="split">
        <div>
          <div className="card">
            <h3>Recent invoices</h3>
            <table className="data">
              <thead><tr><th>No.</th><th>Date</th><th>Party</th><th>Total</th><th>e-Invoice</th></tr></thead>
              <tbody>
                {d.recent.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/invoices/${r.id}`}>{r.number}</Link></td>
                    <td>{r.invoice_date_in || indianDate(r.invoice_date)}</td>
                    <td>{r.party_name}</td>
                    <td className="calc">{inr(r.total)}</td>
                    <td><span className={`badge ${badgeClass(r.einvoice_status)}`}>{r.einvoice_status_label || EINVOICE_LABEL[r.einvoice_status] || r.einvoice_status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {d.pending_irn && d.pending_irn.length > 0 && (
            <div className="card" style={{ marginTop: 12 }}>
              <h3>Pending IRN ({d.pending_irn_count})</h3>
              <p className="hint">B2B tax invoices above the e-invoice threshold without IRN. Generate before sharing with the buyer.</p>
              <table className="data">
                <thead><tr><th>No.</th><th>Date</th><th>Party</th><th>Total</th><th></th></tr></thead>
                <tbody>
                  {d.pending_irn.map((r) => (
                    <tr key={r.id}>
                      <td><Link to={`/invoices/${r.id}`}>{r.number}</Link></td>
                      <td>{r.invoice_date_in || indianDate(r.invoice_date)}</td>
                      <td>{r.party_name}<div className="hint">{r.party_gstin}</div></td>
                      <td className="calc">{inr(r.total)}</td>
                      <td><button className="btn" disabled={busyId === r.id} onClick={() => generateIrn(r.id)}>{busyId === r.id ? "Generating..." : "Generate IRN"}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div>
          <div className="card">
            <h3>Filing calendar</h3>
            <p>GSTR-1 <span className={`badge ${filingClass(d.filing?.gstr1, g1)}`}>{d.filing?.gstr1 === "FILED" ? "Filed" : "Not filed"}</span></p>
            <p className="hint">{dueText(g1, d.due_dates.gstr1_in || d.due_dates.gstr1)}</p>
            <p>GSTR-3B <span className={`badge ${filingClass(d.filing?.gstr3b, g3)}`}>{d.filing?.gstr3b === "FILED" ? "Filed" : "Not filed"}</span></p>
            <p className="hint">{dueText(g3, d.due_dates.gstr3b_in || d.due_dates.gstr3b)}</p>
            <p className="hint">{d.period_label || periodPretty(d.period)} · FY {d.fy}</p>
            <Link className="btn" to="/returns">Open returns</Link>
          </div>
          <div className="card" style={{ marginTop: 12 }}>
            <h3>Organisation</h3>
            <p>{d.counts.gstins} GSTINs · {d.counts.parties} parties · {d.counts.items} items</p>
            <p className="hint">{d.sandbox ? "E-invoice is in sandbox / mock IRP mode." : "Live GSP configured."}</p>
            <Link className="btn secondary" to="/invoices/new">Create invoice</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
