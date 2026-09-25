from datetime import date
from app.gst_engine import (
    calc_line, calc_invoice, preset_by_code, supply_type, gstin_checksum,
    validate_gstin, money, amount_in_words, format_inr, gst_portal_date, gstr1_inv_typ,
)
from app.einvoice import einvoice_required, einvoice_status_of, build_inv01
from app.returns import gstr1_tables, gstr3b_summary, reconcile_gstr1_vs_irn
from types import SimpleNamespace


def test_intra_regular():
    p = preset_by_code("REG_18")
    c = calc_line(2, 100, 0, p, "INTRA")
    assert c["taxable_value"] == 200
    assert c["cgst"] == 18
    assert c["sgst"] == 18
    assert c["igst"] == 0
    assert c["total"] == 236


def test_inter_regular():
    p = preset_by_code("REG_18")
    c = calc_line(1, 1000, 0, p, "INTER")
    assert c["igst"] == 180
    assert c["cgst"] == 0
    assert c["sgst"] == 0


def test_composition_no_gst():
    p = preset_by_code("COMP_1")
    c = calc_line(1, 10000, 0, p, "INTRA")
    assert c["cgst"] == 0 and c["sgst"] == 0 and c["igst"] == 0
    assert c["total"] == 10000


def test_exempt():
    p = preset_by_code("EXEMPT")
    c = calc_line(3, 500, 0, p, "INTER")
    assert c["total"] == 1500 and c["igst"] == 0


def test_supply_type():
    assert supply_type("29", "29") == "INTRA"
    assert supply_type("29", "27") == "INTER"
    assert supply_type("29", "96") == "EXPORT"
    assert supply_type("29", "29", is_sez=True) == "INTER"


def test_portal_date_and_inv_typ():
    assert gst_portal_date(date(2026, 9, 5)) == "05-09-2026"
    assert gstr1_inv_typ("29AAA", False, True) == "R"
    assert gstr1_inv_typ("29AAA", True, True) == "SEWP"
    assert gstr1_inv_typ("29AAA", True, False) == "SEWOP"


def test_gstin_checksum_roundtrip():
    body = "29AABCA1234C1Z"
    g = body + gstin_checksum(body)
    ok, val = validate_gstin(g)
    assert ok and val == g


def test_invoice_totals():
    p = preset_by_code("REG_12")
    r = calc_invoice([{"qty": 1, "rate": 100, "discount": 0}, {"qty": 2, "rate": 50, "discount": 0}], p, "INTRA")
    assert r["taxable_value"] == 200
    assert money(r["cgst"] + r["sgst"]) == 24
    assert r["total"] == 224


def test_amount_in_words():
    assert "Rupees" in amount_in_words(125500)
    assert amount_in_words(0).startswith("Zero")
    assert format_inr(62000000).startswith("Rs ")
    assert "," in format_inr(125500)


def test_einvoice_required_rules():
    assert einvoice_required("29ABCDE1234F1Z5", 6_20_00_000, "TAX_INVOICE", "REGULAR") is True
    assert einvoice_required("", 6_20_00_000, "TAX_INVOICE", "REGULAR") is False
    assert einvoice_required("29ABCDE1234F1Z5", 1_00_00_000, "TAX_INVOICE", "REGULAR") is False
    assert einvoice_required("29ABCDE1234F1Z5", 6_20_00_000, "BILL_OF_SUPPLY", "REGULAR") is False
    assert einvoice_required("29ABCDE1234F1Z5", 6_20_00_000, "TAX_INVOICE", "COMPOSITION") is False


def test_einvoice_status_derivation():
    inv = SimpleNamespace(
        irn="", einvoice_status="NOT_REQUIRED", status="ISSUED",
        party_gstin="29ABCDE1234F1Z5", invoice_type="TAX_INVOICE", scheme="REGULAR",
    )
    assert einvoice_status_of(inv, 6_20_00_000) == "REQUIRED"
    inv.irn = "abc"
    assert einvoice_status_of(inv, 6_20_00_000) == "GENERATED"


