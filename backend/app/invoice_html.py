from .gst_engine import STATES, amount_in_words, format_inr


def invoice_html(inv, gstin, company, lines, qr_png="", original=None):
    intra = inv.supply_type == "INTRA"
    sez = bool(getattr(inv.party, "sez", False)) if getattr(inv, "party", None) else False
    title = {
        "TAX_INVOICE": "TAX INVOICE",
        "BILL_OF_SUPPLY": "BILL OF SUPPLY",
        "CREDIT_NOTE": "CREDIT NOTE",
        "DEBIT_NOTE": "DEBIT NOTE",
    }.get(inv.invoice_type, "INVOICE")
    logo = f'<img src="{company.logo_data}" alt="logo" style="max-height:56px"/>' if company.logo_data else ""
    qr = f'<img src="{qr_png}" alt="IRN QR" style="width:110px;height:110px"/>' if qr_png else ""
    inv_date = inv.invoice_date.strftime("%d-%m-%Y") if inv.invoice_date else ""
    irn_dt = inv.irn_date.strftime("%d-%m-%Y %H:%M") if inv.irn_date else ""
    irn_block = ""
    if inv.irn:
        irn_block = f"""
        <div class="irn">
          {qr}
          <div>
            <div><b>IRN</b><br/>{inv.irn}</div>
            <div style="margin-top:6px"><b>Ack No.</b> {inv.ack_no or "-"}</div>
            <div><b>Ack Date</b> {irn_dt}</div>
          </div>
        </div>"""
    elif inv.invoice_type == "TAX_INVOICE" and inv.party_gstin:
        irn_block = '<div class="irn warn">e-Invoice IRN not generated. Generate IRN before sharing this B2B tax invoice.</div>'
    rows = ""
    for i, ln in enumerate(lines, 1):
        tax_cols = (
            f"<td class='r'>{ln.cgst_rate:.2f}</td><td class='r'>{format_inr(ln.cgst)}</td>"
            f"<td class='r'>{ln.sgst_rate:.2f}</td><td class='r'>{format_inr(ln.sgst)}</td>"
            if intra
            else f"<td class='r'>{ln.igst_rate:.2f}</td><td class='r'>{format_inr(ln.igst)}</td>"
        )
        custom = " <span class='custom'>CUSTOM</span>" if ln.custom else ""
        rows += f"""<tr>
          <td>{i}</td><td>{ln.description}{custom}</td>
          <td>{ln.hsn_sac}</td><td>{ln.unit}</td>
          <td class="r">{ln.qty:g}</td><td class="r">{format_inr(ln.rate)}</td>
          <td class="r">{format_inr(ln.taxable_value)}</td>{tax_cols}<td class="r">{format_inr(ln.total)}</td>
        </tr>"""
    tax_head = "<th>CGST %</th><th>CGST</th><th>SGST %</th><th>SGST</th>" if intra else "<th>IGST %</th><th>IGST</th>"
    tax_sum = (
        f"<tr><td>CGST</td><td class='r green'>{format_inr(inv.cgst)}</td></tr>"
        f"<tr><td>SGST / UTGST</td><td class='r green'>{format_inr(inv.sgst)}</td></tr>"
        if intra
        else f"<tr><td>IGST</td><td class='r green'>{format_inr(inv.igst)}</td></tr>"
    )
    orig = ""
    if original:
        orig_dt = original.invoice_date.strftime("%d-%m-%Y") if original.invoice_date else ""
        orig = f"<div><b>Against original invoice</b> {original.number} dated {orig_dt}</div>"
    elif inv.original_invoice_id:
        orig = f"<div><b>Against original invoice id</b> {inv.original_invoice_id}</div>"
    rcm = "Yes — tax payable on reverse charge" if inv.reverse_charge else "No"
    sez_line = "SEZ supply (IGST)" if sez else ""
    words = amount_in_words(inv.total)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>{inv.number}</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; color:#1a1a1a; margin:0; background:#fff; }}
  .page {{ max-width:900px; margin:0 auto; padding:28px; }}
  h1 {{ font-size:20px; letter-spacing:1px; margin:0; }}
  .muted {{ color:#666; font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th, td {{ border:1px solid #cfcfcf; padding:6px 8px; font-size:12px; }}
  th {{ background:#f4f4f4; text-align:left; }}
  .r {{ text-align:right; }}
  .head {{ display:flex; justify-content:space-between; gap:16px; margin-bottom:16px; }}
  .box {{ border:1px solid #cfcfcf; padding:10px 12px; flex:1; }}
  .irn {{ display:flex; gap:12px; border:1px dashed #888; padding:8px; margin:12px 0; font-size:11px; word-break:break-all; }}
  .irn.warn {{ background:#fff8e1; border-color:#efd27a; display:block; }}
  .totals {{ width:320px; margin-left:auto; margin-top:8px; }}
  .green {{ background:#e8f6ee; }}
  .custom {{ background:#fff3cd; font-size:10px; padding:1px 4px; }}
  .foot {{ margin-top:24px; font-size:11px; color:#555; }}
  .words {{ margin-top:10px; font-size:12px; }}
  .bar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
  .sig {{ margin-top:36px; display:flex; justify-content:space-between; }}
  .sig .box {{ border:0; padding:0; min-height:72px; }}
  .rule {{ font-size:10px; color:#777; margin-top:16px; border-top:1px solid #eee; padding-top:8px; }}
  @media print {{ .noprint {{ display:none }} body {{ margin:0 }} }}
</style></head>
<body>
<div class="page">
  <div class="bar noprint">
    <span class="muted">Rule 46 GST tax document</span>
    <button onclick="window.print()">Print / Save PDF</button>
  </div>
  <div class="head">
    <div>
      {logo}
      <h1>{company.trade_name}</h1>
      <div class="muted">{company.legal_name}</div>
      <div class="muted">{gstin.address1} {gstin.address2}<br/>{gstin.city} - {gstin.pincode}, {STATES.get(gstin.state_code,"")}</div>
      <div><b>GSTIN:</b> {gstin.gstin} &nbsp; <b>PAN:</b> {company.pan}</div>
    </div>
    <div style="text-align:right">
      <h1>{title}</h1>
      <div><b>Invoice No.</b> {inv.number}</div>
      <div><b>Date</b> {inv_date}</div>
      <div><b>Place of Supply</b> {inv.place_of_supply} - {STATES.get(inv.place_of_supply or "","")}</div>
      <div><b>Supply</b> {inv.supply_type}{(" · " + sez_line) if sez_line else ""}</div>
      <div><b>Reverse Charge</b> {rcm}</div>
      {orig}
    </div>
  </div>
  {irn_block}
  <div class="head">
    <div class="box">
      <div class="muted">Bill To (Recipient)</div>
      <b>{inv.party_name}</b><br/>
      {inv.party_address}<br/>
      State: {STATES.get(inv.party_state or "", inv.party_state or "")} ({inv.party_state or "-"})<br/>
      GSTIN: {inv.party_gstin or "Unregistered person"}
    </div>
    <div class="box">
      <div class="muted">Bank Details</div>
      {company.bank_name}<br/>
      A/c {company.bank_account}<br/>
      IFSC {company.bank_ifsc}<br/>
      {company.bank_branch}
    </div>
  </div>
  <table>
    <thead><tr>
      <th>#</th><th>Description of goods / services</th><th>HSN/SAC</th><th>UQC</th><th>Qty</th><th>Rate</th><th>Taxable value</th>
      {tax_head}<th>Total</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <table class="totals">
    <tr><td>Taxable value</td><td class="r green">{format_inr(inv.taxable_value)}</td></tr>
    {tax_sum}
    <tr><td>Round off</td><td class="r">{format_inr(inv.round_off)}</td></tr>
    <tr><td><b>Total invoice value</b></td><td class="r green"><b>{format_inr(inv.total)}</b></td></tr>
  </table>
  <div class="words"><b>Total invoice value in words:</b> {words}</div>
  <div class="foot">
    <div>{company.terms}</div>
    <div class="sig">
      <div class="box"><span class="muted">Receiver's signature</span></div>
      <div class="box" style="text-align:right">For {company.legal_name}<br/><br/><br/>Authorised Signatory</div>
    </div>
    <div class="rule">This is a computer-generated tax invoice under Rule 46 of the CGST Rules, 2017. HSN/SAC, place of supply, GSTIN of supplier and recipient, tax rate and amount are shown as required.</div>
  </div>
</div>
</body></html>"""
