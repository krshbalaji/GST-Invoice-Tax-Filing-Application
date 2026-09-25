from .gst_engine import STATES, INVOICE_TYPE_LABELS, EINVOICE_LABELS, STATUS_LABELS, amount_in_words, format_inr
from .einvoice import einvoice_status_of


def gstin_out(g):
    return {
        "id": g.id,
        "gstin": g.gstin,
        "legal_name": g.legal_name,
        "trade_name": g.trade_name,
        "address1": g.address1,
        "address2": g.address2,
        "city": g.city,
        "state_code": g.state_code,
        "state_name": STATES.get(g.state_code, ""),
        "pincode": g.pincode,
        "email": g.email,
        "phone": g.phone,
        "invoice_prefix": g.invoice_prefix,
        "next_number": g.next_number,
        "cn_prefix": g.cn_prefix,
        "dn_prefix": g.dn_prefix,
        "bos_prefix": g.bos_prefix,
        "is_primary": g.is_primary,
        "active": g.active,
    }


def company_out(c, gstins=None):
    return {
        "id": c.id,
        "legal_name": c.legal_name,
        "trade_name": c.trade_name,
        "pan": c.pan,
        "scheme": c.scheme,
        "aato": c.aato,
        "logo_data": c.logo_data or "",
        "bank_name": c.bank_name,
        "bank_account": c.bank_account,
        "bank_ifsc": c.bank_ifsc,
        "bank_branch": c.bank_branch,
        "terms": c.terms,
        "gstins": [gstin_out(g) for g in (gstins or c.gstins or [])],
    }


def user_out(u):
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "active": u.active,
        "company_id": u.company_id,
    }


def party_out(p):
    return {
        "id": p.id,
        "kind": p.kind,
        "name": p.name,
        "trade_name": p.trade_name,
        "gstin": p.gstin,
        "pan": p.pan,
        "email": p.email,
        "phone": p.phone,
        "address1": p.address1,
        "address2": p.address2,
        "city": p.city,
        "state_code": p.state_code,
        "state_name": STATES.get(p.state_code or "", ""),
        "pincode": p.pincode,
        "place_of_supply": p.place_of_supply,
        "sez": p.sez,
        "notes": p.notes,
        "active": p.active,
    }


def item_out(i):
    return {
        "id": i.id,
        "kind": i.kind,
        "code": i.code,
        "description": i.description,
        "hsn_sac": i.hsn_sac,
        "unit": i.unit,
        "rate": i.rate,
        "taxability": i.taxability,
        "gst_preset": i.gst_preset,
        "active": i.active,
    }


def line_out(ln):
    return {
        "id": ln.id,
        "item_id": ln.item_id,
        "custom": ln.custom,
        "description": ln.description,
        "hsn_sac": ln.hsn_sac,
        "unit": ln.unit,
        "qty": ln.qty,
        "rate": ln.rate,
        "discount": ln.discount,
        "taxable_value": ln.taxable_value,
        "gst_rate": ln.gst_rate,
        "cgst_rate": ln.cgst_rate,
        "sgst_rate": ln.sgst_rate,
        "igst_rate": ln.igst_rate,
        "cgst": ln.cgst,
        "sgst": ln.sgst,
        "igst": ln.igst,
        "total": ln.total,
    }


def invoice_out(inv, gstin=None, lines=None, aato=0, original=None):
    g = gstin or inv.gstin
    ev = einvoice_status_of(inv, aato or 0)
    orig = original
    orig_num = ""
    orig_dt = ""
    if orig:
        orig_num = orig.number
        orig_dt = orig.invoice_date.strftime("%d-%m-%Y") if orig.invoice_date else ""
    return {
        "id": inv.id,
        "gstin_id": inv.gstin_id,
        "seller_gstin": g.gstin if g else "",
        "seller_name": g.trade_name if g else "",
        "seller_state": g.state_code if g else "",
        "party_id": inv.party_id,
        "invoice_type": inv.invoice_type,
        "invoice_type_label": INVOICE_TYPE_LABELS.get(inv.invoice_type, inv.invoice_type),
        "number": inv.number,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "place_of_supply": inv.place_of_supply,
        "place_of_supply_name": STATES.get(inv.place_of_supply or "", ""),
        "supply_type": inv.supply_type,
        "reverse_charge": inv.reverse_charge,
        "gst_preset": inv.gst_preset,
        "scheme": inv.scheme,
        "party_name": inv.party_name,
        "party_gstin": inv.party_gstin,
        "party_address": inv.party_address,
        "party_state": inv.party_state,
        "taxable_value": inv.taxable_value,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "round_off": inv.round_off,
        "total": inv.total,
        "notes": inv.notes,
        "status": inv.status,
        "status_label": STATUS_LABELS.get(inv.status, inv.status),
        "einvoice_status": ev,
        "einvoice_status_label": EINVOICE_LABELS.get(ev, ev),
        "amount_in_words": amount_in_words(inv.total),
        "total_inr": format_inr(inv.total),
        "irn": inv.irn,
        "irn_date": inv.irn_date.isoformat() if inv.irn_date else None,
        "ack_no": inv.ack_no,
        "signed_qr": inv.signed_qr,
        "period": inv.period,
        "fy": inv.fy,
        "custom_mode": inv.custom_mode,
        "locked": inv.locked,
        "original_invoice_id": inv.original_invoice_id,
        "original_number": orig_num,
        "original_date": orig_dt,
        "invoice_date_in": inv.invoice_date.strftime("%d-%m-%Y") if inv.invoice_date else "",
        "due_date_in": inv.due_date.strftime("%d-%m-%Y") if inv.due_date else "",
        "irn_date_in": inv.irn_date.strftime("%d-%m-%Y %H:%M") if inv.irn_date else "",
        "sez": bool(getattr(inv.__dict__.get("party"), "sez", False)),
        "lines": [line_out(x) for x in (lines if lines is not None else (inv.lines or []))],
    }


def purchase_out(p):
    return {
        "id": p.id,
        "gstin_id": p.gstin_id,
        "vendor_id": p.vendor_id,
        "number": p.number,
        "invoice_date": p.invoice_date.isoformat() if p.invoice_date else None,
        "invoice_date_in": p.invoice_date.strftime("%d-%m-%Y") if p.invoice_date else "",
        "vendor_name": p.vendor_name,
        "vendor_gstin": p.vendor_gstin,
        "place_of_supply": p.place_of_supply,
        "supply_type": p.supply_type,
        "reverse_charge": p.reverse_charge,
        "taxable_value": p.taxable_value,
        "cgst": p.cgst,
        "sgst": p.sgst,
        "igst": p.igst,
        "total": p.total,
        "itc_eligible": p.itc_eligible,
        "period": p.period,
        "notes": p.notes,
    }
