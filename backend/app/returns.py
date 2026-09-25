from __future__ import annotations

from collections import defaultdict
from datetime import date
from .gst_engine import money, STATES, due_dates, gst_portal_date, gstr1_inv_typ
from .einvoice import einvoice_status_of


def gstr1_tables(invoices: list, originals: dict | None = None) -> dict:
    originals = originals or {}
    b2b = []
    b2cl = []
    exp = []
    cdnr = []
    cdnur = []
    nil = []
    hsn = defaultdict(lambda: {"hsn": "", "desc": "", "uqc": "", "qty": 0, "txval": 0, "cgst": 0, "sgst": 0, "igst": 0})
    b2cs = defaultdict(lambda: {"sply_ty": "", "pos": "", "rt": 0, "txval": 0, "iamt": 0, "camt": 0, "samt": 0})

    for inv in invoices:
        if inv.status in ("CANCELLED", "DRAFT"):
            continue
        lines = list(inv.lines)
        if inv.invoice_type in ("CREDIT_NOTE", "DEBIT_NOTE"):
            sign = -1 if inv.invoice_type == "CREDIT_NOTE" else 1
            party = getattr(inv, "party", None)
            sez = bool(getattr(inv, "sez", False) or (party.sez if party else False))
            orig = originals.get(getattr(inv, "original_invoice_id", None))
            orig_num = getattr(inv, "original_number", "") or (orig.number if orig else "")
            orig_dt = getattr(inv, "original_date", "") or (gst_portal_date(orig.invoice_date) if orig else "")
            row = {
                "nt_num": inv.number,
                "nt_dt": gst_portal_date(inv.invoice_date),
                "ntty": "C" if inv.invoice_type == "CREDIT_NOTE" else "D",
                "val": money(inv.total * sign),
                "pos": inv.place_of_supply,
                "rchrg": "Y" if inv.reverse_charge else "N",
                "inv_typ": gstr1_inv_typ(inv.party_gstin, sez, (inv.igst + inv.cgst + inv.sgst) != 0),
                "irn": inv.irn or "",
                "inum": orig_num,
                "idt": orig_dt,
                "ont_num": orig_num,
                "ont_dt": orig_dt,
                "itms": [{
                    "num": 1,
                    "itm_det": {
                        "rt": lines[0].gst_rate if lines else 0,
                        "txval": money(inv.taxable_value * sign),
                        "iamt": money(inv.igst * sign),
                        "camt": money(inv.cgst * sign),
                        "samt": money(inv.sgst * sign),
                    },
                }],
            }
            if inv.party_gstin:
                row["ctin"] = inv.party_gstin
                cdnr.append(row)
            else:
                cdnur.append(row)
        elif inv.supply_type == "EXPORT":
            exp.append({
                "inum": inv.number,
                "idt": gst_portal_date(inv.invoice_date),
                "val": inv.total,
                "sbpcode": "",
                "sbnum": "",
                "sbdt": "",
                "itms": [{
                    "num": 1,
                    "itm_det": {"txval": inv.taxable_value, "rt": lines[0].gst_rate if lines else 0, "iamt": inv.igst},
                }],
            })
        elif inv.party_gstin:
            party = getattr(inv, "party", None)
            sez = bool(getattr(inv, "sez", False) or (party.sez if party else False))
            b2b.append({
                "ctin": inv.party_gstin,
                "inum": inv.number,
                "idt": gst_portal_date(inv.invoice_date),
                "val": inv.total,
                "pos": inv.place_of_supply,
                "rchrg": "Y" if inv.reverse_charge else "N",
                "inv_typ": gstr1_inv_typ(inv.party_gstin, sez, (inv.igst + inv.cgst + inv.sgst) != 0),
                "irn": inv.irn or "",
                "itms": [{
                    "num": i + 1,
                    "itm_det": {
                        "rt": ln.gst_rate,
                        "txval": ln.taxable_value,
                        "iamt": ln.igst,
                        "camt": ln.cgst,
                        "samt": ln.sgst,
                    },
                } for i, ln in enumerate(lines)],
            })
        else:
            if inv.supply_type == "INTER" and inv.total > 250000:
                b2cl.append({
                    "pos": inv.place_of_supply,
                    "inum": inv.number,
                    "idt": gst_portal_date(inv.invoice_date),
                    "val": inv.total,
                    "itms": [{
                        "num": 1,
                        "itm_det": {"rt": lines[0].gst_rate if lines else 0, "txval": inv.taxable_value, "iamt": inv.igst},
                    }],
                })
            else:
                rt = lines[0].gst_rate if lines else 0
                key = (inv.supply_type, inv.place_of_supply, rt)
                b2cs[key]["sply_ty"] = inv.supply_type
                b2cs[key]["pos"] = inv.place_of_supply
                b2cs[key]["rt"] = rt
                b2cs[key]["txval"] = money(b2cs[key]["txval"] + inv.taxable_value)
                b2cs[key]["iamt"] = money(b2cs[key]["iamt"] + inv.igst)
                b2cs[key]["camt"] = money(b2cs[key]["camt"] + inv.cgst)
                b2cs[key]["samt"] = money(b2cs[key]["samt"] + inv.sgst)

        if inv.gst_preset == "EXEMPT" or (inv.cgst + inv.sgst + inv.igst) == 0:
            if inv.invoice_type == "TAX_INVOICE":
                nil.append({"sply_ty": inv.supply_type, "expt_amt": 0, "nil_amt": inv.taxable_value, "ngsup_amt": 0})

        sign_hsn = -1 if inv.invoice_type == "CREDIT_NOTE" else 1
        for ln in lines:
            k = ln.hsn_sac or "NA"
            hsn[k]["hsn"] = k
            hsn[k]["desc"] = ln.description[:30]
            hsn[k]["uqc"] = ln.unit
            hsn[k]["qty"] = money(hsn[k]["qty"] + ln.qty * sign_hsn)
            hsn[k]["txval"] = money(hsn[k]["txval"] + ln.taxable_value * sign_hsn)
            hsn[k]["cgst"] = money(hsn[k]["cgst"] + ln.cgst * sign_hsn)
            hsn[k]["sgst"] = money(hsn[k]["sgst"] + ln.sgst * sign_hsn)
            hsn[k]["igst"] = money(hsn[k]["igst"] + ln.igst * sign_hsn)

    grouped = defaultdict(list)
    for row in b2b:
        ctin = row.pop("ctin")
        grouped[ctin].append(row)
    b2b_out = [{"ctin": ctin, "inv": invs} for ctin, invs in grouped.items()]

    return {
        "b2b": b2b_out,
        "b2cl": b2cl,
        "b2cs": list(b2cs.values()),
        "exp": exp,
        "cdnr": cdnr,
        "cdnur": cdnur,
        "nil": nil,
        "hsn": {"data": list(hsn.values())},
        "doc_issue": _doc_summary(invoices),
    }


