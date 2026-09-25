# GST Invoice & Tax Compliance Platform

Production-ready web application for Indian GST invoicing, e-invoice (IRN) sandbox, GSTR-1 / GSTR-3B draft, and ITC reconciliation.

## What is included

- Multi-GSTIN company profile, roles (Owner / Accountant / Viewer / CA)
- Customer and vendor masters with GSTIN checksum validation
- Product / service catalog with HSN/SAC
- Tax Invoice, Bill of Supply, Credit Note, Debit Note
- Live GST calculation: Regular intra (CGST+SGST), Regular inter (IGST), Composition (no GST on invoice), Exempt
- Single-click GST rate preset that recalculates unlocked invoices
- Custom Mode line items (`<< CUSTOM ENTRY >>`)
- E-invoice GST INV-01 JSON + mock IRP (IRN, Ack, QR)
- Auto-draft GSTR-1 tables (B2B, B2C, HSN, document summary) and GSTR-3B
- GSTR-1 vs IRN and GSTR-2B vs purchase register reconciliation
- Printable invoice, CSV / JSON export, audit log

## Quick start

```bash
# Python API dependencies
pip3 install --break-system-packages -r backend/requirements.txt

# Frontend dependencies
npm install --prefix frontend

# Run API (8000) + Vite UI (5173) with /api reverse proxy
npm start
```

Open http://localhost:5173

Demo login:

- owner@aarohi.example / Owner@123
- accounts@aarohi.example / Acct@123
- viewer@aarohi.example / View@123
- ca@aarohi.example / CA@12345

Seed company: Aarohi Digital Services Pvt Ltd (PAN AABCA1234C), Karnataka + Maharashtra GSTINs, sample invoices, purchases and GSTR-2B rows.

## Demo flow

1. Sign in as owner.
2. Open **New invoice**, pick Deccan Healthcare (intra-state) or Nimbus Retail (inter-state).
3. Select a catalog item (only Qty is editable) or `<< CUSTOM ENTRY >>`.
4. Change **GST rate preset** and watch CGST/SGST/IGST split and totals (green cells).
5. Issue invoice, then **Generate IRN (sandbox)**.
6. Open **Returns** for the current MMYYYY period — GSTR-1 B2B / HSN is auto-drafted. Download JSON.
7. Open **Reconciliation** — GSTR-1 vs IRN and GSTR-2B vs books (seeded mismatches).

Organisation → **Apply preset** recalculates all unlocked invoices that do not yet have an IRN.

## Project layout

```text
backend/app/          FastAPI API, SQLAlchemy models, GST engine
backend/app/gst_engine.py   Tax math (must-correct rules)
backend/app/einvoice.py     INV-01 + mock IRP
backend/app/returns.py      GSTR-1 / 3B / reco
frontend/src/         React + Vite UI
data/gst.db           SQLite (created on first run)
```

SQLite is used for a zero-ops v1 install. Swap `GST_DB` / SQLAlchemy URL to PostgreSQL without changing models.

## Tax rules implemented

- Regular + Inter-State → IGST only
- Regular + Intra-State → CGST + SGST (half of slab)
- Composition → Bill of Supply, no GST charged to customer
- Place of supply vs supplier state code drives supply type
- Reverse charge flag on invoice
- HSN digit check from AATO (4 digits default, 6 if AATO > Rs 5 Cr)
- E-invoice required when AATO >= Rs 5 Cr and buyer GSTIN is present
- 30-day IRN window enforced when AATO >= Rs 10 Cr
- IRN cancel allowed within 24 hours (sandbox)

## Connect a real GSP later

The app is API-ready. Today `einvoice.py` uses mock IRP when GSP env is empty.

Set:

```bash
export GSP_BASE_URL=https://your-gsp.example/einvoice
export GSP_API_KEY=your-gsp-key
```

Then replace `mock_irn()` in `backend/app/einvoice.py` with an HTTP POST of the INV-01 payload to the GSP, store `Irn`, `AckNo`, `AckDt`, `SignedQRCode` on the invoice (same fields already persist). GSTN public GSTIN search can replace `/api/gstin/lookup`.

Live GST portal filing without a GSP is out of scope for v1; JSON export is intended for offline GST portal upload.

## Tests

```bash
python3 -m pytest backend/tests -q
```

## Security notes

- JWT auth with role checks
- GSTIN checksum validation
- Do not commit real GSP keys; use environment variables
- For production, move SQLite to PostgreSQL, put the API behind TLS, and encrypt PAN / bank columns at rest
