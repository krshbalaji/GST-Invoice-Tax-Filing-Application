import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, inr, authUrl } from "../api.js";
import { TYPE_LABEL, EINVOICE_LABEL, STATUS_LABEL, SUPPLY_LABEL, badgeClass, indianDate } from "../labels.js";

export default function InvoiceView() {
  const { id } = useParams();
  const nav = useNavigate();
  const [inv, setInv] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try { setInv(await api("/api/invoices/" + id)); } catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, [id]);

  async function irn() {
    setErr(""); setMsg(""); setBusy(true);
    try {
      const r = await api("/api/invoices/" + id + "/einvoice", { method: "POST" });
      setMsg("Sandbox IRN generated.");
      load();
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  async function cancel() {
    if (!confirm("Cancel this invoice? This cannot be undone.")) return;
    try { await api("/api/invoices/" + id + "/cancel", { method: "POST" }); load(); } catch (e) { setErr(e.message); }
  }
  async function duplicate() {
    setBusy(true);
    try {
      const r = await api("/api/invoices/" + id + "/duplicate", { method: "POST" });
      nav("/invoices/" + r.id);
    } catch (e) { setErr(e.message); setBusy(false); }
  }
  async function creditNote() {
    if (!confirm("Issue a credit note copying these lines?")) return;
    setBusy(true);
    try {
      const r = await api("/api/invoices/" + id + "/credit-note", { method: "POST" });
      nav("/invoices/" + r.id);
    } catch (e) { setErr(e.message); setBusy(false); }
  }

  if (!inv) return err ? <div className="error">{err}</div> : "Loading...";
  const intra = inv.supply_type === "INTRA";
  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, flex: 1 }}>{inv.invoice_type_label || TYPE_LABEL[inv.invoice_type]} {inv.number}</h2>
        {!inv.irn && inv.status !== "CANCELLED" && !inv.locked && <Link className="btn secondary" to={`/invoices/${id}/edit`}>Edit</Link>}
        <button className="btn secondary" onClick={duplicate} disabled={busy}>Duplicate</button>
        {inv.invoice_type === "TAX_INVOICE" && inv.status !== "CANCELLED" && <button className="btn secondary" onClick={creditNote} disabled={busy}>Credit note</button>}
        {inv.einvoice_status === "REQUIRED" && <button className="btn" onClick={irn} disabled={busy}>Generate IRN</button>}
        <a className="btn secondary" href={authUrl(`/api/invoices/${id}/print`)} target="_blank" rel="noreferrer">Print / PDF</a>
        <a className="btn secondary" href={authUrl(`/api/invoices/${id}/einvoice-json`)} target="_blank" rel="noreferrer">INV-01 JSON</a>
        <button className="btn danger" onClick={cancel} disabled={inv.status === "CANCELLED"}>Cancel</button>
      </div>
      {err && <div className="error">{err}</div>}
      {msg && <div className="okmsg">{msg}</div>}
      {inv.custom_mode && <div className="custom-banner">This invoice contains custom (free-form) line items.</div>}
      <div className="split">
        <div className="card">
          <p><b>Date</b> {inv.invoice_date_in || indianDate(inv.invoice_date)} · <b>Place of supply</b> {inv.place_of_supply} {inv.place_of_supply_name} · <b>{SUPPLY_LABEL[inv.supply_type] || inv.supply_type}</b>{inv.sez ? " · SEZ" : ""}</p>
          <p><b>Bill to</b> {inv.party_name}<br />{inv.party_address}<br />GSTIN {inv.party_gstin || "Unregistered"}</p>
          <p><b>Seller GSTIN</b> {inv.seller_gstin} · Preset {inv.gst_preset} · Reverse charge {inv.reverse_charge ? "Yes" : "No"}</p>
          {inv.original_number && <p><b>Against original invoice</b> {inv.original_invoice_id ? <Link to={`/invoices/${inv.original_invoice_id}`}>{inv.original_number}</Link> : inv.original_number} dated {inv.original_date}</p>}
          {inv.irn && <p><b>IRN</b> {inv.irn}<br /><b>Ack</b> {inv.ack_no} · {inv.irn_date_in || inv.irn_date}</p>}
        </div>
        <div className="card">
          <h3>Totals</h3>
          <p>Taxable {inr(inv.taxable_value)}</p>
          <p>CGST {inr(inv.cgst)} · SGST {inr(inv.sgst)} · IGST {inr(inv.igst)}</p>
          <p><b>Total {inr(inv.total)}</b></p>
          <p className="hint">{inv.amount_in_words}</p>
          <p>
            <span className={`badge ${badgeClass(inv.einvoice_status)}`}>{inv.einvoice_status_label || EINVOICE_LABEL[inv.einvoice_status]}</span>
            {" "}
            <span className={`badge ${badgeClass(inv.status)}`}>{inv.status_label || STATUS_LABEL[inv.status]}</span>
          </p>
        </div>
      </div>
      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data">
          <thead>
            <tr><th>Description</th><th>HSN</th><th>Qty</th><th>Rate</th><th>Taxable</th>{intra ? <><th>CGST</th><th>SGST</th></> : <th>IGST</th>}<th>Total</th></tr>
          </thead>
          <tbody>
            {inv.lines.map((ln) => (
              <tr key={ln.id}>
                <td>{ln.description}{ln.custom ? " (Custom)" : ""}</td>
                <td>{ln.hsn_sac}</td>
                <td>{ln.qty} {ln.unit}</td>
                <td>{inr(ln.rate)}</td>
                <td className="calc">{inr(ln.taxable_value)}</td>
                {intra ? <><td className="calc">{inr(ln.cgst)}</td><td className="calc">{inr(ln.sgst)}</td></> : <td className="calc">{inr(ln.igst)}</td>}
                <td className="calc">{inr(ln.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