def _doc_summary(invoices):
    buckets = defaultdict(list)
    for inv in invoices:
        if inv.status == "DRAFT":
            continue
        key = inv.invoice_type
        buckets[key].append(inv)
    out = []
    mapping = {"TAX_INVOICE": "Invoices for outward supply", "BILL_OF_SUPPLY": "Bill of Supply", "CREDIT_NOTE": "Credit Note", "DEBIT_NOTE": "Debit Note"}
    for k, rows in buckets.items():
        nums = sorted(r.number for r in rows)
        cancelled = sum(1 for r in rows if r.status == "CANCELLED")
        out.append({
            "doc_typ": mapping.get(k, k),
            "from": nums[0] if nums else "",
            "to": nums[-1] if nums else "",
            "totnum": len(rows),
            "cancel": cancelled,
            "net_issue": len(rows) - cancelled,
        })
    return out


def gstr3b_summary(invoices, purchases) -> dict:
    outward_taxable = 0
    outward_zero = 0
    outward_nil = 0
    igst = cgst = sgst = 0
    itc_igst = itc_cgst = itc_sgst = 0
    rcm_igst = rcm_cgst = rcm_sgst = 0
    rcm_txval = 0
    for inv in invoices:
        if inv.status in ("CANCELLED", "DRAFT"):
            continue
        if inv.invoice_type == "CREDIT_NOTE":
            sign = -1
        else:
            sign = 1
        tax = inv.cgst + inv.sgst + inv.igst
        if tax == 0:
            outward_nil += inv.taxable_value * sign
        else:
            outward_taxable += inv.taxable_value * sign
        igst += inv.igst * sign
        cgst += inv.cgst * sign
        sgst += inv.sgst * sign
        if inv.reverse_charge:
            rcm_txval += inv.taxable_value * sign
            rcm_igst += inv.igst * sign
            rcm_cgst += inv.cgst * sign
            rcm_sgst += inv.sgst * sign
    for p in purchases:
        if p.itc_eligible:
            itc_igst += p.igst
            itc_cgst += p.cgst
            itc_sgst += p.sgst
    net_igst = money(igst - itc_igst)
    net_cgst = money(cgst - itc_cgst)
    net_sgst = money(sgst - itc_sgst)
    return {
        "sup_details": {
            "osup_det": {"txval": money(outward_taxable), "iamt": money(igst), "camt": money(cgst), "samt": money(sgst)},
            "osup_zero": {"txval": money(outward_zero), "iamt": 0},
            "osup_nil_exmp": {"txval": money(outward_nil)},
            "isup_rev": {"txval": money(rcm_txval), "iamt": money(rcm_igst), "camt": money(rcm_cgst), "samt": money(rcm_sgst)},
        },
        "itc_elg": {
            "itc_avl": [
                {"ty": "IMPG", "iamt": 0, "camt": 0, "samt": 0},
                {"ty": "IMPS", "iamt": 0, "camt": 0, "samt": 0},
                {"ty": "ISRC", "iamt": 0, "camt": 0, "samt": 0},
                {"ty": "ISD", "iamt": 0, "camt": 0, "samt": 0},
                {"ty": "OTH", "iamt": money(itc_igst), "camt": money(itc_cgst), "samt": money(itc_sgst)},
            ]
        },
        "tx_pmt": {
            "igst": money(max(net_igst, 0)),
            "cgst": money(max(net_cgst, 0)),
            "sgst": money(max(net_sgst, 0)),
            "total": money(max(net_igst, 0) + max(net_cgst, 0) + max(net_sgst, 0)),
        },
        "itc": {"igst": money(itc_igst), "cgst": money(itc_cgst), "sgst": money(itc_sgst)},
        "outward": {"taxable": money(outward_taxable), "nil": money(outward_nil), "igst": money(igst), "cgst": money(cgst), "sgst": money(sgst)},
    }


