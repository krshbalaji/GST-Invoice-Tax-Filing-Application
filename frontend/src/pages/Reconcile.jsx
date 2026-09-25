import React, { useEffect, useState } from "react";
import { api, inr, currentPeriod } from "../api.js";
import { badgeClass, periodPretty, indianDate } from "../labels.js";

export default function Reconcile() {
  const [gstins, setGstins] = useState([]);
  const [gstinId, setGstinId] = useState("");
  const [period, setPeriod] = useState(currentPeriod());
  const [tab, setTab] = useState("irn");
  const [data, setData] = useState({ rows: [], buckets: {} });
  const [err, setErr] = useState("");

  useEffect(() => {
    api("/api/gstins").then((g) => { setGstins(g); setGstinId(String((g.find((x) => x.is_primary) || g[0])?.id || "")); });
  }, []);

  async function load() {
    if (!gstinId) return;
    setErr("");
    try {
      const path = tab === "irn" ? "/api/reconcile/einvoice" : "/api/reconcile/itc";
      setData(await api(`${path}?gstin_id=${gstinId}&period=${period}`));
    } catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, [gstinId, period, tab]);

  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, flex: 1 }}>Reconciliation</h2>
        <button className={tab === "irn" ? "btn" : "btn secondary"} onClick={() => setTab("irn")}>GSTR-1 vs IRN</button>
        <button className={tab === "itc" ? "btn" : "btn secondary"} onClick={() => setTab("itc")}>GSTR-2B vs books</button>
        <select value={gstinId} onChange={(e) => setGstinId(e.target.value)}>
          {gstins.map((g) => <option key={g.id} value={g.id}>{g.gstin}</option>)}
        </select>
        <input className="edit" value={period} onChange={(e) => setPeriod(e.target.value)} />
      </div>
      {err && <div className="error">{err}</div>}
      <div className="cards">
        {Object.entries(data.buckets || {}).map(([k, v]) => (
          <div className="card" key={k}><h3>{k}</h3><div className="kpi">{v}</div></div>
        ))}
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Bucket</th><th>Number</th><th>Date</th><th>Party / Vendor</th><th>GSTIN</th>
              {tab === "itc" ? <><th>Books</th><th>2B</th></> : <><th>Total</th><th>IRN</th></>}
            </tr>
          </thead>
          <tbody>
            {(data.rows || []).map((r, i) => (
              <tr key={i}>
                <td><span className={`badge ${badgeClass(r.bucket)}`}>{r.bucket === "OK" ? "Matched" : r.bucket}</span></td>
                <td>{r.number}</td>
                <td>{r.date && r.date.includes("-") && r.date[4] === "-" ? indianDate(r.date) : r.date}</td>
                <td>{r.party || r.vendor_name}</td>
                <td>{r.gstin || r.vendor_gstin}</td>
                {tab === "itc" ? <><td className="calc">{r.book_total != null ? inr(r.book_total) : "-"}</td><td className="calc">{r.portal_total != null ? inr(r.portal_total) : "-"}</td></> : <><td className="calc">{inr(r.total)}</td><td>{r.irn ? r.irn.slice(0, 12) + "…" : ""}</td></>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
