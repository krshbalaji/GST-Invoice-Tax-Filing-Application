from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

STATES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "96": "Foreign Country",
}

PRESETS = [
    {"code": "REG_5", "name": "Regular 5%", "scheme": "REGULAR", "rate": 5.0, "composition": False, "exempt": False},
    {"code": "REG_12", "name": "Regular 12%", "scheme": "REGULAR", "rate": 12.0, "composition": False, "exempt": False},
    {"code": "REG_18", "name": "Regular 18%", "scheme": "REGULAR", "rate": 18.0, "composition": False, "exempt": False},
    {"code": "REG_28", "name": "Regular 28%", "scheme": "REGULAR", "rate": 28.0, "composition": False, "exempt": False},
    {"code": "COMP_1", "name": "Composition 1%", "scheme": "COMPOSITION", "rate": 1.0, "composition": True, "exempt": False},
    {"code": "COMP_5", "name": "Composition 5%", "scheme": "COMPOSITION", "rate": 5.0, "composition": True, "exempt": False},
    {"code": "COMP_6", "name": "Composition 6%", "scheme": "COMPOSITION", "rate": 6.0, "composition": True, "exempt": False},
    {"code": "EXEMPT", "name": "Exempt / Nil-rated", "scheme": "REGULAR", "rate": 0.0, "composition": False, "exempt": True},
]

EINVOICE_THRESHOLD = 5_00_00_000
EINVOICE_WINDOW_THRESHOLD = 10_00_00_000
EINVOICE_DAYS = 30