def reconcile_gstr1_vs_irn(invoices, aato: float = 0):
    rows = []
    for inv in invoices:
        if inv.status == "DRAFT":
            continue
        st = einvoice_status_of(inv, aato)
        bucket = "OK"
        if st == "REQUIRED":
            bucket = "Missing IRN"
        elif st == "FAILED":
            bucket = "IRN failed"
        elif st == "CANCELLED":
            bucket = "Cancelled IRN"
        elif st == "GENERATED" and not inv.irn:
            bucket = "Missing IRN"
        elif inv.status == "CANCELLED" and inv.irn:
            bucket = "Cancelled IRN"
        elif st == "NOT_REQUIRED":
            bucket = "Not required"
        rows.append({
            "id": getattr(inv, "id", None),
            "number": inv.number,
            "date": gst_portal_date(inv.invoice_date),
            "party": inv.party_name,
            "gstin": inv.party_gstin,
            "total": inv.total,
            "irn": inv.irn,
            "einvoice_status": inv.einvoice_status,
            "status": inv.status,
            "bucket": bucket,
        })
    return rows


def reconcile_2b(purchases, gstr2b):
    book_map = {}
    for p in purchases:
        key = f"{(p.vendor_gstin or '').upper()}|{(p.number or '').upper()}"
        book_map[key] = p
    portal_map = {}
    for r in gstr2b:
        key = f"{(r.vendor_gstin or '').upper()}|{(r.invoice_number or '').upper()}"
        portal_map[key] = r
    out = []
    seen = set()
    for key, p in book_map.items():
        r = portal_map.get(key)
        seen.add(key)
        if not r:
            out.append(_mm("Missing in GSTR-2B", p, None))
            continue
        if abs((p.total or 0) - (r.total or 0)) > 1:
            out.append(_mm("Value mismatch", p, r))
        else:
            out.append(_mm("Matched", p, r))
    for key, r in portal_map.items():
        if key not in seen:
            out.append(_mm("Missing in books", None, r))
    return out


def _mm(bucket, p, r):
    src = p or r
    return {
        "bucket": bucket,
        "vendor_gstin": (p.vendor_gstin if p else r.vendor_gstin) if src else "",
        "vendor_name": (p.vendor_name if p else r.vendor_name) if src else "",
        "number": (p.number if p else r.invoice_number) if src else "",
        "date": gst_portal_date(p.invoice_date if p and getattr(p, "invoice_date", None) else None) or gst_portal_date(r.invoice_date if r and getattr(r, "invoice_date", None) else None),
        "book_total": p.total if p else None,
        "portal_total": r.total if r else None,
        "book_taxable": p.taxable_value if p else None,
        "portal_taxable": r.taxable_value if r else None,
    }
