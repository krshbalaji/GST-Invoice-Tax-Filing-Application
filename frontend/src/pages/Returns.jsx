import React, { useEffect, useState } from "react";
import { api, inr, currentPeriod, authUrl } from "../api.js";

export default function Returns() {
  const [gstins, setGstins] = useState([]);
  const [gstinId, setGstinId] = useState("");
  const [period, setPeriod] = useState(currentPeriod());
  const [g1, setG1] = useState(null);
  const [g3, setG3] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api("/api/gstins").then((g) => { setGstins(g); setGstinId(String((g.find((x) => x.is_primary) || g[0])?.id || "")); });
  }, []);

  async function load() {
    if (!gstinId) return;
    setErr("");
    try {
      const qs = `gstin_id=${gstinId}&period=${period}`;
      const [a, b] = await Promise.all([api("/api/returns/gstr1?" + qs), api("/api/returns/gstr3b?" + qs)]);
      setG1(a); setG3(b);
    } catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, [gstinId, period]);

  async function lock(form) {
    setErr(""); setMsg("");
    try {
      await api(`/api/returns/lock?gstin_id=${gstinId}&period=${period}&form=${form}`, { method: "POST" });
      setMsg(form + " marked filed and period locked.");
    } catch (e) { setErr(e.message); }
  }

  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, flex: 1 }}>Returns — GSTR-1 / GSTR-3B</h2>
        <select value={gstinId} onChange={(e) => setGstinId(e.target.value)}>
          {gstins.map((g) => <option key={g.id} value={g.id}>{g.gstin}</option>)}
        </select>
        <input className="edit" value={period} onChange={(e) => setPeriod(e.target.value)} />
        {gstinId && <a className="btn secondary" href={authUrl(`/api/export/gstr1?gstin_id=${gstinId}&period=${period}`)}>Download GSTR-1 JSON</a>}
      </div>
      {err && <div className="error">{err}</div>}
      {msg && <div className="card" style={{ background: "var(--green)" }}>{msg}</div>}
      {g3 && (
        <div className="cards">
          <div className="card"><h3>3.1 Outward taxable</h3><div className="kpi">{inr(g3.outward?.taxable)}</div></div>
          <div className="card"><h3>IGST / CGST / SGST</h3><div>{inr(g3.outward?.igst)} · {inr(g3.outward?.cgst)} · {inr(g3.outward?.sgst)}</div></div>
          <div className="card"><h3>ITC</h3><div>{inr(g3.itc?.igst + g3.itc?.cgst + g3.itc?.sgst)}</div></div>
          <div className="card"><h3>Net payable</h3><div className="kpi">{inr(g3.tx_pmt?.total)}</div></div>
          {g3.sup_details?.isup_rev && (g3.sup_details.isup_rev.txval || g3.sup_details.isup_rev.samt || g3.sup_details.isup_rev.iamt) ? (
            <div className="card"><h3>3.1(d) Reverse charge</h3><div>{inr(g3.sup_details.isup_rev.txval)} taxable</div></div>
          ) : null}
        </div>
      )}
      {g1 && (
        <div className="split">
          <div className="card">
            <h3>GSTR-1 Table 4A/4B B2B ({g1.b2b?.length || 0})</h3>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>GSTIN</th><th>Invoice</th><th>Date</th><th>Value</th><th>IRN</th></tr></thead>
                <tbody>
                  {(g1.b2b || []).flatMap((b) => (b.inv || []).map((inv) => (
                    <tr key={b.ctin + inv.inum}><td>{b.ctin}</td><td>{inv.inum}</td><td>{inv.idt}</td><td className="calc">{inr(inv.val)}</td><td>{inv.irn ? "Yes" : ""}{inv.inv_typ && inv.inv_typ !== "R" ? ` · ${inv.inv_typ}` : ""}</td></tr>
                  )))}
                </tbody>
              </table>
            </div>
            {(g1.cdnr || []).length > 0 && (
              <>
                <h3 style={{ marginTop: 16 }}>Table 9B CDNR ({g1.cdnr.length})</h3>
                <table className="data">
                  <thead><tr><th>GSTIN</th><th>Note</th><th>Date</th><th>Original inv.</th><th>Orig. date</th><th>Value</th></tr></thead>
                  <tbody>
                    {g1.cdnr.map((n) => (
                      <tr key={n.nt_num}>
                        <td>{n.ctin}</td>
                        <td>{n.nt_num}</td>
                        <td>{n.nt_dt}</td>
                        <td>{n.ont_num || n.inum}</td>
                        <td>{n.ont_dt || n.idt}</td>
                        <td className="calc">{inr(n.val)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            <h3 style={{ marginTop: 16 }}>Table 12 HSN summary</h3>
            <table className="data">
              <thead><tr><th>HSN</th><th>Qty</th><th>Taxable</th><th>IGST</th><th>CGST</th><th>SGST</th></tr></thead>
              <tbody>
                {(g1.hsn?.data || []).map((h) => (
                  <tr key={h.hsn}><td>{h.hsn}</td><td>{h.qty}</td><td className="calc">{inr(h.txval)}</td><td className="calc">{inr(h.igst)}</td><td className="calc">{inr(h.cgst)}</td><td className="calc">{inr(h.sgst)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <div className="card">
              <h3>Document summary</h3>
              {(g1.doc_issue || []).map((d) => (
                <p key={d.doc_typ}>{d.doc_typ}: {d.from} – {d.to} ({d.net_issue} net / {d.cancel} cancelled)</p>
              ))}
              <p className="hint">B2C rows: {g1.b2cs?.length || 0} · CDNR: {g1.cdnr?.length || 0} · Export: {g1.exp?.length || 0}</p>
              <button className="btn" onClick={() => lock("GSTR1")}>Mark GSTR-1 filed</button>
              <button className="btn secondary" style={{ marginLeft: 8 }} onClick={() => lock("GSTR3B")}>Mark GSTR-3B filed</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
