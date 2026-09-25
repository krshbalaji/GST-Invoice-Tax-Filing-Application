import React, { useContext, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Ctx } from "../App.jsx";
import { api, inr } from "../api.js";
import { SUPPLY_LABEL } from "../labels.js";

const emptyLine = () => ({ item_id: "", custom: false, description: "", hsn_sac: "", unit: "NOS", qty: 1, rate: 0, discount: 0 });

export default function InvoiceForm() {
  const { id } = useParams();
  const { meta, gstinId: ctxGstin } = useContext(Ctx);
  const nav = useNavigate();
  const [gstins, setGstins] = useState([]);
  const [parties, setParties] = useState([]);
  const [items, setItems] = useState([]);
  const [originals, setOriginals] = useState([]);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState(null);
  const [form, setForm] = useState({
    gstin_id: "",
    party_id: "",
    invoice_type: "TAX_INVOICE",
    invoice_date: new Date().toISOString().slice(0, 10),
    place_of_supply: "",
    reverse_charge: false,
    gst_preset: "REG_18",
    notes: "",
    round_off: 0,
    custom_mode: false,
    original_invoice_id: "",
    lines: [emptyLine()],
  });

  useEffect(() => {
    Promise.all([api("/api/gstins"), api("/api/parties?kind=CUSTOMER"), api("/api/items")]).then(([g, p, i]) => {
      setGstins(g); setParties(p); setItems(i);
      setForm((f) => ({ ...f, gstin_id: f.gstin_id || ctxGstin || (g.find((x) => x.is_primary) || g[0])?.id || "" }));
    });
  }, []);

  useEffect(() => {
    if (form.invoice_type !== "CREDIT_NOTE" && form.invoice_type !== "DEBIT_NOTE") return;
    const qs = new URLSearchParams();
    if (form.gstin_id) qs.set("gstin_id", form.gstin_id);
    api("/api/invoices?" + qs.toString()).then((rows) => {
      setOriginals(rows.filter((r) => r.invoice_type === "TAX_INVOICE" || r.invoice_type === "BILL_OF_SUPPLY"));
    }).catch(() => {});
  }, [form.invoice_type, form.gstin_id]);

  useEffect(() => {
    if (!id) return;
    api("/api/invoices/" + id).then((inv) => {
      setForm({
        gstin_id: inv.gstin_id,
        party_id: inv.party_id || "",
        invoice_type: inv.invoice_type,
        invoice_date: inv.invoice_date,
        place_of_supply: inv.place_of_supply,
        reverse_charge: inv.reverse_charge,
        gst_preset: inv.gst_preset,
        notes: inv.notes || "",
        round_off: inv.round_off || 0,
        custom_mode: inv.custom_mode,
        original_invoice_id: inv.original_invoice_id || "",
        lines: inv.lines.map((ln) => ({
          item_id: ln.item_id || "",
          custom: ln.custom,
          description: ln.description,
          hsn_sac: ln.hsn_sac,
          unit: ln.unit,
          qty: ln.qty,
          rate: ln.rate,
          discount: ln.discount,
        })),
      });
    }).catch((e) => setErr(e.message));
  }, [id]);

  function setField(k, v) { setForm((f) => ({ ...f, [k]: v })); }
  function setLine(i, patch) {
    setForm((f) => {
      const lines = f.lines.map((ln, idx) => (idx === i ? { ...ln, ...patch } : ln));
      return { ...f, lines };
    });
  }

  const seller = gstins.find((g) => String(g.id) === String(form.gstin_id));
  const party = parties.find((p) => String(p.id) === String(form.party_id));

  useEffect(() => {
    if (party && !form.place_of_supply) setField("place_of_supply", party.place_of_supply || party.state_code);
  }, [form.party_id]);

  const payload = useMemo(() => ({
    ...form,
    gstin_id: Number(form.gstin_id),
    party_id: form.party_id ? Number(form.party_id) : null,
    reverse_charge: !!form.reverse_charge,
    round_off: Number(form.round_off || 0),
    original_invoice_id: form.original_invoice_id ? Number(form.original_invoice_id) : null,
    lines: form.lines.map((ln) => ({
      ...ln,
      item_id: ln.custom || ln.item_id === "<<CUSTOM>>" || ln.item_id === "" ? null : Number(ln.item_id),
      custom: ln.custom || ln.item_id === "<<CUSTOM>>",
      qty: Number(ln.qty || 0),
      rate: Number(ln.rate || 0),
      discount: Number(ln.discount || 0),
    })),
  }), [form]);

  useEffect(() => {
    if (!form.gstin_id) return;
    const t = setTimeout(() => {
      api("/api/invoices/preview", { method: "POST", body: JSON.stringify(payload) })
        .then(setPreview)
        .catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [payload.gstin_id, payload.party_id, payload.gst_preset, payload.place_of_supply, payload.round_off, JSON.stringify(payload.lines)]);

  function validate() {
    if (!form.gstin_id) return "Select the GSTIN / branch issuing this document.";
    if (!form.party_id) return "Select a customer (Bill To).";
    if (!form.invoice_date) return "Invoice date is required.";
    if (!form.place_of_supply) return "Place of supply is required (Rule 46).";
    if (!form.lines.length) return "Add at least one line item.";
    for (let i = 0; i < form.lines.length; i++) {
      const ln = form.lines[i];
      const custom = ln.custom || ln.item_id === "<<CUSTOM>>";
      if (!custom && !ln.item_id) return `Line ${i + 1}: select an item or Custom Entry.`;
      if (custom && !ln.description) return `Line ${i + 1}: custom lines need a description.`;
      if (Number(ln.qty) <= 0) return `Line ${i + 1}: quantity must be greater than zero.`;
    }
    if ((form.invoice_type === "CREDIT_NOTE" || form.invoice_type === "DEBIT_NOTE") && !form.original_invoice_id) {
      return "Credit / debit notes should reference the original invoice number (GSTR-1 CDNR).";
    }
    return "";
  }

  async function save() {
    const v = validate();
    if (v) { setErr(v); return; }
    setErr("");
    try {
      const r = id
        ? await api("/api/invoices/" + id, { method: "PUT", body: JSON.stringify(payload) })
        : await api("/api/invoices", { method: "POST", body: JSON.stringify(payload) });
      nav("/invoices/" + r.id);
    } catch (e) { setErr(e.message); }
  }

  const intra = preview?.supply_type === "INTRA";
  const supplyHint = preview
    ? (preview.sez
      ? "SEZ recipient — treated as inter-State. IGST is charged even if the buyer is in the same State."
      : preview.supply_type === "INTRA"
        ? "Same State as the supplier — CGST + SGST (half the GST rate each)."
        : preview.supply_type === "EXPORT"
          ? "Export / POS 96 — IGST (or LUT zero-rated as configured)."
          : "Different State from the supplier — IGST only.")
    : "";
  const taxHint = preview?.composition
    ? "Composition scheme: Bill of Supply. Do not charge GST to the customer."
    : intra
      ? "Yellow cells are editable. Green cells are calculated (taxable value, CGST, SGST, total)."
      : "Yellow cells are editable. Green cells are calculated (taxable value, IGST, total).";

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>{id ? "Edit invoice" : "Create invoice"}</h2>
      {err && <div className="error">{err}</div>}
      {(form.custom_mode || form.lines.some((l) => l.custom || l.item_id === "<<CUSTOM>>")) && (
        <div className="custom-banner">Custom Mode is on. Description, HSN/SAC, unit and rate are typed by you — they are not pulled from the item master.</div>
      )}

      <div className="card" style={{ marginBottom: 12 }}>
        <h3>1. Issuing GSTIN</h3>
        <div className="row">
          <div className="field"><label>GSTIN / Branch</label>
            <select className="edit" value={form.gstin_id} onChange={(e) => setField("gstin_id", e.target.value)}>
              {gstins.map((g) => <option key={g.id} value={g.id}>{g.gstin} · {g.city} ({g.state_code})</option>)}
            </select>
          </div>
          <div className="field"><label>Document type</label>
            <select className="edit" value={form.invoice_type} onChange={(e) => setField("invoice_type", e.target.value)}>
              <option value="TAX_INVOICE">Tax Invoice</option>
              <option value="BILL_OF_SUPPLY">Bill of Supply</option>
              <option value="CREDIT_NOTE">Credit Note</option>
              <option value="DEBIT_NOTE">Debit Note</option>
            </select>
          </div>
          <div className="field"><label>Invoice date</label>
            <input className="edit" type="date" value={form.invoice_date} onChange={(e) => setField("invoice_date", e.target.value)} />
          </div>
          <div className="field"><label>GST rate preset</label>
            <select className="edit" value={form.gst_preset} onChange={(e) => setField("gst_preset", e.target.value)}>
              {(meta.presets || []).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
            </select>
          </div>
        </div>
        {(form.invoice_type === "CREDIT_NOTE" || form.invoice_type === "DEBIT_NOTE") && (
          <div className="row" style={{ marginTop: 10 }}>
            <div className="field"><label>Original tax invoice (GSTR-1 CDNR)</label>
              <select className="edit" value={form.original_invoice_id} onChange={(e) => {
                const o = originals.find((x) => String(x.id) === e.target.value);
                setForm((f) => ({
                  ...f,
                  original_invoice_id: e.target.value,
                  party_id: o?.party_id || f.party_id,
                  place_of_supply: o?.place_of_supply || f.place_of_supply,
                  gst_preset: o?.gst_preset || f.gst_preset,
                }));
              }}>
                <option value="">Select original invoice</option>
                {originals.map((o) => (
                  <option key={o.id} value={o.id}>{o.number} · {o.invoice_date_in || o.invoice_date} · {o.party_name}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <h3>2. Customer and place of supply</h3>
        <div className="row">
          <div className="field"><label>Bill to (customer)</label>
            <select className="edit" value={form.party_id} onChange={(e) => {
              const p = parties.find((x) => String(x.id) === e.target.value);
              setForm((f) => ({ ...f, party_id: e.target.value, place_of_supply: p ? (p.place_of_supply || p.state_code) : f.place_of_supply }));
            }}>
              <option value="">Select customer</option>
              {parties.map((p) => <option key={p.id} value={p.id}>{p.name} {p.gstin ? "· " + p.gstin : "· Unregistered"}{p.sez ? " · SEZ" : ""}</option>)}
            </select>
          </div>
          <div className="field"><label>Place of supply (State)</label>
            <select className="edit" value={form.place_of_supply} onChange={(e) => setField("place_of_supply", e.target.value)}>
              <option value="">Select</option>
              {(meta.states || []).map((s) => <option key={s.code} value={s.code}>{s.code} - {s.name}</option>)}
            </select>
          </div>
          <div className="field"><label>Reverse charge</label>
            <select className="edit" value={form.reverse_charge ? "Y" : "N"} onChange={(e) => setField("reverse_charge", e.target.value === "Y")}>
              <option value="N">No — supplier pays GST</option>
              <option value="Y">Yes — recipient pays GST</option>
            </select>
          </div>
          <div className="field"><label>Supply type (calculated)</label>
            <input className="calc" readOnly value={preview ? `${SUPPLY_LABEL[preview.supply_type] || preview.supply_type} · seller ${seller?.state_code || ""} vs POS ${form.place_of_supply}` : ""} />
          </div>
        </div>
        {party && (
          <p className="hint" style={{ marginBottom: 0 }}>
            {party.gstin ? `GSTIN ${party.gstin}` : "Unregistered person (B2C)"} · {party.city || ""} {party.state_code || ""}
            {party.sez ? " · SEZ unit" : ""}
          </p>
        )}
        {supplyHint && <p className="hint" style={{ marginBottom: 0 }}>{supplyHint}</p>}
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <h3>3. Line items</h3>
        <p className="hint">{taxHint} HSN/SAC needs at least {preview?.hsn_digits || 4} digits for this AATO.</p>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Item / Service</th><th>HSN/SAC</th><th>UQC</th><th>Qty</th><th>Rate</th><th>Discount</th>
                <th>Taxable</th>{intra ? <><th>CGST</th><th>SGST</th></> : <th>IGST</th>}<th>Total</th><th></th>
              </tr>
            </thead>
            <tbody>
              {form.lines.map((ln, i) => {
                const c = preview?.lines?.[i];
                const custom = ln.custom || ln.item_id === "<<CUSTOM>>";
                return (
                  <tr key={i}>
                    <td>
                      <select className="edit" value={custom ? "<<CUSTOM>>" : ln.item_id} onChange={(e) => {
                        if (e.target.value === "<<CUSTOM>>") setLine(i, { item_id: "<<CUSTOM>>", custom: true });
                        else {
                          const it = items.find((x) => String(x.id) === e.target.value);
                          setLine(i, { item_id: e.target.value, custom: false, description: it?.description || "", hsn_sac: it?.hsn_sac || "", unit: it?.unit || "NOS", rate: it?.rate || 0 });
                        }
                      }}>
                        <option value="">Select</option>
                        <option value="<<CUSTOM>>">&lt;&lt; CUSTOM ENTRY &gt;&gt;</option>
                        {items.map((it) => <option key={it.id} value={it.id}>{it.code} — {it.description}</option>)}
                      </select>
                      {custom && <input className="edit" style={{ marginTop: 4 }} placeholder="Description" value={ln.description} onChange={(e) => setLine(i, { description: e.target.value, custom: true })} />}
                    </td>
                    <td>{custom ? <input className="edit" value={ln.hsn_sac} onChange={(e) => setLine(i, { hsn_sac: e.target.value })} /> : <span className="calc" style={{ display: "block", padding: 6 }}>{ln.hsn_sac}</span>}</td>
                    <td>{custom ? <input className="edit" value={ln.unit} onChange={(e) => setLine(i, { unit: e.target.value })} /> : ln.unit}</td>
                    <td><input className="edit" type="number" value={ln.qty} onChange={(e) => setLine(i, { qty: e.target.value })} style={{ width: 80 }} /></td>
                    <td>{custom ? <input className="edit" type="number" value={ln.rate} onChange={(e) => setLine(i, { rate: e.target.value })} style={{ width: 100 }} /> : <span className="calc">{inr(ln.rate)}</span>}</td>
                    <td><input className="edit" type="number" value={ln.discount} onChange={(e) => setLine(i, { discount: e.target.value })} style={{ width: 80 }} /></td>
                    <td className="calc">{c ? inr(c.taxable_value) : ""}</td>
                    {intra ? <><td className="calc">{c ? inr(c.cgst) : ""}</td><td className="calc">{c ? inr(c.sgst) : ""}</td></> : <td className="calc">{c ? inr(c.igst) : ""}</td>}
                    <td className="calc">{c ? inr(c.total) : ""}</td>
                    <td><button className="btn secondary" type="button" onClick={() => setForm((f) => ({ ...f, lines: f.lines.filter((_, idx) => idx !== i) }))}>Remove</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="toolbar" style={{ marginTop: 8, marginBottom: 0 }}>
          <button className="btn secondary" type="button" onClick={() => setForm((f) => ({ ...f, lines: [...f.lines, emptyLine()] }))}>Add line</button>
          <div className="field" style={{ maxWidth: 140 }}><label>Round off</label>
            <input className="edit" type="number" value={form.round_off} onChange={(e) => setField("round_off", e.target.value)} />
          </div>
        </div>
      </div>

      <div className="split">
        <div className="card">
          <h3>4. Notes</h3>
          <textarea className="edit" rows={4} value={form.notes} onChange={(e) => setField("notes", e.target.value)} placeholder="Payment terms, delivery note, or any remark printed on the invoice" />
        </div>
        <div className="card">
          <h3>Tax summary (calculated)</h3>
          <p>Taxable <b className="calc" style={{ padding: "2px 6px" }}>{inr(preview?.taxable_value)}</b></p>
          {intra
            ? <p>CGST {inr(preview?.cgst)} · SGST {inr(preview?.sgst)}</p>
            : <p>IGST {inr(preview?.igst)}</p>}
          <p>Total <b>{inr(preview?.total)}</b></p>
          <p className="hint">{preview?.einvoice_required ? "E-invoice required: generate IRN after issue (AATO at or above Rs 5 Cr, B2B tax invoice)." : "E-invoice is not mandatory for this document."}</p>
          <button className="btn" onClick={save}>{id ? "Save changes" : "Issue invoice"}</button>
        </div>
      </div>
    </div>
  );
}