def test_gstr1_groups_b2b_by_ctin():
    line = SimpleNamespace(gst_rate=18, taxable_value=100, igst=18, cgst=0, sgst=0, hsn_sac="9983", description="Dev", unit="HRS", qty=1)
    inv1 = SimpleNamespace(
        status="ISSUED", invoice_type="TAX_INVOICE", supply_type="INTER", party_gstin="27AAA",
        number="A1", invoice_date=__import__("datetime").date(2026, 9, 1), total=118, place_of_supply="27",
        reverse_charge=False, irn="", gst_preset="REG_18", cgst=0, sgst=0, igst=18, taxable_value=100, lines=[line],
    )
    inv2 = SimpleNamespace(
        status="ISSUED", invoice_type="TAX_INVOICE", supply_type="INTER", party_gstin="27AAA",
        number="A2", invoice_date=__import__("datetime").date(2026, 9, 2), total=118, place_of_supply="27",
        reverse_charge=False, irn="", gst_preset="REG_18", cgst=0, sgst=0, igst=18, taxable_value=100, lines=[line],
    )
    tables = gstr1_tables([inv1, inv2])
    assert len(tables["b2b"]) == 1
    assert tables["b2b"][0]["ctin"] == "27AAA"
    assert len(tables["b2b"][0]["inv"]) == 2
    assert tables["b2b"][0]["inv"][0]["idt"] == "01-09-2026"


def test_gstr1_cdnr_original_ref():
    line = SimpleNamespace(gst_rate=18, taxable_value=100, igst=18, cgst=0, sgst=0, hsn_sac="9983", description="Dev", unit="HRS", qty=1)
    orig = SimpleNamespace(id=10, number="ADS/25-26/0001", invoice_date=date(2026, 9, 1))
    cn = SimpleNamespace(
        status="ISSUED", invoice_type="CREDIT_NOTE", supply_type="INTER", party_gstin="27AAA",
        number="CN-1", invoice_date=date(2026, 9, 10), total=118, place_of_supply="27",
        reverse_charge=False, irn="", gst_preset="REG_18", cgst=0, sgst=0, igst=18, taxable_value=100,
        lines=[line], original_invoice_id=10, party=None, sez=False,
    )
    tables = gstr1_tables([cn], {10: orig})
    assert tables["cdnr"][0]["nt_dt"] == "10-09-2026"
    assert tables["cdnr"][0]["ont_num"] == "ADS/25-26/0001"
    assert tables["cdnr"][0]["ont_dt"] == "01-09-2026"
    assert tables["cdnr"][0]["inum"] == "ADS/25-26/0001"


def test_sez_inv01_and_igst_on_intra():
    gstin = SimpleNamespace(gstin="29AABCA1234C1ZB", legal_name="A", trade_name="A", address1="x", address2="", city="Bengaluru", pincode="560103", state_code="29")
    company = SimpleNamespace()
    inv = SimpleNamespace(
        party_gstin="29SEZ", party_name="SEZ Co", party_address="Whitefield, 560066",
        place_of_supply="29", party_state="29", reverse_charge=False, invoice_type="TAX_INVOICE",
        number="A1", invoice_date=date(2026, 9, 1), taxable_value=100, cgst=0, sgst=0, igst=18,
        round_off=0, total=118,
    )
    line = SimpleNamespace(description="Dev", hsn_sac="998314", qty=1, unit="HRS", rate=100, discount=0, taxable_value=100, gst_rate=18, igst=18, cgst=0, sgst=0, total=118)
    payload = build_inv01(inv, gstin, company, [line], sez=True)
    assert payload["TranDtls"]["SupTyp"] == "SEZWP"
    assert payload["TranDtls"]["IgstOnIntra"] == "Y"


def test_gstr3b_rcm_and_irn_reco():
    inv = SimpleNamespace(
        status="ISSUED", invoice_type="TAX_INVOICE", taxable_value=100, cgst=9, sgst=9, igst=0,
        reverse_charge=True, irn="", einvoice_status="NOT_REQUIRED", party_gstin="29AAA",
        scheme="REGULAR", number="A1", invoice_date=date(2026, 9, 1), party_name="X", total=118,
    )
    s = gstr3b_summary([inv], [])
    assert s["sup_details"]["isup_rev"]["camt"] == 9
    rows = reconcile_gstr1_vs_irn([inv], 6_20_00_000)
    assert rows[0]["bucket"] == "Missing IRN"
    assert rows[0]["date"] == "01-09-2026"
