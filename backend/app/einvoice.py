from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, date, timedelta
from io import BytesIO
import base64

from .gst_engine import EINVOICE_DAYS, EINVOICE_THRESHOLD, EINVOICE_WINDOW_THRESHOLD, invoice_doc_type, STATES

GSP_BASE = os.environ.get("GSP_BASE_URL", "")
GSP_KEY = os.environ.get("GSP_API_KEY", "")


def sandbox_mode() -> bool:
    return not (GSP_BASE and GSP_KEY)


def build_inv01(invoice, gstin, company, lines, sez: bool = False) -> dict:
    seller = {
        "Gstin": gstin.gstin,
        "LglNm": gstin.legal_name,
        "TrdNm": gstin.trade_name,
        "Addr1": gstin.address1,
        "Addr2": gstin.address2 or None,
        "Loc": gstin.city,
        "Pin": int(gstin.pincode or 0) if (gstin.pincode or "").isdigit() else 0,
        "Stcd": gstin.state_code,
    }
    buyer_pin = 0
    addr = invoice.party_address or ""
    digits = "".join(ch for ch in addr if ch.isdigit())
    if len(digits) >= 6:
        buyer_pin = int(digits[-6:])
    buyer = {
        "Gstin": invoice.party_gstin or "URP",
        "LglNm": invoice.party_name,
        "Addr1": (invoice.party_address or "-")[:100],
        "Loc": (invoice.party_address or gstin.city or "-").split(",")[-1].strip()[:50] or gstin.city,
        "Pin": buyer_pin or (int(gstin.pincode or 0) if (gstin.pincode or "").isdigit() else 0),
        "Pos": invoice.place_of_supply,
        "Stcd": invoice.party_state or invoice.place_of_supply,
    }
    item_list = []
    for i, ln in enumerate(lines, 1):
        item_list.append({
            "SlNo": str(i),
            "IsServc": "Y",
            "PrdDesc": ln.description,
            "HsnCd": ln.hsn_sac,
            "Qty": ln.qty,
            "Unit": ln.unit,
            "UnitPrice": ln.rate,
            "TotAmt": round(ln.qty * ln.rate, 2),
            "Discount": ln.discount,
            "AssAmt": ln.taxable_value,
            "GstRt": ln.gst_rate,
            "IgstAmt": ln.igst,
            "CgstAmt": ln.cgst,
            "SgstAmt": ln.sgst,
            "TotItemVal": ln.total,
        })
    return {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": "SEZWP" if sez and (invoice.igst or invoice.cgst or invoice.sgst) else ("SEZWOP" if sez else ("B2B" if invoice.party_gstin else "B2C")),
            "RegRev": "Y" if invoice.reverse_charge else "N",
            "IgstOnIntra": "Y" if sez and gstin.state_code == (invoice.place_of_supply or "") else "N",
        },
        "DocDtls": {
            "Typ": invoice_doc_type(invoice.invoice_type),
            "No": invoice.number,
            "Dt": invoice.invoice_date.strftime("%d/%m/%Y"),
        },
        "SellerDtls": seller,
        "BuyerDtls": buyer,
        "ItemList": item_list,
        "ValDtls": {
            "AssVal": invoice.taxable_value,
            "CgstVal": invoice.cgst,
            "SgstVal": invoice.sgst,
            "IgstVal": invoice.igst,
            "RndOffAmt": invoice.round_off,
            "TotInvVal": invoice.total,
        },
    }


def qr_png_from_text(text: str) -> str:
    if not text:
        return ""
    try:
        import qrcode
        img = qrcode.make(text)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def einvoice_status_of(inv, aato: float) -> str:
    if inv.einvoice_status == "CANCELLED" or (inv.status == "CANCELLED" and inv.irn):
        return "CANCELLED"
    if inv.irn:
        return "GENERATED"
    if inv.einvoice_status == "FAILED":
        return "FAILED"
    if einvoice_required(inv.party_gstin, aato, inv.invoice_type, inv.scheme):
        return "REQUIRED"
    return "NOT_REQUIRED"


def mock_irn(payload: dict) -> dict:
    raw = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    irn = hashlib.sha256((digest + str(uuid.uuid4())).encode()).hexdigest()
    ack = str(abs(hash(irn)) % 10**16).zfill(16)
    qr_payload = {
        "SellerGstin": payload["SellerDtls"]["Gstin"],
        "BuyerGstin": payload["BuyerDtls"]["Gstin"],
        "DocNo": payload["DocDtls"]["No"],
        "DocTyp": payload["DocDtls"]["Typ"],
        "DocDt": payload["DocDtls"]["Dt"],
        "TotInvVal": payload["ValDtls"]["TotInvVal"],
        "ItemCnt": len(payload["ItemList"]),
        "MainHsnCode": payload["ItemList"][0]["HsnCd"] if payload["ItemList"] else "",
        "Irn": irn,
        "IrnDt": datetime.utcnow().isoformat(),
    }
    qr_png = qr_png_from_text(json.dumps(qr_payload))
    return {
        "Irn": irn,
        "AckNo": ack,
        "AckDt": datetime.utcnow().isoformat(timespec="seconds"),
        "SignedQRCode": json.dumps(qr_payload),
        "QrPng": qr_png,
        "Status": "ACT",
        "sandbox": True,
    }


def validate_einvoice_window(invoice_date: date, aato: float) -> tuple[bool, str]:
    if float(aato or 0) < EINVOICE_WINDOW_THRESHOLD:
        return True, ""
    if date.today() - invoice_date > timedelta(days=EINVOICE_DAYS):
        return False, f"IRN cannot be generated after {EINVOICE_DAYS} days for AATO >= Rs 10 Cr"
    return True, ""


def einvoice_required(party_gstin: str, aato: float, invoice_type: str, scheme: str) -> bool:
    if scheme == "COMPOSITION":
        return False
    if invoice_type == "BILL_OF_SUPPLY":
        return False
    if not party_gstin:
        return False
    if float(aato or 0) < EINVOICE_THRESHOLD:
        return False
    return True
