from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
import csv
import json
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .database import Base, engine, get_db
from . import models, schemas
from .security import hash_password, verify_password, create_token, current_user
from .gst_engine import (
    STATES, PRESETS, validate_gstin, validate_pan, state_from_gstin, supply_type,
    calc_invoice, preset_by_code, period_of, fy_label, due_dates, default_invoice_type,
    EINVOICE_THRESHOLD, hsn_required_digits, period_label, amount_in_words, format_inr,
)
from .einvoice import (
    sandbox_mode, build_inv01, mock_irn, validate_einvoice_window, einvoice_required,
    qr_png_from_text, einvoice_status_of,
)
from .returns import gstr1_tables, gstr3b_summary, reconcile_gstr1_vs_irn, reconcile_2b
from .serialize import (
    company_out, gstin_out, user_out, party_out, item_out, invoice_out, purchase_out,
)
from .invoice_html import invoice_html
from .seed import seed

app = FastAPI(title="GST Invoice & Tax Compliance", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def repair_einvoice_flags():
    from .database import SessionLocal
    db = SessionLocal()
    try:
        aatos = {c.id: c.aato for c in db.query(models.Company).all()}
        changed = False
        for inv in db.query(models.Invoice).all():
            status = einvoice_status_of(inv, aatos.get(inv.company_id, 0))
            if inv.einvoice_status != status:
                inv.einvoice_status = status
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    seed()
    repair_einvoice_flags()


def audit(db: Session, user, action, entity="", entity_id=None, detail=""):
    db.add(models.AuditLog(
        company_id=user.company_id if user else None,
        user_id=user.id if user else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        detail=detail[:2000] if detail else "",
    ))


def cid(user):
    return user.company_id


def company_of(db: Session, user) -> models.Company:
    c = db.get(models.Company, user.company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return c


def gstin_of(db: Session, user, gstin_id: int) -> models.Gstin:
    g = db.get(models.Gstin, gstin_id)
    if not g or g.company_id != user.company_id:
        raise HTTPException(404, "GSTIN not found")
    return g


def next_number(gstin: models.Gstin, invoice_type: str) -> str:
    mapping = {
        "TAX_INVOICE": ("invoice_prefix", "next_number"),
        "CREDIT_NOTE": ("cn_prefix", "cn_next"),
        "DEBIT_NOTE": ("dn_prefix", "dn_next"),
        "BILL_OF_SUPPLY": ("bos_prefix", "bos_next"),
    }
    pfield, nfield = mapping.get(invoice_type, ("invoice_prefix", "next_number"))
    n = getattr(gstin, nfield)
    number = f"{getattr(gstin, pfield)}{n:04d}"
    setattr(gstin, nfield, n + 1)
    return number


def apply_lines(db, inv, payload: schemas.InvoiceIn, gstin: models.Gstin, company: models.Company):
    preset = preset_by_code(payload.gst_preset)
    if company.scheme == "COMPOSITION" or preset.get("composition"):
        inv.scheme = "COMPOSITION"
        if inv.invoice_type == "TAX_INVOICE":
            inv.invoice_type = "BILL_OF_SUPPLY"
    else:
        inv.scheme = "REGULAR"
    pos = payload.place_of_supply or inv.party_state or gstin.state_code
    inv.place_of_supply = pos
    party = db.get(models.Party, inv.party_id) if inv.party_id else None
    sez = bool(party.sez) if party else False
    inv.supply_type = supply_type(gstin.state_code, pos, is_sez=sez)
    inv.gst_preset = payload.gst_preset
    inv.reverse_charge = payload.reverse_charge
    inv.round_off = payload.round_off or 0
    inv.custom_mode = payload.custom_mode
    inv.notes = payload.notes or ""
    if payload.original_invoice_id:
        orig = db.get(models.Invoice, payload.original_invoice_id)
        if orig and orig.company_id == company.id:
            inv.original_invoice_id = orig.id
    if payload.due_date:
        inv.due_date = payload.due_date
    if payload.invoice_date:
        inv.invoice_date = payload.invoice_date
        inv.period = period_of(payload.invoice_date)
        inv.fy = fy_label(payload.invoice_date)

    digits = hsn_required_digits(company.aato)
    raw_lines = []
    for ln in payload.lines:
        if not ln.item_id and not ln.custom and not ln.description:
            continue
        desc, hsn, unit, rate, item_id, custom = ln.description, ln.hsn_sac, ln.unit, ln.rate, ln.item_id, ln.custom
        if ln.item_id and not ln.custom:
            item = db.get(models.Item, ln.item_id)
            if not item or item.company_id != company.id:
                raise HTTPException(400, "Catalog item not found")
            desc = item.description
            hsn = item.hsn_sac
            unit = item.unit
            rate = item.rate
            custom = False
        else:
            custom = True
            inv.custom_mode = True
            if not desc:
                raise HTTPException(400, "Custom line requires Description")
        if hsn and len(hsn) < digits and inv.invoice_type != "BILL_OF_SUPPLY":
            raise HTTPException(400, f"HSN/SAC must be at least {digits} digits for this turnover")
        raw_lines.append({
            "item_id": item_id if not custom else None,
            "custom": custom,
            "description": desc,
            "hsn_sac": hsn,
            "unit": unit or "NOS",
            "qty": ln.qty,
            "rate": rate,
            "discount": ln.discount or 0,
        })
    if not raw_lines:
        raise HTTPException(400, "Add at least one line item")
    computed = calc_invoice(raw_lines, preset, inv.supply_type, inv.round_off)
    db.query(models.LineItem).filter(models.LineItem.invoice_id == inv.id).delete()
    for src, c in zip(raw_lines, computed["lines"]):
        db.add(models.LineItem(
            invoice_id=inv.id,
            item_id=src["item_id"],
            custom=src["custom"],
            description=src["description"],
            hsn_sac=src["hsn_sac"],
            unit=src["unit"],
            qty=c["qty"],
            rate=c["rate"],
            discount=c["discount"],
            taxable_value=c["taxable_value"],
            gst_rate=c["gst_rate"],
            cgst_rate=c["cgst_rate"],
            sgst_rate=c["sgst_rate"],
            igst_rate=c["igst_rate"],
            cgst=c["cgst"],
            sgst=c["sgst"],
            igst=c["igst"],
            total=c["total"],
        ))
    inv.taxable_value = computed["taxable_value"]
    inv.cgst = computed["cgst"]
    inv.sgst = computed["sgst"]
    inv.igst = computed["igst"]
    inv.total = computed["total"]
    req = einvoice_required(inv.party_gstin, company.aato, inv.invoice_type, inv.scheme)
    if inv.irn:
        inv.einvoice_status = "GENERATED"
    elif req:
        inv.einvoice_status = "REQUIRED"
    else:
        inv.einvoice_status = "NOT_REQUIRED"
    return computed


@app.get("/api/health")
def health():
    return {"ok": True, "sandbox": sandbox_mode()}


@app.get("/api/meta")
def meta():
    return {
        "states": [{"code": k, "name": v} for k, v in STATES.items()],
        "presets": PRESETS,
        "roles": ["OWNER", "ACCOUNTANT", "VIEWER", "CA"],
        "invoice_types": ["TAX_INVOICE", "BILL_OF_SUPPLY", "CREDIT_NOTE", "DEBIT_NOTE"],
        "einvoice_threshold": EINVOICE_THRESHOLD,
        "sandbox": sandbox_mode(),
    }


@app.post("/api/auth/login")
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email.strip().lower()).first()
    if not user:
        user = db.query(models.User).filter(models.User.email == body.email.strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user)
    company = db.get(models.Company, user.company_id)
    return {"token": token, "user": user_out(user), "company": company_out(company)}


@app.get("/api/me")
def me(user=Depends(current_user), db: Session = Depends(get_db)):
    company = company_of(db, user)
    return {"user": user_out(user), "company": company_out(company)}


@app.get("/api/company")
def get_company(user=Depends(current_user), db: Session = Depends(get_db)):
    return company_out(company_of(db, user))


@app.put("/api/company")
def update_company(body: schemas.CompanyIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in ("OWNER", "ACCOUNTANT"):
        raise HTTPException(403, "Insufficient permissions")
    c = company_of(db, user)
    data = body.model_dump(exclude_unset=True)
    if "pan" in data and data["pan"]:
        ok, pan = validate_pan(data["pan"])
        if not ok:
            raise HTTPException(400, pan)
        data["pan"] = pan
    for k, v in data.items():
        setattr(c, k, v)
    if data.get("scheme") == "COMPOSITION":
        pass
    audit(db, user, "UPDATE", "COMPANY", c.id, "Updated company profile")
    db.commit()
    db.refresh(c)
    return company_out(c)


@app.get("/api/gstins")
def list_gstins(user=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.Gstin).filter(models.Gstin.company_id == cid(user)).all()
    return [gstin_out(g) for g in rows]


@app.post("/api/gstins")
def create_gstin(body: schemas.GstinIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in ("OWNER", "ACCOUNTANT"):
        raise HTTPException(403, "Insufficient permissions")
    ok, g = validate_gstin(body.gstin)
    if not ok:
        raise HTTPException(400, g)
    exists = db.query(models.Gstin).filter(models.Gstin.gstin == g).first()
    if exists:
        raise HTTPException(400, "GSTIN already exists")
    company = company_of(db, user)
    if g[2:12] != company.pan:
        raise HTTPException(400, "GSTIN PAN segment must match company PAN")
    state = body.state_code or g[:2]
    row = models.Gstin(
        company_id=company.id,
        gstin=g,
        legal_name=body.legal_name,
        trade_name=body.trade_name or body.legal_name,
        address1=body.address1,
        address2=body.address2,
        city=body.city,
        state_code=state,
        pincode=body.pincode,
        email=body.email,
        phone=body.phone,
        invoice_prefix=body.invoice_prefix or "INV",
        is_primary=body.is_primary,
    )
    db.add(row)
    audit(db, user, "CREATE", "GSTIN", None, g)
    db.commit()
    db.refresh(row)
    return gstin_out(row)


@app.put("/api/gstins/{gstin_id}")
def update_gstin(gstin_id: int, body: schemas.GstinIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in ("OWNER", "ACCOUNTANT"):
        raise HTTPException(403, "Insufficient permissions")
    row = gstin_of(db, user, gstin_id)
    ok, g = validate_gstin(body.gstin)
    if not ok:
        raise HTTPException(400, g)
    row.gstin = g
    row.legal_name = body.legal_name
    row.trade_name = body.trade_name or body.legal_name
    row.address1 = body.address1
    row.address2 = body.address2
    row.city = body.city
    row.state_code = body.state_code or g[:2]
    row.pincode = body.pincode
    row.email = body.email
    row.phone = body.phone
    row.invoice_prefix = body.invoice_prefix or row.invoice_prefix
    row.is_primary = body.is_primary
    db.commit()
    db.refresh(row)
    return gstin_out(row)


@app.get("/api/users")
def list_users(user=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.User).filter(models.User.company_id == cid(user)).all()
    return [user_out(u) for u in rows]


@app.post("/api/users")
def create_user(body: schemas.UserIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "OWNER":
        raise HTTPException(403, "Only owner can add users")
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(400, "Email already in use")
    if body.role not in ("OWNER", "ACCOUNTANT", "VIEWER", "CA"):
        raise HTTPException(400, "Invalid role")
    row = models.User(
        company_id=cid(user),
        name=body.name,
        email=body.email.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(row)
    audit(db, user, "CREATE", "USER", None, body.email)
    db.commit()
    db.refresh(row)
    return user_out(row)


@app.get("/api/parties")
def list_parties(kind: Optional[str] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(models.Party).filter(models.Party.company_id == cid(user), models.Party.active == True)
    if kind:
        q = q.filter(models.Party.kind == kind)
    return [party_out(p) for p in q.order_by(models.Party.name).all()]


@app.post("/api/parties")
def create_party(body: schemas.PartyIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    gstin = ""
    if body.gstin:
        ok, g = validate_gstin(body.gstin)
        if not ok:
            raise HTTPException(400, g)
        gstin = g
    state = body.state_code or (gstin[:2] if gstin else "")
    row = models.Party(
        company_id=cid(user),
        kind=body.kind or "CUSTOMER",
        name=body.name,
        trade_name=body.trade_name,
        gstin=gstin,
        pan=body.pan.upper() if body.pan else "",
        email=body.email,
        phone=body.phone,
        address1=body.address1,
        address2=body.address2,
        city=body.city,
        state_code=state,
        pincode=body.pincode,
        place_of_supply=body.place_of_supply or state,
        sez=body.sez,
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return party_out(row)


@app.put("/api/parties/{party_id}")
def update_party(party_id: int, body: schemas.PartyIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    row = db.get(models.Party, party_id)
    if not row or row.company_id != cid(user):
        raise HTTPException(404, "Party not found")
    gstin = ""
    if body.gstin:
        ok, g = validate_gstin(body.gstin)
        if not ok:
            raise HTTPException(400, g)
        gstin = g
    state = body.state_code or (gstin[:2] if gstin else "")
    row.kind = body.kind or row.kind
    row.name = body.name
    row.trade_name = body.trade_name
    row.gstin = gstin
    row.pan = body.pan.upper() if body.pan else ""
    row.email = body.email
    row.phone = body.phone
    row.address1 = body.address1
    row.address2 = body.address2
    row.city = body.city
    row.state_code = state
    row.pincode = body.pincode
    row.place_of_supply = body.place_of_supply or state
    row.sez = body.sez
    row.notes = body.notes
    db.commit()
    db.refresh(row)
    return party_out(row)


@app.get("/api/gstin/lookup")
def lookup_gstin(gstin: str, user=Depends(current_user)):
    ok, g = validate_gstin(gstin)
    if not ok:
        raise HTTPException(400, g)
    return {
        "gstin": g,
        "valid": True,
        "state_code": g[:2],
        "state_name": STATES.get(g[:2], ""),
        "pan": g[2:12],
        "name": "",
        "address": "",
        "hint": "Sandbox: checksum valid. Connect a GSP to auto-fill legal name and address.",
    }


@app.get("/api/items")
def list_items(user=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.Item).filter(models.Item.company_id == cid(user), models.Item.active == True).order_by(models.Item.description).all()
    return [item_out(i) for i in rows]


@app.post("/api/items")
def create_item(body: schemas.ItemIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    row = models.Item(company_id=cid(user), **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return item_out(row)


@app.put("/api/items/{item_id}")
def update_item(item_id: int, body: schemas.ItemIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    row = db.get(models.Item, item_id)
    if not row or row.company_id != cid(user):
        raise HTTPException(404, "Item not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return item_out(row)


@app.post("/api/invoices/preview")
def preview_invoice(body: schemas.InvoiceIn, user=Depends(current_user), db: Session = Depends(get_db)):
    company = company_of(db, user)
    gstin = gstin_of(db, user, body.gstin_id)
    party = db.get(models.Party, body.party_id) if body.party_id else None
    party_state = ""
    party_gstin = ""
    if party and party.company_id == cid(user):
        party_state = party.state_code
        party_gstin = party.gstin
    pos = body.place_of_supply or (party.place_of_supply if party else "") or gstin.state_code
    sez = bool(party.sez) if party else False
    supply = supply_type(gstin.state_code, pos, is_sez=sez)
    preset = preset_by_code(body.gst_preset)
    raw = []
    for ln in body.lines:
        if not ln.item_id and not ln.custom and not ln.description:
            continue
        rate, desc, hsn, unit = ln.rate, ln.description, ln.hsn_sac, ln.unit
        if ln.item_id and not ln.custom:
            item = db.get(models.Item, ln.item_id)
            if item:
                rate, desc, hsn, unit = item.rate, item.description, item.hsn_sac, item.unit
        raw.append({"qty": ln.qty, "rate": rate, "discount": ln.discount or 0, "description": desc, "hsn_sac": hsn, "unit": unit})
    computed = calc_invoice(raw, preset, supply, body.round_off or 0)
    inv_type = body.invoice_type
    if company.scheme == "COMPOSITION" or preset.get("composition"):
        inv_type = default_invoice_type("COMPOSITION") if body.invoice_type == "TAX_INVOICE" else body.invoice_type
    return {
        **computed,
        "place_of_supply": pos,
        "place_of_supply_name": STATES.get(pos, ""),
        "invoice_type": inv_type,
        "scheme": "COMPOSITION" if (company.scheme == "COMPOSITION" or preset.get("composition")) else "REGULAR",
        "einvoice_required": einvoice_required(party_gstin, company.aato, inv_type, company.scheme),
        "hsn_digits": hsn_required_digits(company.aato),
        "party_state": party_state,
        "seller_state": gstin.state_code,
        "preset": preset,
        "sez": sez,
        "composition": company.scheme == "COMPOSITION" or preset.get("composition"),
    }


def fill_party(inv: models.Invoice, party: Optional[models.Party]):
    if not party:
        return
    inv.party_id = party.id
    inv.party_name = party.name
    inv.party_gstin = party.gstin or ""
    inv.party_address = ", ".join([x for x in [party.address1, party.city, party.pincode] if x])
    inv.party_state = party.state_code or ""
    if not inv.place_of_supply:
        inv.place_of_supply = party.place_of_supply or party.state_code or ""


@app.get("/api/invoices")
def list_invoices(
    gstin_id: Optional[int] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    qry = db.query(models.Invoice).options(joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)).filter(
        models.Invoice.company_id == cid(user)
    )
    if gstin_id:
        qry = qry.filter(models.Invoice.gstin_id == gstin_id)
    if period:
        qry = qry.filter(models.Invoice.period == period)
    if status:
        qry = qry.filter(models.Invoice.status == status)
    if q:
        like = f"%{q}%"
        qry = qry.filter(
            (models.Invoice.number.ilike(like)) | (models.Invoice.party_name.ilike(like)) | (models.Invoice.party_gstin.ilike(like))
        )
    rows = qry.order_by(models.Invoice.invoice_date.desc(), models.Invoice.id.desc()).limit(500).all()
    aato = company_of(db, user).aato
    return [invoice_out(r, aato=aato) for r in rows]


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin), joinedload(models.Invoice.party)])
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    original = db.get(models.Invoice, inv.original_invoice_id) if inv.original_invoice_id else None
    return invoice_out(inv, aato=company_of(db, user).aato, original=original)


@app.post("/api/invoices")
def create_invoice(body: schemas.InvoiceIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    company = company_of(db, user)
    gstin = gstin_of(db, user, body.gstin_id)
    party = db.get(models.Party, body.party_id) if body.party_id else None
    if body.party_id and (not party or party.company_id != cid(user)):
        raise HTTPException(400, "Customer not found")
    inv_type = body.invoice_type
    preset = preset_by_code(body.gst_preset)
    if company.scheme == "COMPOSITION" or preset.get("composition"):
        if inv_type == "TAX_INVOICE":
            inv_type = "BILL_OF_SUPPLY"
    inv = models.Invoice(
        company_id=cid(user),
        gstin_id=gstin.id,
        invoice_type=inv_type,
        number=next_number(gstin, inv_type),
        invoice_date=body.invoice_date,
        due_date=body.due_date or (body.invoice_date + timedelta(days=15)),
        status="ISSUED",
        created_by=user.id,
        period=period_of(body.invoice_date),
        fy=fy_label(body.invoice_date),
        gst_preset=body.gst_preset,
        scheme=company.scheme,
    )
    fill_party(inv, party)
    db.add(inv)
    db.flush()
    apply_lines(db, inv, body, gstin, company)
    audit(db, user, "CREATE", "INVOICE", inv.id, inv.number)
    db.commit()
    inv = db.get(models.Invoice, inv.id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    return invoice_out(inv, aato=company.aato)


@app.put("/api/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: schemas.InvoiceIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    inv = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines)])
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    if inv.locked or inv.status == "CANCELLED":
        raise HTTPException(400, "Invoice is locked or cancelled")
    if inv.irn:
        raise HTTPException(400, "Cannot edit invoice after IRN generation")
    company = company_of(db, user)
    gstin = gstin_of(db, user, body.gstin_id)
    party = db.get(models.Party, body.party_id) if body.party_id else None
    inv.gstin_id = gstin.id
    inv.invoice_type = body.invoice_type
    fill_party(inv, party)
    apply_lines(db, inv, body, gstin, company)
    audit(db, user, "UPDATE", "INVOICE", inv.id, inv.number)
    db.commit()
    inv = db.get(models.Invoice, inv.id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    return invoice_out(inv, aato=company.aato)


@app.post("/api/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    inv = db.get(models.Invoice, invoice_id)
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    if inv.locked:
        raise HTTPException(400, "Period is locked")
    inv.status = "CANCELLED"
    if inv.irn:
        inv.einvoice_status = "CANCELLED"
        inv.cancel_reason = "Invoice cancelled"
    audit(db, user, "CANCEL", "INVOICE", inv.id, inv.number)
    db.commit()
    return {"ok": True}


@app.post("/api/invoices/{invoice_id}/duplicate")
def duplicate_invoice(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    src = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    if not src or src.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    company = company_of(db, user)
    gstin = src.gstin
    today = date.today()
    inv = models.Invoice(
        company_id=cid(user),
        gstin_id=src.gstin_id,
        party_id=src.party_id,
        invoice_type=src.invoice_type,
        number=next_number(gstin, src.invoice_type),
        invoice_date=today,
        due_date=today + timedelta(days=15),
        place_of_supply=src.place_of_supply,
        supply_type=src.supply_type,
        reverse_charge=src.reverse_charge,
        gst_preset=src.gst_preset,
        scheme=src.scheme,
        party_name=src.party_name,
        party_gstin=src.party_gstin,
        party_address=src.party_address,
        party_state=src.party_state,
        notes=src.notes,
        custom_mode=src.custom_mode,
        status="ISSUED",
        created_by=user.id,
        period=period_of(today),
        fy=fy_label(today),
    )
    db.add(inv)
    db.flush()
    body = schemas.InvoiceIn(
        gstin_id=src.gstin_id,
        party_id=src.party_id,
        invoice_type=src.invoice_type,
        invoice_date=today,
        place_of_supply=src.place_of_supply,
        reverse_charge=src.reverse_charge,
        gst_preset=src.gst_preset,
        notes=src.notes or "",
        round_off=src.round_off or 0,
        custom_mode=src.custom_mode,
        lines=[
            schemas.LineIn(
                item_id=ln.item_id,
                custom=ln.custom,
                description=ln.description,
                hsn_sac=ln.hsn_sac,
                unit=ln.unit,
                qty=ln.qty,
                rate=ln.rate,
                discount=ln.discount,
            )
            for ln in src.lines
        ],
    )
    apply_lines(db, inv, body, gstin, company)
    audit(db, user, "DUPLICATE", "INVOICE", inv.id, f"from {src.number}")
    db.commit()
    inv = db.get(models.Invoice, inv.id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    return invoice_out(inv, aato=company.aato)


@app.post("/api/invoices/{invoice_id}/credit-note")
def credit_note_from(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    src = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    if not src or src.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    if src.invoice_type in ("CREDIT_NOTE", "DEBIT_NOTE"):
        raise HTTPException(400, "Cannot issue a credit note against another note")
    company = company_of(db, user)
    gstin = src.gstin
    today = date.today()
    inv = models.Invoice(
        company_id=cid(user),
        gstin_id=src.gstin_id,
        party_id=src.party_id,
        invoice_type="CREDIT_NOTE",
        number=next_number(gstin, "CREDIT_NOTE"),
        invoice_date=today,
        due_date=today,
        place_of_supply=src.place_of_supply,
        supply_type=src.supply_type,
        reverse_charge=src.reverse_charge,
        gst_preset=src.gst_preset,
        scheme=src.scheme,
        party_name=src.party_name,
        party_gstin=src.party_gstin,
        party_address=src.party_address,
        party_state=src.party_state,
        notes=f"Credit note against {src.number}",
        custom_mode=src.custom_mode,
        original_invoice_id=src.id,
        status="ISSUED",
        created_by=user.id,
        period=period_of(today),
        fy=fy_label(today),
    )
    db.add(inv)
    db.flush()
    body = schemas.InvoiceIn(
        gstin_id=src.gstin_id,
        party_id=src.party_id,
        invoice_type="CREDIT_NOTE",
        invoice_date=today,
        place_of_supply=src.place_of_supply,
        reverse_charge=src.reverse_charge,
        gst_preset=src.gst_preset,
        notes=inv.notes,
        round_off=0,
        custom_mode=src.custom_mode,
        original_invoice_id=src.id,
        lines=[
            schemas.LineIn(
                item_id=ln.item_id,
                custom=ln.custom,
                description=ln.description,
                hsn_sac=ln.hsn_sac,
                unit=ln.unit,
                qty=ln.qty,
                rate=ln.rate,
                discount=ln.discount,
            )
            for ln in src.lines
        ],
    )
    apply_lines(db, inv, body, gstin, company)
    audit(db, user, "CREDIT_NOTE", "INVOICE", inv.id, f"against {src.number}")
    db.commit()
    inv = db.get(models.Invoice, inv.id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin), joinedload(models.Invoice.party)])
    return invoice_out(inv, aato=company.aato, original=src)


@app.post("/api/gst-preset/apply")
def apply_preset(code: str, gstin_id: Optional[int] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    preset = preset_by_code(code)
    company = company_of(db, user)
    q = db.query(models.Invoice).options(joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)).filter(
        models.Invoice.company_id == cid(user),
        models.Invoice.status != "CANCELLED",
        models.Invoice.locked == False,
        models.Invoice.irn == "",
    )
    if gstin_id:
        q = q.filter(models.Invoice.gstin_id == gstin_id)
    updated = 0
    for inv in q.all():
        gstin = inv.gstin
        inv.gst_preset = code
        body = schemas.InvoiceIn(
            gstin_id=inv.gstin_id,
            party_id=inv.party_id,
            invoice_type=inv.invoice_type,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            place_of_supply=inv.place_of_supply,
            reverse_charge=inv.reverse_charge,
            gst_preset=code,
            notes=inv.notes or "",
            round_off=inv.round_off or 0,
            custom_mode=inv.custom_mode,
            lines=[
                schemas.LineIn(
                    item_id=ln.item_id,
                    custom=ln.custom,
                    description=ln.description,
                    hsn_sac=ln.hsn_sac,
                    unit=ln.unit,
                    qty=ln.qty,
                    rate=ln.rate,
                    discount=ln.discount,
                )
                for ln in inv.lines
            ],
        )
        apply_lines(db, inv, body, gstin, company)
        updated += 1
    audit(db, user, "PRESET", "INVOICE", None, f"{code} applied to {updated} invoices")
    db.commit()
    return {"ok": True, "updated": updated, "preset": preset}


@app.get("/api/invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_invoice(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin), joinedload(models.Invoice.party)])
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    company = company_of(db, user)
    qr = qr_png_from_text(inv.signed_qr) if inv.signed_qr else ""
    original = db.get(models.Invoice, inv.original_invoice_id) if inv.original_invoice_id else None
    html = invoice_html(inv, inv.gstin, company, inv.lines, qr, original=original)
    return HTMLResponse(html)


@app.get("/api/invoices/{invoice_id}/einvoice-json")
def einvoice_json(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    company = company_of(db, user)
    sez = bool(getattr(inv.party, "sez", False)) if inv.party_id else False
    if inv.party_id and not getattr(inv, "party", None):
        p = db.get(models.Party, inv.party_id)
        sez = bool(p.sez) if p else False
    return build_inv01(inv, inv.gstin, company, inv.lines, sez=sez)


@app.post("/api/invoices/{invoice_id}/einvoice")
def generate_irn(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    inv = db.get(models.Invoice, invoice_id, options=[joinedload(models.Invoice.lines), joinedload(models.Invoice.gstin)])
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    if inv.status == "CANCELLED":
        raise HTTPException(400, "Cannot generate IRN for cancelled invoice")
    if inv.irn:
        raise HTTPException(400, "IRN already generated")
    if not inv.party_gstin:
        raise HTTPException(400, "E-invoice requires buyer GSTIN (B2B)")
    if inv.invoice_type == "BILL_OF_SUPPLY":
        raise HTTPException(400, "Bill of Supply is not eligible for e-invoice")
    company = company_of(db, user)
    ok, msg = validate_einvoice_window(inv.invoice_date, company.aato)
    if not ok:
        raise HTTPException(400, msg)
    sez = False
    if inv.party_id:
        p = db.get(models.Party, inv.party_id)
        sez = bool(p.sez) if p else False
    payload = build_inv01(inv, inv.gstin, company, inv.lines, sez=sez)
    result = mock_irn(payload)
    inv.irn = result["Irn"]
    inv.ack_no = result["AckNo"]
    inv.irn_date = datetime.utcnow()
    inv.signed_qr = result["SignedQRCode"]
    inv.einvoice_status = "GENERATED"
    audit(db, user, "IRN", "INVOICE", inv.id, inv.irn)
    db.commit()
    return {"ok": True, "sandbox": True, "irn": inv.irn, "ack_no": inv.ack_no, "ack_dt": result["AckDt"], "qr_png": result.get("QrPng"), "payload": payload}


@app.post("/api/invoices/{invoice_id}/einvoice/cancel")
def cancel_irn(invoice_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    inv = db.get(models.Invoice, invoice_id)
    if not inv or inv.company_id != cid(user):
        raise HTTPException(404, "Invoice not found")
    if not inv.irn:
        raise HTTPException(400, "No IRN to cancel")
    if inv.irn_date and datetime.utcnow() - inv.irn_date > timedelta(hours=24):
        raise HTTPException(400, "IRN can be cancelled only within 24 hours")
    inv.einvoice_status = "CANCELLED"
    inv.cancel_reason = "IRN cancelled in sandbox"
    audit(db, user, "IRN_CANCEL", "INVOICE", inv.id, inv.irn)
    db.commit()
    return {"ok": True}


@app.get("/api/purchases")
def list_purchases(gstin_id: Optional[int] = None, period: Optional[str] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(models.Purchase).filter(models.Purchase.company_id == cid(user))
    if gstin_id:
        q = q.filter(models.Purchase.gstin_id == gstin_id)
    if period:
        q = q.filter(models.Purchase.period == period)
    return [purchase_out(p) for p in q.order_by(models.Purchase.invoice_date.desc()).all()]


@app.post("/api/purchases")
def create_purchase(body: schemas.PurchaseIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    gstin = gstin_of(db, user, body.gstin_id)
    vendor = db.get(models.Party, body.vendor_id) if body.vendor_id else None
    pos = body.place_of_supply or (vendor.place_of_supply if vendor else gstin.state_code)
    row = models.Purchase(
        company_id=cid(user),
        gstin_id=gstin.id,
        vendor_id=body.vendor_id,
        number=body.number,
        invoice_date=body.invoice_date,
        vendor_name=body.vendor_name or (vendor.name if vendor else ""),
        vendor_gstin=body.vendor_gstin or (vendor.gstin if vendor else ""),
        place_of_supply=pos,
        supply_type=supply_type(gstin.state_code, pos),
        reverse_charge=body.reverse_charge,
        taxable_value=body.taxable_value,
        cgst=body.cgst,
        sgst=body.sgst,
        igst=body.igst,
        total=body.total or (body.taxable_value + body.cgst + body.sgst + body.igst),
        itc_eligible=body.itc_eligible,
        period=period_of(body.invoice_date),
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return purchase_out(row)


@app.get("/api/gstr2b")
def list_gstr2b(gstin_id: int, period: str, user=Depends(current_user), db: Session = Depends(get_db)):
    gstin_of(db, user, gstin_id)
    rows = db.query(models.Gstr2bRow).filter(
        models.Gstr2bRow.company_id == cid(user),
        models.Gstr2bRow.gstin_id == gstin_id,
        models.Gstr2bRow.period == period,
    ).all()
    return [
        {
            "id": r.id,
            "vendor_gstin": r.vendor_gstin,
            "vendor_name": r.vendor_name,
            "invoice_number": r.invoice_number,
            "invoice_date": r.invoice_date.isoformat() if r.invoice_date else None,
            "taxable_value": r.taxable_value,
            "cgst": r.cgst,
            "sgst": r.sgst,
            "igst": r.igst,
            "total": r.total,
            "irn": r.irn,
            "source": r.source,
        }
        for r in rows
    ]


@app.post("/api/gstr2b")
def add_gstr2b(body: schemas.Gstr2bIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Insufficient permissions")
    gstin_of(db, user, body.gstin_id)
    row = models.Gstr2bRow(company_id=cid(user), **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@app.get("/api/returns/gstr1")
def get_gstr1(gstin_id: int, period: str, user=Depends(current_user), db: Session = Depends(get_db)):
    gstin = gstin_of(db, user, gstin_id)
    invoices = db.query(models.Invoice).options(joinedload(models.Invoice.lines), joinedload(models.Invoice.party)).filter(
        models.Invoice.company_id == cid(user),
        models.Invoice.gstin_id == gstin_id,
        models.Invoice.period == period,
    ).all()
    orig_ids = [i.original_invoice_id for i in invoices if i.original_invoice_id]
    originals = {}
    if orig_ids:
        originals = {o.id: o for o in db.query(models.Invoice).filter(models.Invoice.id.in_(orig_ids)).all()}
    tables = gstr1_tables(invoices, originals)
    payload = {
        "gstin": gstin.gstin,
        "fp": period,
        "gt": company_of(db, user).aato,
        "cur_gt": company_of(db, user).aato,
        **tables,
    }
    return payload


@app.get("/api/returns/gstr3b")
def get_gstr3b(gstin_id: int, period: str, user=Depends(current_user), db: Session = Depends(get_db)):
    gstin = gstin_of(db, user, gstin_id)
    invoices = db.query(models.Invoice).options(joinedload(models.Invoice.lines)).filter(
        models.Invoice.company_id == cid(user),
        models.Invoice.gstin_id == gstin_id,
        models.Invoice.period == period,
    ).all()
    purchases = db.query(models.Purchase).filter(
        models.Purchase.company_id == cid(user),
        models.Purchase.gstin_id == gstin_id,
        models.Purchase.period == period,
    ).all()
    summary = gstr3b_summary(invoices, purchases)
    return {"gstin": gstin.gstin, "fp": period, **summary}


@app.post("/api/returns/lock")
def lock_period(gstin_id: int, period: str, form: str = "GSTR1", user=Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in ("OWNER", "ACCOUNTANT", "CA"):
        raise HTTPException(403, "Insufficient permissions")
    gstin_of(db, user, gstin_id)
    row = db.query(models.ReturnPeriod).filter(models.ReturnPeriod.gstin_id == gstin_id, models.ReturnPeriod.period == period).first()
    if not row:
        row = models.ReturnPeriod(company_id=cid(user), gstin_id=gstin_id, period=period)
        db.add(row)
        db.flush()
    if form == "GSTR1":
        row.gstr1_status = "FILED"
        invoices = db.query(models.Invoice).options(joinedload(models.Invoice.lines), joinedload(models.Invoice.party)).filter(
            models.Invoice.gstin_id == gstin_id, models.Invoice.period == period
        ).all()
        orig_ids = [i.original_invoice_id for i in invoices if i.original_invoice_id]
        originals = {}
        if orig_ids:
            originals = {o.id: o for o in db.query(models.Invoice).filter(models.Invoice.id.in_(orig_ids)).all()}
        row.gstr1_json = json.dumps(gstr1_tables(invoices, originals))
    else:
        row.gstr3b_status = "FILED"
    row.locked = True
    row.filed_at = datetime.utcnow()
    db.query(models.Invoice).filter(models.Invoice.gstin_id == gstin_id, models.Invoice.period == period).update({"locked": True})
    audit(db, user, "LOCK", "RETURN", row.id, f"{form} {period}")
    db.commit()
    return {"ok": True}


@app.get("/api/reconcile/einvoice")
def reco_einvoice(gstin_id: int, period: str, user=Depends(current_user), db: Session = Depends(get_db)):
    gstin_of(db, user, gstin_id)
    invoices = db.query(models.Invoice).filter(
        models.Invoice.company_id == cid(user),
        models.Invoice.gstin_id == gstin_id,
        models.Invoice.period == period,
    ).all()
    rows = reconcile_gstr1_vs_irn(invoices, company_of(db, user).aato)
    buckets = {}
    for r in rows:
        buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
    return {"rows": rows, "buckets": buckets}


@app.get("/api/reconcile/itc")
def reco_itc(gstin_id: int, period: str, user=Depends(current_user), db: Session = Depends(get_db)):
    gstin_of(db, user, gstin_id)
    purchases = db.query(models.Purchase).filter(
        models.Purchase.company_id == cid(user),
        models.Purchase.gstin_id == gstin_id,
        models.Purchase.period == period,
    ).all()
    portal = db.query(models.Gstr2bRow).filter(
        models.Gstr2bRow.company_id == cid(user),
        models.Gstr2bRow.gstin_id == gstin_id,
        models.Gstr2bRow.period == period,
    ).all()
    rows = reconcile_2b(purchases, portal)
    buckets = {}
    for r in rows:
        buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
    return {"rows": rows, "buckets": buckets}


@app.get("/api/dashboard")
def dashboard(gstin_id: Optional[int] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    company = company_of(db, user)
    today = date.today()
    period = period_of(today)
    q = db.query(models.Invoice).filter(models.Invoice.company_id == cid(user), models.Invoice.status != "CANCELLED")
    pq = db.query(models.Purchase).filter(models.Purchase.company_id == cid(user))
    if gstin_id:
        q = q.filter(models.Invoice.gstin_id == gstin_id)
        pq = pq.filter(models.Purchase.gstin_id == gstin_id)
    invoices = q.all()
    purchases = pq.all()
    this_period = [i for i in invoices if i.period == period]
    fy_inv = [i for i in invoices if i.fy == fy_label(today)]
    outward = sum(i.taxable_value for i in this_period if i.invoice_type != "CREDIT_NOTE") - sum(i.taxable_value for i in this_period if i.invoice_type == "CREDIT_NOTE")
    tax = sum((i.cgst + i.sgst + i.igst) * (-1 if i.invoice_type == "CREDIT_NOTE" else 1) for i in this_period)
    itc = sum(p.cgst + p.sgst + p.igst for p in purchases if p.period == period and p.itc_eligible)
    aato = company.aato
    dues = due_dates(today.year, today.month)
    recent = sorted(invoices, key=lambda x: (x.invoice_date, x.id), reverse=True)[:8]
    gstins = db.query(models.Gstin).filter(models.Gstin.company_id == cid(user)).all()
    pending_irn = [
        invoice_out(i, lines=[], aato=aato)
        for i in this_period
        if einvoice_status_of(i, aato) == "REQUIRED" and i.status != "CANCELLED"
    ]
    rp_q = db.query(models.ReturnPeriod).filter(models.ReturnPeriod.company_id == cid(user), models.ReturnPeriod.period == period)
    if gstin_id:
        rp_q = rp_q.filter(models.ReturnPeriod.gstin_id == gstin_id)
    rps = rp_q.all()
    filing = {
        "gstr1": (rps[0].gstr1_status if rps else "OPEN"),
        "gstr3b": (rps[0].gstr3b_status if rps else "OPEN"),
    }
    if gstin_id is None and rps:
        filing = {
            "gstr1": "FILED" if all(r.gstr1_status == "FILED" for r in rps) else "OPEN",
            "gstr3b": "FILED" if all(r.gstr3b_status == "FILED" for r in rps) else "OPEN",
        }
    return {
        "company": company_out(company, gstins),
        "period": period,
        "fy": fy_label(today),
        "today_in": today.strftime("%d %b %Y"),
        "aato": aato,
        "einvoice_threshold": EINVOICE_THRESHOLD,
        "einvoice_warning": aato >= EINVOICE_THRESHOLD,
        "outward_taxable": round(outward, 2),
        "tax_liability": round(tax, 2),
        "itc": round(itc, 2),
        "net_payable": round(max(tax - itc, 0), 2),
        "invoice_count": len(this_period),
        "fy_turnover": round(sum(i.taxable_value for i in fy_inv if i.invoice_type != "CREDIT_NOTE"), 2),
        "due_dates": dues,
        "filing": filing,
        "pending_irn": pending_irn,
        "pending_irn_count": len(pending_irn),
        "sandbox": sandbox_mode(),
        "recent": [invoice_out(i, lines=[], aato=aato) for i in recent],
        "period_label": period_label(period),
        "counts": {
            "invoices": len(invoices),
            "parties": db.query(models.Party).filter(models.Party.company_id == cid(user)).count(),
            "items": db.query(models.Item).filter(models.Item.company_id == cid(user)).count(),
            "gstins": len(gstins),
        },
    }


@app.get("/api/reports/sales")
def sales_register(gstin_id: Optional[int] = None, period: Optional[str] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(models.Invoice).filter(models.Invoice.company_id == cid(user))
    if gstin_id:
        q = q.filter(models.Invoice.gstin_id == gstin_id)
    if period:
        q = q.filter(models.Invoice.period == period)
    rows = q.order_by(models.Invoice.invoice_date, models.Invoice.number).all()
    aato = company_of(db, user).aato
    return [invoice_out(r, lines=[], aato=aato) for r in rows]


@app.get("/api/reports/party")
def party_report(party_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    party = db.get(models.Party, party_id)
    if not party or party.company_id != cid(user):
        raise HTTPException(404, "Party not found")
    rows = db.query(models.Invoice).filter(models.Invoice.company_id == cid(user), models.Invoice.party_id == party_id).all()
    return {
        "party": party_out(party),
        "invoices": [invoice_out(r, lines=[], aato=company_of(db, user).aato) for r in rows],
        "total": round(sum(r.total for r in rows if r.status != "CANCELLED"), 2),
    }


@app.get("/api/export/gstr1")
def export_gstr1(gstin_id: int, period: str, user=Depends(current_user), db: Session = Depends(get_db)):
    data = get_gstr1(gstin_id, period, user, db)
    raw = json.dumps(data, indent=2).encode()
    return StreamingResponse(BytesIO(raw), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=GSTR1_{period}.json"})


@app.get("/api/export/sales.csv")
def export_sales_csv(gstin_id: Optional[int] = None, period: Optional[str] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    rows = sales_register(gstin_id, period, user, db)
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["Number", "Date", "Type", "Party", "GSTIN", "POS", "Supply", "Taxable", "CGST", "SGST", "IGST", "Total", "IRN", "Status"])
    for r in rows:
        w.writerow([r["number"], r["invoice_date"], r["invoice_type"], r["party_name"], r["party_gstin"], r["place_of_supply"], r["supply_type"], r["taxable_value"], r["cgst"], r["sgst"], r["igst"], r["total"], r["irn"], r["status"]])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sales_register.csv"})


@app.get("/api/audit")
def audit_log(user=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.AuditLog).filter(models.AuditLog.company_id == cid(user)).order_by(models.AuditLog.id.desc()).limit(200).all()
    return [
        {"id": r.id, "action": r.action, "entity": r.entity, "entity_id": r.entity_id, "detail": r.detail, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]
