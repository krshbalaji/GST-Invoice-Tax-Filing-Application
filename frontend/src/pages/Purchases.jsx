import React, { useContext, useEffect, useState } from "react";
import { Ctx } from "../App.jsx";
import { api, inr, currentPeriod } from "../api.js";
import { periodPretty, indianDate } from "../labels.js";

const empty = {
  number: "", invoice_date: new Date().toISOString().slice(0, 10), vendor_id: "",
  vendor_name: "", vendor_gstin: "", place_of_supply: "", taxable_value: 0, cgst: 0, sgst: 0, igst: 0, total: 0, itc_eligible: true, notes: "",
};

export default function Purchases() {
  const { gstinId, gstins, meta } = useContext(Ctx);
  const [rows, setRows] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [period, setPeriod] = useState(currentPeriod());
  const [form, setForm] = useState(empty);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    if (!gstinId) return;
    setRows(await api(`/api/purchases?gstin_id=${gstinId}&period=${period}`));
  }
  useEffect(() => { api("/api/parties?kind=VENDOR").then(setVendors); }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [gstinId, period]);

  function setField(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  async function save() {
    setErr(""); setMsg("");
    try {
      const body = {
        ...form,
        gstin_id: Number(gstinId),
        vendor_id: form.vendor_id ? Number(form.vendor_id) : null,
        taxable_value: Number(form.taxable_value || 0),
        cgst: Number(form.cgst || 0),
        sgst: Number(form.sgst || 0),
        igst: Number(form.igst || 0),
        total: Number(form.total || 0) || (Number(form.taxable_value || 0) + Number(form.cgst || 0) + Number(form.sgst || 0) + Number(form.igst || 0)),
      };
      await api("/api/purchases", { method: "POST", body: JSON.stringify(body) });
      setForm(empty);
      setMsg("Purchase recorded.");
      load();
    } catch (e) { setErr(e.message); }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Purchase register</h2>
      <p className="hint">Books used for GSTR-3B ITC and GSTR-2B reconciliation. Period {periodPretty(period)}.</p>
      {err && <div className="error">{err}</div>}
      {msg && <div className="okmsg">{msg}</div>}
      <div className="toolbar">
        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value={period}>{periodPretty(period)}</option>
        </select>
        <input className="edit" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="MMYYYY" />
      </div>
      <div className="split">
        <div className="card">
          <h3>Add purchase invoice</h3>
          <div className="row">
            <div className="field"><label>Vendor</label>
              <select className="edit" value={form.vendor_id} onChange={(e) => {
                const v = vendors.find((x) => String(x.id) === e.target.value);
                setForm((f) => ({
                  ...f,
                  vendor_id: e.target.value,
                  vendor_name: v?.name || f.vendor_name,
                  vendor_gstin: v?.gstin || f.vendor_gstin,
                  place_of_supply: v?.place_of_supply || v?.state_code || f.place_of_supply,
                }));
              }}>
                <option value="">Select vendor</option>
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            <div className="field"><label>Invoice no.</label><input className="edit" value={form.number} onChange={(e) => setField("number", e.target.value)} /></div>
            <div className="field"><label>Date</label><input className="edit" type="date" value={form.invoice_date} onChange={(e) => setField("invoice_date", e.target.value)} /></div>
            <div className="field"><label>Place of supply</label>
              <select className="edit" value={form.place_of_supply} onChange={(e) => setField("place_of_supply", e.target.value)}>
                <option value="">Select</option>
                {(meta.states || []).map((s) => <option key={s.code} value={s.code}>{s.code} - {s.name}</option>)}
              </select>
            </div>
            <div className="field"><label>Taxable</label><input className="edit" type="number" value={form.taxable_value} onChange={(e) => setField("taxable_value", e.target.value)} /></div>
            <div className="field"><label>CGST</label><input className="edit" type="number" value={form.cgst} onChange={(e) => setField("cgst", e.target.value)} /></div>
            <div className="field"><label>SGST</label><input className="edit" type="number" value={form.sgst} onChange={(e) => setField("sgst", e.target.value)} /></div>
            <div className="field"><label>IGST</label><input className="edit" type="number" value={form.igst} onChange={(e) => setField("igst", e.target.value)} /></div>
            <div className="field"><label>ITC eligible</label>
              <select className="edit" value={form.itc_eligible ? "Y" : "N"} onChange={(e) => setField("itc_eligible", e.target.value === "Y")}>
                <option value="Y">Yes</option><option value="N">No</option>
              </select>
            </div>
          </div>
          <button className="btn" style={{ marginTop: 10 }} onClick={save} disabled={!gstinId}>Save purchase</button>
        </div>
        <div className="card">
          <h3>{rows.length} invoices · {inr(rows.reduce((a, p) => a + p.total, 0))}</h3>
          <p className="hint">Select a GSTIN in the top bar to post purchases against that registration.</p>
        </div>
      </div>
      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data">
          <thead><tr><th>No</th><th>Date</th><th>Vendor</th><th>GSTIN</th><th>Taxable</th><th>Tax</th><th>Total</th><th>ITC</th></tr></thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={8} className="hint">No purchases in this period.</td></tr>
            )}
            {rows.map((p) => (
              <tr key={p.id}>
                <td>{p.number}</td>
                <td>{p.invoice_date_in || indianDate(p.invoice_date)}</td>
                <td>{p.vendor_name}</td>
                <td>{p.vendor_gstin}</td>
                <td className="calc">{inr(p.taxable_value)}</td>
                <td className="calc">{inr(p.cgst + p.sgst + p.igst)}</td>
                <td className="calc">{inr(p.total)}</td>
                <td>{p.itc_eligible ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
