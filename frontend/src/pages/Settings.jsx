import React, { useContext, useEffect, useState } from "react";
import { Ctx } from "../App.jsx";
import { api, inr } from "../api.js";

export default function Settings() {
  const { me, setMe, meta } = useContext(Ctx);
  const [company, setCompany] = useState(null);
  const [gstins, setGstins] = useState([]);
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [preset, setPreset] = useState("REG_18");
  const [gform, setGform] = useState({ gstin: "", legal_name: "", trade_name: "", address1: "", city: "", state_code: "29", pincode: "", email: "", phone: "", invoice_prefix: "INV/" });

  useEffect(() => {
    api("/api/company").then(setCompany);
    api("/api/gstins").then(setGstins);
    api("/api/users").then(setUsers);
  }, []);

  async function saveCompany() {
    setErr(""); setMsg("");
    try {
      const c = await api("/api/company", { method: "PUT", body: JSON.stringify(company) });
      setCompany(c);
      setMe((m) => ({ ...m, company: c }));
      setMsg("Company profile saved.");
    } catch (e) { setErr(e.message); }
  }
  async function addGstin() {
    setErr("");
    try {
      const row = await api("/api/gstins", { method: "POST", body: JSON.stringify(gform) });
      setGstins((g) => [...g, row]);
      setMsg("GSTIN added.");
    } catch (e) { setErr(e.message); }
  }
  async function applyPreset() {
    setErr(""); setMsg("");
    try {
      const r = await api("/api/gst-preset/apply?code=" + preset, { method: "POST" });
      setMsg(`Preset ${preset} applied to ${r.updated} unlocked invoices.`);
    } catch (e) { setErr(e.message); }
  }

  if (!company) return "Loading...";
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Organisation & GSTINs</h2>
      {err && <div className="error">{err}</div>}
      {msg && <div className="card" style={{ background: "var(--green)" }}>{msg}</div>}
      <div className="split">
        <div className="card">
          <h3>Business profile</h3>
          <div className="row">
            <div className="field"><label>Legal name</label><input className="edit" value={company.legal_name} onChange={(e) => setCompany({ ...company, legal_name: e.target.value })} /></div>
            <div className="field"><label>Trade name</label><input className="edit" value={company.trade_name} onChange={(e) => setCompany({ ...company, trade_name: e.target.value })} /></div>
            <div className="field"><label>PAN</label><input className="edit" value={company.pan} onChange={(e) => setCompany({ ...company, pan: e.target.value.toUpperCase() })} /></div>
            <div className="field"><label>Scheme</label>
              <select className="edit" value={company.scheme} onChange={(e) => setCompany({ ...company, scheme: e.target.value })}>
                <option>REGULAR</option><option>COMPOSITION</option>
              </select>
            </div>
            <div className="field"><label>AATO</label><input className="edit" type="number" value={company.aato} onChange={(e) => setCompany({ ...company, aato: Number(e.target.value) })} /></div>
            <div className="field"><label>Bank</label><input className="edit" value={company.bank_name} onChange={(e) => setCompany({ ...company, bank_name: e.target.value })} /></div>
            <div className="field"><label>Account</label><input className="edit" value={company.bank_account} onChange={(e) => setCompany({ ...company, bank_account: e.target.value })} /></div>
            <div className="field"><label>IFSC</label><input className="edit" value={company.bank_ifsc} onChange={(e) => setCompany({ ...company, bank_ifsc: e.target.value })} /></div>
            <div className="field"><label>Branch</label><input className="edit" value={company.bank_branch} onChange={(e) => setCompany({ ...company, bank_branch: e.target.value })} /></div>
            <div className="field" style={{ flex: "1 1 100%" }}><label>Terms</label><textarea className="edit" rows={2} value={company.terms} onChange={(e) => setCompany({ ...company, terms: e.target.value })} /></div>
          </div>
          <button className="btn" style={{ marginTop: 10 }} onClick={saveCompany}>Save profile</button>
        </div>
        <div className="card">
          <h3>GST rate preset — apply to open invoices</h3>
          <p className="hint">Single click updates Scheme, CGST/SGST/IGST split and recalculates unlocked invoices without IRN.</p>
          <select className="edit" value={preset} onChange={(e) => setPreset(e.target.value)}>
            {(meta.presets || []).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
          </select>
          <button className="btn" style={{ marginTop: 10 }} onClick={applyPreset}>Apply preset</button>
          <p className="hint" style={{ marginTop: 12 }}>AATO {inr(company.aato)}. E-invoicing threshold Rs 5,00,00,000.</p>
        </div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>GSTINs</h3>
        <table className="data">
          <thead><tr><th>GSTIN</th><th>Trade name</th><th>State</th><th>Prefix</th></tr></thead>
          <tbody>
            {gstins.map((g) => (
              <tr key={g.id}><td>{g.gstin}{g.is_primary ? " (primary)" : ""}</td><td>{g.trade_name}</td><td>{g.state_code} {g.state_name}</td><td>{g.invoice_prefix}</td></tr>
            ))}
          </tbody>
        </table>
        <h3 style={{ marginTop: 16 }}>Add GSTIN</h3>
        <div className="row">
          <div className="field"><label>GSTIN</label><input className="edit" value={gform.gstin} onChange={(e) => setGform({ ...gform, gstin: e.target.value.toUpperCase() })} /></div>
          <div className="field"><label>Legal name</label><input className="edit" value={gform.legal_name} onChange={(e) => setGform({ ...gform, legal_name: e.target.value })} /></div>
          <div className="field"><label>City</label><input className="edit" value={gform.city} onChange={(e) => setGform({ ...gform, city: e.target.value })} /></div>
          <div className="field"><label>State</label>
            <select className="edit" value={gform.state_code} onChange={(e) => setGform({ ...gform, state_code: e.target.value })}>
              {(meta.states || []).map((s) => <option key={s.code} value={s.code}>{s.code} - {s.name}</option>)}
            </select>
          </div>
          <div className="field"><label>Pincode</label><input className="edit" value={gform.pincode} onChange={(e) => setGform({ ...gform, pincode: e.target.value })} /></div>
          <div className="field"><label>Address</label><input className="edit" value={gform.address1} onChange={(e) => setGform({ ...gform, address1: e.target.value })} /></div>
        </div>
        <button className="btn" style={{ marginTop: 8 }} onClick={addGstin}>Add GSTIN</button>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Users</h3>
        <table className="data">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead>
          <tbody>{users.map((u) => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
