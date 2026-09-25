import React, { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Ctx } from "../App.jsx";
import { api, inr, currentPeriod, authUrl } from "../api.js";
import { TYPE_LABEL, EINVOICE_LABEL, STATUS_LABEL, SUPPLY_LABEL, badgeClass, periodPretty, indianDate } from "../labels.js";

export default function Invoices() {
  const { gstinId, gstins } = useContext(Ctx);
  const [rows, setRows] = useState([]);
  const [localGstin, setLocalGstin] = useState(gstinId || "");
  const [period, setPeriod] = useState(currentPeriod());
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { setLocalGstin(gstinId || ""); }, [gstinId]);

  async function load() {
    setErr("");
    try {
      const qs = new URLSearchParams();
      if (localGstin) qs.set("gstin_id", localGstin);
      if (period) qs.set("period", period);
      if (q) qs.set("q", q);
      setRows(await api("/api/invoices?" + qs.toString()));
    } catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, [localGstin, period]);

  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, flex: 1 }}>Invoice register</h2>
        <Link className="btn" to="/invoices/new">New invoice</Link>
      </div>
      <div className="toolbar">
        <select value={localGstin} onChange={(e) => setLocalGstin(e.target.value)}>
          <option value="">All GSTINs</option>
          {gstins.map((g) => <option key={g.id} value={g.id}>{g.gstin} · {g.city}</option>)}
        </select>
        <input className="edit" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="MMYYYY" title="Return period MMYYYY" />
        <input className="edit" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search number / party" />
        <button className="btn secondary" onClick={load}>Search</button>
        <a className="btn secondary" href={authUrl(`/api/export/sales.csv?${localGstin ? "gstin_id=" + localGstin + "&" : ""}period=${period}`)}>Export CSV</a>
      </div>
      <p className="hint" style={{ marginTop: 0 }}>Period {periodPretty(period)}. Yellow fields are filters; green cells are calculated tax values.</p>
      {err && <div className="error">{err}</div>}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Number</th><th>Date</th><th>Type</th><th>Party</th><th>POS</th><th>Supply</th>
              <th>Taxable</th><th>Tax</th><th>Total</th><th>e-Invoice</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={11} className="hint">No invoices in this period. <Link to="/invoices/new">Create one</Link>.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/invoices/${r.id}`}>{r.number}</Link></td>
                <td>{r.invoice_date_in || indianDate(r.invoice_date)}</td>
                <td>{r.invoice_type_label || TYPE_LABEL[r.invoice_type]}</td>
                <td>{r.party_name}<div className="hint">{r.party_gstin || "Unregistered"}</div></td>
                <td>{r.place_of_supply}</td>
                <td>{SUPPLY_LABEL[r.supply_type] || r.supply_type}</td>
                <td className="calc">{inr(r.taxable_value)}</td>
                <td className="calc">{inr(r.cgst + r.sgst + r.igst)}</td>
                <td className="calc">{inr(r.total)}</td>
                <td><span className={`badge ${badgeClass(r.einvoice_status)}`}>{r.einvoice_status_label || EINVOICE_LABEL[r.einvoice_status]}</span></td>
                <td>{r.status_label || STATUS_LABEL[r.status]}{r.custom_mode ? " · Custom" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
