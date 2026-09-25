import React, { useContext, useEffect, useState } from "react";
import { Ctx } from "../App.jsx";
import { api, inr } from "../api.js";

const emptyParty = { kind: "CUSTOMER", name: "", trade_name: "", gstin: "", pan: "", email: "", phone: "", address1: "", city: "", state_code: "", pincode: "", place_of_supply: "", sez: false };
const emptyItem = { kind: "SERVICE", code: "", description: "", hsn_sac: "", unit: "NOS", rate: 0, taxability: "TAXABLE", gst_preset: "REG_18" };

export default function Masters() {
  const { meta } = useContext(Ctx);
  const [tab, setTab] = useState("customers");
  const [parties, setParties] = useState([]);
  const [items, setItems] = useState([]);
  const [party, setParty] = useState(emptyParty);
  const [item, setItem] = useState(emptyItem);
  const [err, setErr] = useState("");
  const [hint, setHint] = useState("");

  async function load() {
    const [p, i] = await Promise.all([api("/api/parties"), api("/api/items")]);
    setParties(p); setItems(i);
  }
  useEffect(() => { load().catch((e) => setErr(e.message)); }, []);

  async function lookup() {
    setErr(""); setHint("");
    if (!party.gstin) return;
    try {
      const r = await api("/api/gstin/lookup?gstin=" + encodeURIComponent(party.gstin));
      setParty((p) => ({ ...p, gstin: r.gstin, state_code: r.state_code, place_of_supply: r.state_code, pan: r.pan }));
      setHint(`GSTIN valid · ${r.state_name} · PAN ${r.pan}. ${r.hint}`);
    } catch (e) { setErr(e.message); }
  }

  async function saveParty() {
    setErr("");
    try {
      await api("/api/parties", { method: "POST", body: JSON.stringify(party) });
      setParty({ ...emptyParty, kind: party.kind });
      load();
    } catch (e) { setErr(e.message); }
  }
  async function saveItem() {
    setErr("");
    try {
      await api("/api/items", { method: "POST", body: JSON.stringify({ ...item, rate: Number(item.rate) }) });
      setItem(emptyItem);
      load();
    } catch (e) { setErr(e.message); }
  }

  const shown = parties.filter((p) => (tab === "vendors" ? p.kind === "VENDOR" : p.kind === "CUSTOMER"));
  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, flex: 1 }}>Masters</h2>
        {["customers", "vendors", "items"].map((t) => (
          <button key={t} className={tab === t ? "btn" : "btn secondary"} onClick={() => setTab(t)}>{t === "customers" ? "Customers" : t === "vendors" ? "Vendors" : "Items"}</button>
        ))}
      </div>
      {err && <div className="error">{err}</div>}
      {tab !== "items" && (
        <div className="split">
          <div className="card">
            <h3>Add {tab === "vendors" ? "vendor" : "customer"}</h3>
            <div className="row">
              <div className="field"><label>Legal name</label><input className="edit" value={party.name} onChange={(e) => setParty({ ...party, name: e.target.value, kind: tab === "vendors" ? "VENDOR" : "CUSTOMER" })} /></div>
              <div className="field"><label>GSTIN</label>
                <div className="row">
                  <input className="edit" value={party.gstin} onChange={(e) => setParty({ ...party, gstin: e.target.value.toUpperCase() })} />
                  <button className="btn secondary" type="button" onClick={lookup}>Validate</button>
                </div>
              </div>
            </div>
            {hint && <p className="hint">{hint}</p>}
            <div className="row">
              <div className="field"><label>Email</label><input className="edit" value={party.email} onChange={(e) => setParty({ ...party, email: e.target.value })} /></div>
              <div className="field"><label>Phone</label><input className="edit" value={party.phone} onChange={(e) => setParty({ ...party, phone: e.target.value })} /></div>
              <div className="field"><label>City</label><input className="edit" value={party.city} onChange={(e) => setParty({ ...party, city: e.target.value })} /></div>
              <div className="field"><label>State</label>
                <select className="edit" value={party.state_code} onChange={(e) => setParty({ ...party, state_code: e.target.value, place_of_supply: e.target.value })}>
                  <option value="">Select</option>
                  {(meta.states || []).map((s) => <option key={s.code} value={s.code}>{s.code} - {s.name}</option>)}
                </select>
              </div>
              <div className="field"><label>Pincode</label><input className="edit" value={party.pincode} onChange={(e) => setParty({ ...party, pincode: e.target.value })} /></div>
              <div className="field"><label>Address</label><input className="edit" value={party.address1} onChange={(e) => setParty({ ...party, address1: e.target.value })} /></div>
              <div className="field"><label>SEZ unit</label>
                <select className="edit" value={party.sez ? "Y" : "N"} onChange={(e) => setParty({ ...party, sez: e.target.value === "Y" })}>
                  <option value="N">No</option>
                  <option value="Y">Yes — charge IGST (SEWP)</option>
                </select>
              </div>
            </div>
            <button className="btn" style={{ marginTop: 10 }} onClick={saveParty}>Save party</button>
          </div>
          <div className="card">
            <h3>{shown.length} records</h3>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Name</th><th>GSTIN</th><th>State</th><th>SEZ</th></tr></thead>
                <tbody>{shown.map((p) => <tr key={p.id}><td>{p.name}</td><td>{p.gstin || "Unregistered"}</td><td>{p.state_code} {p.state_name || ""}</td><td>{p.sez ? "Yes" : ""}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "items" && (
        <div className="split">
          <div className="card">
            <h3>Add product / service</h3>
            <div className="row">
              <div className="field"><label>Code</label><input className="edit" value={item.code} onChange={(e) => setItem({ ...item, code: e.target.value })} /></div>
              <div className="field"><label>Description</label><input className="edit" value={item.description} onChange={(e) => setItem({ ...item, description: e.target.value })} /></div>
              <div className="field"><label>HSN/SAC</label><input className="edit" value={item.hsn_sac} onChange={(e) => setItem({ ...item, hsn_sac: e.target.value })} /></div>
              <div className="field"><label>Unit</label><input className="edit" value={item.unit} onChange={(e) => setItem({ ...item, unit: e.target.value })} /></div>
              <div className="field"><label>Rate</label><input className="edit" type="number" value={item.rate} onChange={(e) => setItem({ ...item, rate: e.target.value })} /></div>
              <div className="field"><label>Kind</label>
                <select className="edit" value={item.kind} onChange={(e) => setItem({ ...item, kind: e.target.value })}>
                  <option>SERVICE</option><option>GOODS</option>
                </select>
              </div>
              <div className="field"><label>Preset</label>
                <select className="edit" value={item.gst_preset} onChange={(e) => setItem({ ...item, gst_preset: e.target.value })}>
                  {(meta.presets || []).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
                </select>
              </div>
            </div>
            <button className="btn" style={{ marginTop: 10 }} onClick={saveItem}>Save item</button>
          </div>
          <div className="card">
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Code</th><th>Description</th><th>HSN</th><th>Rate</th></tr></thead>
                <tbody>{items.map((i) => <tr key={i.id}><td>{i.code}</td><td>{i.description}</td><td>{i.hsn_sac}</td><td className="calc">{inr(i.rate)}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
