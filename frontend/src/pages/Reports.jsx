import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr, currentPeriod, authUrl } from "../api.js";
import { indianDate, periodPretty, SUPPLY_LABEL } from "../labels.js";

export default function Reports() {
  const [gstins, setGstins] = useState([]);
  const [gstinId, setGstinId] = useState("");
  const [period, setPeriod] = useState(currentPeriod());
  const [rows, setRows] = useState([]);
  const [purchases, setPurchases] = useState([]);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    api("/api/gstins").then((g) => { setGstins(g); setGstinId(String((g.find((x) => x.is_primary) || g[0])?.id || "")); });
    api("/api/audit").then(setAudit).catch(() => {});
  }, []);
  useEffect(() => {
    if (!gstinId) return;
    const qs = `gstin_id=${gstinId}&period=${period}`;
    api("/api/reports/sales?" + qs).then(setRows);
    api("/api/purchases?" + qs).then(setPurchases);
  }, [gstinId, period]);

  const sales = rows.filter((r) => r.status !== "CANCELLED");
  const tot = sales.reduce((a, r) => a + r.total, 0);
  const tax = sales.reduce((a, r) => a + r.cgst + r.sgst + r.igst, 0);
  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, flex: 1 }}>Registers & reports</h2>
        <select value={gstinId} onChange={(e) => setGstinId(e.target.value)}>
          {gstins.map((g) => <option key={g.id} value={g.id}>{g.gstin}</option>)}
        </select>
        <input className="edit" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="MMYYYY" title="Return period" />
        <a className="btn secondary" href={authUrl(`/api/export/sales.csv?gstin_id=${gstinId}&period=${period}`)}>Export sales CSV</a>
      </div>
      <div className="cards">
        <div className="card"><h3>Sales total</h3><div className="kpi">{inr(tot)}</div></div>
        <div className="card"><h3>Tax on sales</h3><div className="kpi">{inr(tax)}</div></div>
        <div className="card"><h3>Purchases</h3><div className="kpi">{inr(purchases.reduce((a, p) => a + p.total, 0))}</div></div>
      </div>
      <div className="card">
        <h3>Sales register</h3>
        <table className="data">
          <thead><tr><th>No</th><th>Party</th><th>Supply</th><th>Taxable</th><th>Total</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/invoices/${r.id}`}>{r.number}</Link></td>
                <td>{r.party_name}</td>
                <td>{SUPPLY_LABEL[r.supply_type] || r.supply_type}</td>
                <td className="calc">{inr(r.taxable_value)}</td>
                <td className="calc">{inr(r.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Purchase register</h3>
        <table className="data">
          <thead><tr><th>No</th><th>Vendor</th><th>GSTIN</th><th>Taxable</th><th>ITC tax</th><th>Total</th></tr></thead>
          <tbody>
            {purchases.map((p) => (
              <tr key={p.id}>
                <td>{p.number}</td><td>{p.vendor_name}</td><td>{p.vendor_gstin}</td>
                <td className="calc">{inr(p.taxable_value)}</td>
                <td className="calc">{inr(p.cgst + p.sgst + p.igst)}</td>
                <td className="calc">{inr(p.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Audit log</h3>
        <table className="data">
          <thead><tr><th>When</th><th>Action</th><th>Entity</th><th>Detail</th></tr></thead>
          <tbody>
            {audit.map((a) => (
              <tr key={a.id}>                <td>{a.created_at ? String(a.created_at).replace("T", " ").slice(0, 16) : ""}</td><td>{a.action}</td><td>{a.entity} {a.entity_id || ""}</td><td>{a.detail}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
