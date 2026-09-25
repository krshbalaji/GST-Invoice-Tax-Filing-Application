from datetime import date, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from . import models
from .security import hash_password
from .gst_engine import PRESETS, period_of, fy_label, calc_line, preset_by_code, supply_type, gstin_checksum


def make_gstin(state: str, pan: str, entity: str = "1") -> str:
    body = f"{state}{pan}{entity}Z"
    return body + gstin_checksum(body)


def seed():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        if db.query(models.User).first():
            return
        company = models.Company(
            legal_name="Aarohi Digital Services Private Limited",
            trade_name="Aarohi Digital",
            pan="AABCA1234C",
            scheme="REGULAR",
            aato=6_20_00_000,
            bank_name="HDFC Bank",
            bank_account="50100123456789",
            bank_ifsc="HDFC0001234",
            bank_branch="Koramangala, Bengaluru",
            terms="Payment due within 15 days. Interest @18% p.a. after due date. Subject to Bengaluru jurisdiction.",
        )
        db.add(company)
        db.flush()

        gstin_ka = models.Gstin(
            company_id=company.id,
            gstin=make_gstin("29", "AABCA1234C", "1"),
            legal_name=company.legal_name,
            trade_name=company.trade_name,
            address1="42, 3rd Floor, Prestige Tech Park",
            address2="Marathahalli Outer Ring Road",
            city="Bengaluru",
            state_code="29",
            pincode="560103",
            email="accounts@aarohi.example",
            phone="08041234567",
            invoice_prefix="ADS/25-26/",
            next_number=1,
            is_primary=True,
        )
        gstin_mh = models.Gstin(
            company_id=company.id,
            gstin=make_gstin("27", "AABCA1234C", "2"),
            legal_name=company.legal_name,
            trade_name="Aarohi Digital (West)",
            address1="801, WeWork, Bandra Kurla Complex",
            city="Mumbai",
            state_code="27",
            pincode="400051",
            email="mumbai@aarohi.example",
            phone="02241234567",
            invoice_prefix="ADS-MUM/",
            next_number=1,
        )
        db.add_all([gstin_ka, gstin_mh])
        db.flush()

        users = [
            models.User(company_id=company.id, name="Priya Sharma", email="owner@aarohi.example", password_hash=hash_password("Owner@123"), role="OWNER"),
            models.User(company_id=company.id, name="Rahul Mehta", email="accounts@aarohi.example", password_hash=hash_password("Acct@123"), role="ACCOUNTANT"),
            models.User(company_id=company.id, name="Neha Iyer", email="viewer@aarohi.example", password_hash=hash_password("View@123"), role="VIEWER"),
            models.User(company_id=company.id, name="CA Ankit Joshi", email="ca@aarohi.example", password_hash=hash_password("CA@12345"), role="CA"),
        ]
        db.add_all(users)

        for p in PRESETS:
            db.add(models.GstPreset(company_id=company.id, **p, is_default=(p["code"] == "REG_18")))

        customers = [
            models.Party(company_id=company.id, kind="CUSTOMER", name="Nimbus Retail Private Limited", trade_name="Nimbus", gstin=make_gstin("27", "AABCN9988D", "1"), pan="AABCN9988D", email="ap@nimbus.example", phone="02299887766", address1="12, Nariman Point", city="Mumbai", state_code="27", pincode="400021", place_of_supply="27"),
            models.Party(company_id=company.id, kind="CUSTOMER", name="Deccan Healthcare LLP", trade_name="Deccan Health", gstin=make_gstin("29", "AAGCD4455E", "1"), pan="AAGCD4455E", email="finance@deccan.example", phone="08077665544", address1="Indiranagar 100 Feet Road", city="Bengaluru", state_code="29", pincode="560038", place_of_supply="29"),
            models.Party(company_id=company.id, kind="CUSTOMER", name="Coastal Traders", trade_name="Coastal", gstin="", pan="", email="buy@coastal.example", phone="9845011122", address1="MG Road", city="Bengaluru", state_code="29", pincode="560001", place_of_supply="29", notes="Unregistered B2C"),
            models.Party(company_id=company.id, kind="CUSTOMER", name="Tamil Nadu Logistics Pvt Ltd", trade_name="TN Logistics", gstin=make_gstin("33", "AABCT2211F", "1"), pan="AABCT2211F", email="accounts@tnlog.example", phone="04433445566", address1="Guindy Industrial Estate", city="Chennai", state_code="33", pincode="600032", place_of_supply="33"),
            models.Party(company_id=company.id, kind="VENDOR", name="Cloudstack Infra Pvt Ltd", trade_name="Cloudstack", gstin=make_gstin("29", "AABCC7777G", "1"), pan="AABCC7777G", email="billing@cloudstack.example", phone="08022334455", address1="Whitefield", city="Bengaluru", state_code="29", pincode="560066", place_of_supply="29"),
            models.Party(company_id=company.id, kind="VENDOR", name="OfficeKart Wholesale", trade_name="OfficeKart", gstin=make_gstin("27", "AAACO3333H", "1"), pan="AAACO3333H", email="sales@officekart.example", phone="02255667788", address1="Andheri East", city="Mumbai", state_code="27", pincode="400069", place_of_supply="27"),
        ]
        db.add_all(customers)
        db.flush()

        items = [
            models.Item(company_id=company.id, kind="SERVICE", code="WEB-DEV", description="Custom web application development", hsn_sac="998314", unit="HRS", rate=2500, gst_preset="REG_18"),
            models.Item(company_id=company.id, kind="SERVICE", code="GST-RET", description="GST return filing & compliance retainer", hsn_sac="998221", unit="MON", rate=12000, gst_preset="REG_18"),
            models.Item(company_id=company.id, kind="SERVICE", code="CLOUD", description="Managed cloud hosting", hsn_sac="998315", unit="MON", rate=8500, gst_preset="REG_18"),
            models.Item(company_id=company.id, kind="GOODS", code="LAP-14", description="Business laptop 14-inch", hsn_sac="847130", unit="NOS", rate=62000, gst_preset="REG_18"),
            models.Item(company_id=company.id, kind="SERVICE", code="TRAIN", description="Staff GST training workshop", hsn_sac="999293", unit="DAY", rate=18000, gst_preset="REG_18"),
            models.Item(company_id=company.id, kind="SERVICE", code="AUDIT", description="ITC reconciliation & health check", hsn_sac="998221", unit="NOS", rate=35000, gst_preset="REG_18"),
            models.Item(company_id=company.id, kind="SERVICE", code="EXEMPT-EDU", description="Educational content (exempt)", hsn_sac="9992", unit="NOS", rate=5000, taxability="EXEMPT", gst_preset="EXEMPT"),
        ]
        db.add_all(items)
        db.flush()

        nimbus, deccan, coastal, tnlog, cloudstack, officekart = customers
        web, gstret, cloud, laptop, train, audit, edu = items
        today = date.today()
        month_start = date(today.year, today.month, 1)
        last_month = (month_start - timedelta(days=1)).replace(day=1)

        def make_inv(gstin, party, inv_type, d, lines_spec, preset="REG_18", rcm=False, status="ISSUED", einv="NOT_REQUIRED"):
            pos = party.place_of_supply or party.state_code or gstin.state_code
            supply = supply_type(gstin.state_code, pos)
            pset = preset_by_code(preset)
            computed_lines = []
            for spec in lines_spec:
                item, qty = spec[0], spec[1]
                c = calc_line(qty, item.rate, 0, pset, supply)
                computed_lines.append((item, qty, c))
            taxable = round(sum(c["taxable_value"] for _, _, c in computed_lines), 2)
            cgst = round(sum(c["cgst"] for _, _, c in computed_lines), 2)
            sgst = round(sum(c["sgst"] for _, _, c in computed_lines), 2)
            igst = round(sum(c["igst"] for _, _, c in computed_lines), 2)
            total = round(taxable + cgst + sgst + igst, 2)
            prefixes = {"TAX_INVOICE": (gstin.invoice_prefix, "next_number"), "CREDIT_NOTE": (gstin.cn_prefix, "cn_next"), "DEBIT_NOTE": (gstin.dn_prefix, "dn_next"), "BILL_OF_SUPPLY": (gstin.bos_prefix, "bos_next")}
            prefix, field = prefixes.get(inv_type, (gstin.invoice_prefix, "next_number"))
            num = getattr(gstin, field)
            number = f"{prefix}{num:04d}"
            setattr(gstin, field, num + 1)
            inv = models.Invoice(
                company_id=company.id,
                gstin_id=gstin.id,
                party_id=party.id,
                invoice_type=inv_type,
                number=number,
                invoice_date=d,
                due_date=d + timedelta(days=15),
                place_of_supply=pos,
                supply_type=supply,
                reverse_charge=rcm,
                gst_preset=preset,
                scheme="REGULAR",
                party_name=party.name,
                party_gstin=party.gstin,
                party_address=f"{party.address1}, {party.city} - {party.pincode}",
                party_state=party.state_code,
                taxable_value=taxable,
                cgst=cgst,
                sgst=sgst,
                igst=igst,
                total=total,
                status=status,
                einvoice_status=einv,
                period=period_of(d),
                fy=fy_label(d),
            )
            db.add(inv)
            db.flush()
            for item, qty, c in computed_lines:
                db.add(models.LineItem(
                    invoice_id=inv.id, item_id=item.id, custom=False,
                    description=item.description, hsn_sac=item.hsn_sac, unit=item.unit,
                    qty=qty, rate=item.rate, **{k: c[k] for k in ("discount", "taxable_value", "gst_rate", "cgst_rate", "sgst_rate", "igst_rate", "cgst", "sgst", "igst", "total")},
                ))
            return inv

        make_inv(gstin_ka, deccan, "TAX_INVOICE", last_month + timedelta(days=4), [(gstret, 1), (audit, 1)], einv="REQUIRED")
        make_inv(gstin_ka, nimbus, "TAX_INVOICE", last_month + timedelta(days=8), [(web, 40)], einv="GENERATED")
        make_inv(gstin_ka, tnlog, "TAX_INVOICE", last_month + timedelta(days=12), [(cloud, 3)], einv="GENERATED")
        make_inv(gstin_ka, coastal, "TAX_INVOICE", last_month + timedelta(days=18), [(train, 1)], einv="NOT_REQUIRED")
        make_inv(gstin_ka, deccan, "TAX_INVOICE", month_start + timedelta(days=2), [(gstret, 1), (cloud, 1)], einv="REQUIRED")
        make_inv(gstin_ka, nimbus, "TAX_INVOICE", month_start + timedelta(days=5), [(web, 24)], einv="REQUIRED")
        make_inv(gstin_ka, tnlog, "TAX_INVOICE", month_start + timedelta(days=7), [(audit, 1)], einv="REQUIRED")
        make_inv(gstin_ka, coastal, "TAX_INVOICE", month_start + timedelta(days=9), [(edu, 2)], preset="EXEMPT", einv="NOT_REQUIRED")

        for inv in db.query(models.Invoice).all():
            if inv.einvoice_status == "GENERATED":
                inv.irn = ("a" * 8 + hex(inv.id)[2:].zfill(8) + "b" * 48)[:64]
                inv.ack_no = f"1120{inv.id:012d}"
                inv.signed_qr = (
                    '{"SellerGstin":"%s","BuyerGstin":"%s","DocNo":"%s","DocTyp":"INV",'
                    '"DocDt":"%s","TotInvVal":%s,"Irn":"%s"}'
                    % (
                        gstin_ka.gstin,
                        inv.party_gstin,
                        inv.number,
                        inv.invoice_date.strftime("%d/%m/%Y"),
                        inv.total,
                        inv.irn,
                    )
                )
            elif inv.party_gstin and inv.invoice_type == "TAX_INVOICE" and company.aato >= 5_00_00_000:
                inv.einvoice_status = "REQUIRED"

        db.add(models.Purchase(
            company_id=company.id, gstin_id=gstin_ka.id, vendor_id=cloudstack.id,
            number="CS/2026/0881", invoice_date=month_start + timedelta(days=3),
            vendor_name=cloudstack.name, vendor_gstin=cloudstack.gstin,
            place_of_supply="29", supply_type="INTRA", taxable_value=25000, cgst=2250, sgst=2250, igst=0, total=29500,
            period=period_of(month_start),
        ))
        db.add(models.Purchase(
            company_id=company.id, gstin_id=gstin_ka.id, vendor_id=officekart.id,
            number="OK-44921", invoice_date=month_start + timedelta(days=6),
            vendor_name=officekart.name, vendor_gstin=officekart.gstin,
            place_of_supply="29", supply_type="INTER", taxable_value=18000, cgst=0, sgst=0, igst=3240, total=21240,
            period=period_of(month_start),
        ))
        db.add(models.Purchase(
            company_id=company.id, gstin_id=gstin_ka.id, vendor_id=cloudstack.id,
            number="CS/2026/0910", invoice_date=month_start + timedelta(days=10),
            vendor_name=cloudstack.name, vendor_gstin=cloudstack.gstin,
            place_of_supply="29", supply_type="INTRA", taxable_value=8000, cgst=720, sgst=720, igst=0, total=9440,
            period=period_of(month_start),
        ))

        db.add(models.Gstr2bRow(
            company_id=company.id, gstin_id=gstin_ka.id, period=period_of(month_start),
            vendor_gstin=cloudstack.gstin, vendor_name=cloudstack.name, invoice_number="CS/2026/0881",
            invoice_date=month_start + timedelta(days=3), taxable_value=25000, cgst=2250, sgst=2250, total=29500,
        ))
        db.add(models.Gstr2bRow(
            company_id=company.id, gstin_id=gstin_ka.id, period=period_of(month_start),
            vendor_gstin=officekart.gstin, vendor_name=officekart.name, invoice_number="OK-44921",
            invoice_date=month_start + timedelta(days=6), taxable_value=17500, igst=3150, total=20650,
        ))
        db.add(models.Gstr2bRow(
            company_id=company.id, gstin_id=gstin_ka.id, period=period_of(month_start),
            vendor_gstin=make_gstin("29", "AAACX0000X", "1"), vendor_name="Xtra Supplies Pvt Ltd", invoice_number="XS-1002",
            invoice_date=month_start + timedelta(days=8), taxable_value=4200, cgst=378, sgst=378, total=4956,
        ))

        db.add(models.AuditLog(company_id=company.id, user_id=1, action="SEED", entity="COMPANY", entity_id=company.id, detail="Demo company seeded"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