def money(value) -> float:
    d = Decimal(str(value if value is not None else 0))
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def gstin_checksum(body14: str) -> str:
    factor = 1
    total = 0
    for ch in body14:
        code = CHARSET.index(ch)
        prod = code * factor
        total += (prod // 36) + (prod % 36)
        factor = 2 if factor == 1 else 1
    check = (36 - (total % 36)) % 36
    return CHARSET[check]


def validate_gstin(gstin: Optional[str]) -> tuple[bool, str]:
    if not gstin:
        return False, "GSTIN is required"
    g = gstin.strip().upper()
    if len(g) != 15:
        return False, "GSTIN must be 15 characters"
    if not GSTIN_RE.match(g):
        return False, "GSTIN format is invalid"
    if g[:2] not in STATES:
        return False, f"Invalid GSTIN state code {g[:2]}"
    if gstin_checksum(g[:14]) != g[14]:
        return False, "GSTIN checksum digit is invalid"
    return True, g


def validate_pan(pan: Optional[str]) -> tuple[bool, str]:
    if not pan:
        return False, "PAN is required"
    p = pan.strip().upper()
    if not PAN_RE.match(p):
        return False, "PAN format is invalid (AAAAA9999A)"
    return True, p


def state_from_gstin(gstin: Optional[str]) -> str:
    if gstin and len(gstin) >= 2:
        return gstin[:2]
    return ""


def supply_type(supplier_state: str, place_of_supply: str, is_export: bool = False, is_sez: bool = False) -> str:
    if is_export or place_of_supply in ("96",):
        return "EXPORT"
    if is_sez:
        return "INTER"
    if (supplier_state or "") == (place_of_supply or ""):
        return "INTRA"
    return "INTER"


def split_rates(preset: dict, supply: str) -> dict:
    rate = float(preset.get("rate") or 0)
    composition = bool(preset.get("composition"))
    exempt = bool(preset.get("exempt"))
    if composition or exempt or rate == 0:
        return {"cgst": 0.0, "sgst": 0.0, "igst": 0.0, "rate": 0.0 if (composition or exempt) else rate}
    if supply == "INTER" or supply == "EXPORT":
        return {"cgst": 0.0, "sgst": 0.0, "igst": rate, "rate": rate}
    half = money(rate / 2.0)
    return {"cgst": half, "sgst": half, "igst": 0.0, "rate": rate}


def calc_line(qty, rate, discount, preset: dict, supply: str) -> dict:
    qty = float(qty or 0)
    rate = float(rate or 0)
    discount = float(discount or 0)
    gross = money(qty * rate)
    taxable = money(max(gross - discount, 0))
    rates = split_rates(preset, supply)
    cgst = money(taxable * rates["cgst"] / 100.0)
    sgst = money(taxable * rates["sgst"] / 100.0)
    igst = money(taxable * rates["igst"] / 100.0)
    total = money(taxable + cgst + sgst + igst)
    return {
        "qty": qty,
        "rate": money(rate),
        "discount": money(discount),
        "taxable_value": taxable,
        "cgst_rate": rates["cgst"],
        "sgst_rate": rates["sgst"],
        "igst_rate": rates["igst"],
        "gst_rate": rates["rate"],
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": total,
    }


def calc_invoice(lines: list[dict], preset: dict, supply: str, round_off: float = 0.0) -> dict:
    computed = [calc_line(x.get("qty"), x.get("rate"), x.get("discount"), preset, supply) for x in lines]
    taxable = money(sum(x["taxable_value"] for x in computed))
    cgst = money(sum(x["cgst"] for x in computed))
    sgst = money(sum(x["sgst"] for x in computed))
    igst = money(sum(x["igst"] for x in computed))
    total = money(taxable + cgst + sgst + igst + float(round_off or 0))
    return {
        "lines": computed,
        "taxable_value": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "round_off": money(round_off),
        "total": total,
        "supply_type": supply,
    }


def fy_label(d: date) -> str:
    if d.month >= 4:
        return f"{str(d.year)[-2:]}-{str(d.year + 1)[-2:]}"
    return f"{str(d.year - 1)[-2:]}-{str(d.year)[-2:]}"


def period_of(d: date) -> str:
    return d.strftime("%m%Y")


def period_label(fp: str) -> str:
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    m = int(fp[:2])
    y = fp[2:]
    return f"{months[m]} {y}"


def hsn_required_digits(aato: float) -> int:
    if float(aato or 0) > 5_00_00_000:
        return 6
    return 4


def filing_countdown(due: date, today: Optional[date] = None) -> dict:
    today = today or date.today()
    days = (due - today).days
    if days < 0:
        state = "overdue"
    elif days <= 3:
        state = "due_soon"
    else:
        state = "ok"
    return {"date": due.isoformat(), "label": due.strftime("%d %b %Y"), "days": days, "state": state}


def due_dates(year: int, month: int) -> dict:
    if month == 12:
        ny, nm = year + 1, 1
    else:
        ny, nm = year, month + 1
    gstr1 = date(ny, nm, 11)
    gstr3b = date(ny, nm, 20)
    return {
        "gstr1": gstr1.isoformat(),
        "gstr3b": gstr3b.isoformat(),
        "gstr1_in": gstr1.strftime("%d-%m-%Y"),
        "gstr3b_in": gstr3b.strftime("%d-%m-%Y"),
        "gstr1_meta": filing_countdown(gstr1),
        "gstr3b_meta": filing_countdown(gstr3b),
    }


def invoice_doc_type(invoice_type: str) -> str:
    return {"TAX_INVOICE": "INV", "CREDIT_NOTE": "CRN", "DEBIT_NOTE": "DBN", "BILL_OF_SUPPLY": "INV"}.get(
        invoice_type, "INV"
    )


def default_invoice_type(scheme: str) -> str:
    return "BILL_OF_SUPPLY" if scheme == "COMPOSITION" else "TAX_INVOICE"


def preset_by_code(code: str) -> dict:
    for p in PRESETS:
        if p["code"] == code:
            return p
    return PRESETS[2]


INVOICE_TYPE_LABELS = {
    "TAX_INVOICE": "Tax Invoice",
    "BILL_OF_SUPPLY": "Bill of Supply",
    "CREDIT_NOTE": "Credit Note",
    "DEBIT_NOTE": "Debit Note",
}

EINVOICE_LABELS = {
    "NOT_REQUIRED": "Not required",
    "REQUIRED": "Required",
    "GENERATED": "Generated",
    "FAILED": "Failed",
    "CANCELLED": "Cancelled",
}

STATUS_LABELS = {
    "DRAFT": "Draft",
    "ISSUED": "Issued",
    "CANCELLED": "Cancelled",
}

_ONES = (
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
)
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def _two_digits(n: int) -> str:
    n = int(n)
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three_digits(n: int) -> str:
    n = int(n)
    h, rest = divmod(n, 100)
    parts = []
    if h:
        parts.append(_ONES[h] + " Hundred")
    if rest:
        parts.append(_two_digits(rest))
    return " ".join(parts)


def amount_in_words(value) -> str:
    d = Decimal(str(value if value is not None else 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negative = d < 0
    d = abs(d)
    rupees = int(d)
    paise = int((d - rupees) * 100)
    if rupees == 0 and paise == 0:
        return "Zero Rupees Only"
    crore, rem = divmod(rupees, 10000000)
    lakh, rem = divmod(rem, 100000)
    thousand, rem = divmod(rem, 1000)
    hundreds = rem
    bits = []
    if crore:
        bits.append(_three_digits(crore) + " Crore")
    if lakh:
        bits.append(_two_digits(lakh) + " Lakh")
    if thousand:
        bits.append(_two_digits(thousand) + " Thousand")
    if hundreds:
        bits.append(_three_digits(hundreds))
    rupee_part = " ".join(bits) + (" Rupee" if rupees == 1 else " Rupees") if bits else ""
    paise_part = ""
    if paise:
        paise_part = " and " + _two_digits(paise) + (" Paisa" if paise == 1 else " Paise")
    text = (rupee_part + paise_part + " Only").strip()
    return ("Minus " + text) if negative else text


def format_inr(value) -> str:
    d = Decimal(str(value if value is not None else 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    d = abs(d)
    whole, frac = f"{d:.2f}".split(".")
    s = whole
    if len(s) <= 3:
        grouped = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        grouped = ",".join(reversed(parts)) + "," + last3
    return f"{sign}Rs {grouped}.{frac}"


def gst_portal_date(d) -> str:
    if not d:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%d-%m-%Y")
    s = str(d)
    if len(s) >= 10 and s[4] == "-":
        return f"{s[8:10]}-{s[5:7]}-{s[0:4]}"
    return s


def gstr1_inv_typ(party_gstin: str, sez: bool = False, tax_charged: bool = True) -> str:
    if sez:
        return "SEWP" if tax_charged else "SEWOP"
    return "R"
