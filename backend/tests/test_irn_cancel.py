from datetime import date, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models
from app.main import generate_irn, cancel_irn
from app.security import hash_password
from app.gst_engine import period_of, fy_label


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _user_ns(user):
    return user


def _eligible_invoice(db):
    company = models.Company(
        legal_name="Test Co",
        trade_name="Test",
        pan="AABCA1234C",
        scheme="REGULAR",
        aato=6_20_00_000,
    )
    db.add(company)
    db.flush()

    gstin = models.Gstin(
        company_id=company.id,
        gstin="29AABCA1234C1ZB",
        legal_name="Test Co",
        trade_name="Test",
        address1="1 Main",
        city="Bengaluru",
        state_code="29",
        pincode="560103",
    )
    db.add(gstin)
    db.flush()

    user = models.User(
        company_id=company.id,
        name="Owner",
        email="owner@test.example",
        password_hash=hash_password("Owner@123"),
        role="OWNER",
    )
    db.add(user)
    db.flush()

    party = models.Party(
        company_id=company.id,
        kind="CUSTOMER",
        name="Buyer Pvt Ltd",
        gstin="27AABCN9988D1Z5",
        state_code="27",
        place_of_supply="27",
        city="Mumbai",
        pincode="400021",
        address1="Nariman Point",
    )
    db.add(party)
    db.flush()

    today = date.today()
    inv = models.Invoice(
        company_id=company.id,
        gstin_id=gstin.id,
        party_id=party.id,
        invoice_type="TAX_INVOICE",
        number="T/0001",
        invoice_date=today,
        place_of_supply="27",
        supply_type="INTER",
        gst_preset="REG_18",
        scheme="REGULAR",
        party_name=party.name,
        party_gstin=party.gstin,
        party_address="Nariman Point, Mumbai - 400021",
        party_state="27",
        taxable_value=1000,
        cgst=0,
        sgst=0,
        igst=180,
        total=1180,
        status="ISSUED",
        einvoice_status="REQUIRED",
        period=period_of(today),
        fy=fy_label(today),
    )
    db.add(inv)
    db.flush()

    db.add(
        models.LineItem(
            invoice_id=inv.id,
            custom=False,
            description="Services",
            hsn_sac="998314",
            unit="NOS",
            qty=1,
            rate=1000,
            discount=0,
            taxable_value=1000,
            gst_rate=18,
            cgst_rate=0,
            sgst_rate=0,
            igst_rate=18,
            cgst=0,
            sgst=0,
            igst=180,
            total=1180,
        )
    )

    db.commit()
    return user, inv.id


def test_sandbox_irn_cancel_clears_active_irn_and_allows_regenerate():
    db = _session()
    user, invoice_id = _eligible_invoice(db)

    gen1 = generate_irn(invoice_id, user=user, db=db)
    assert gen1["ok"] is True
    assert gen1["sandbox"] is True
    first_irn = gen1["irn"]
    assert first_irn

    inv = db.get(models.Invoice, invoice_id)
    assert inv.status == "ISSUED"
    assert inv.einvoice_status == "GENERATED"
    assert inv.irn == first_irn
    assert inv.ack_no
    assert inv.irn_date is not None
    assert inv.signed_qr

    cancelled = cancel_irn(invoice_id, user=user, db=db)
    assert cancelled == {"ok": True}

    db.expire_all()
    inv = db.get(models.Invoice, invoice_id)
    assert not inv.irn
    assert not inv.ack_no
    assert inv.irn_date is None
    assert not inv.signed_qr
    assert inv.status == "ISSUED"
    assert inv.einvoice_status == "REQUIRED"
    assert inv.cancel_reason == "IRN cancelled in sandbox"

    log = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.action == "IRN_CANCEL",
            models.AuditLog.entity_id == invoice_id,
        )
        .one()
    )
    assert log.detail == first_irn

    gen2 = generate_irn(invoice_id, user=user, db=db)
    assert gen2["ok"] is True
    assert gen2["sandbox"] is True
    second_irn = gen2["irn"]
    assert second_irn
    assert second_irn != first_irn

    db.expire_all()
    inv = db.get(models.Invoice, invoice_id)
    assert inv.irn == second_irn
    assert inv.einvoice_status == "GENERATED"
    assert inv.status == "ISSUED"
    assert inv.ack_no
    assert inv.irn_date is not None
    assert inv.signed_qr


def test_sandbox_irn_cancel_not_required_when_ineligible():
    db = _session()
    user, invoice_id = _eligible_invoice(db)

    generate_irn(invoice_id, user=user, db=db)

    inv = db.get(models.Invoice, invoice_id)
    inv.party_gstin = ""
    db.commit()

    cancel_irn(invoice_id, user=user, db=db)
    db.expire_all()

    inv = db.get(models.Invoice, invoice_id)
    assert not inv.irn
    assert inv.status == "ISSUED"
    assert inv.einvoice_status == "NOT_REQUIRED"
