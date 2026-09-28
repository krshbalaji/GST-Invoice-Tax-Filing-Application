from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models, schemas
from app.main import (
    create_invoice,
    update_invoice,
    preview_invoice,
    duplicate_invoice,
    credit_note_from,
)
from app.security import hash_password
from app.gst_engine import period_of



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


def _setup(db):
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
    db.commit()
    return user, gstin, party


def _invoice_body(gstin_id, party_id, invoice_date, invoice_type="TAX_INVOICE"):
    return schemas.InvoiceIn(
        gstin_id=gstin_id,
        party_id=party_id,
        invoice_type=invoice_type,
        invoice_date=invoice_date,
        place_of_supply="27",
        reverse_charge=False,
        gst_preset="REG_18",
        notes="",
        round_off=0,
        custom_mode=False,
        lines=[
            schemas.LineIn(
                custom=True,
                description="Services",
                hsn_sac="998314",
                unit="NOS",
                qty=1,
                rate=1000,
                discount=0,
            )
        ],
    )


def _lock_period(db, company_id, gstin_id, period):
    db.add(
        models.ReturnPeriod(
            company_id=company_id,
            gstin_id=gstin_id,
            period=period,
            locked=True,
            gstr1_status="FILED",
        )
    )
    db.commit()


def _assert_locked(exc):
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 400
    assert exc.detail == "Period is locked"

def test_preview_rejects_customer_from_another_company():
    db = _session()
    user, gstin, _ = _setup(db)

    company_b = models.Company(
        legal_name="Other Co",
        trade_name="Other",
        pan="AABCB5678D",
        scheme="REGULAR",
        aato=1_00_00_000,
    )
    db.add(company_b)
    db.flush()

    foreign_party = models.Party(
        company_id=company_b.id,
        kind="CUSTOMER",
        name="Foreign Customer",
        gstin="27AABCB5678D1Z5",
        state_code="27",
        place_of_supply="27",
        city="Mumbai",
        pincode="400001",
        address1="1 Other Street",
    )
    db.add(foreign_party)
    db.commit()

    body = _invoice_body(gstin.id, foreign_party.id, date(2026, 4, 10))

    try:
        preview_invoice(body, user=user, db=db)
        assert False, "Cross-company customer must be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Customer not found"


def test_preview_rejects_catalog_item_from_another_company():
    db = _session()
    user, gstin, _ = _setup(db)

    company_b = models.Company(
        legal_name="Other Co",
        trade_name="Other",
        pan="AABCB5678D",
        scheme="REGULAR",
        aato=1_00_00_000,
    )
    db.add(company_b)
    db.flush()

    foreign_item = models.Item(
        company_id=company_b.id,
        kind="SERVICE",
        code="FOREIGN-001",
        description="Foreign Item",
        hsn_sac="998599",
        unit="NOS",
        rate=9999,
        taxability="TAXABLE",
        gst_preset="REG_18",
    )
    db.add(foreign_item)
    db.commit()

    body = _invoice_body(gstin.id, None, date(2026, 4, 10))
    body.lines[0].custom = False
    body.lines[0].item_id = foreign_item.id
    body.lines[0].description = ""
    body.lines[0].hsn_sac = ""
    body.lines[0].unit = "NOS"
    body.lines[0].rate = 0

    try:
        preview_invoice(body, user=user, db=db)
        assert False, "Cross-company catalog item must be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Catalog item not found"


def test_update_rejects_customer_from_another_company():
    db = _session()
    user, gstin, party = _setup(db)
    inv_date = date(2026, 4, 10)

    out = create_invoice(
        _invoice_body(gstin.id, party.id, inv_date),
        user=user,
        db=db,
    )
    invoice_id = out["id"]

    company_b = models.Company(
        legal_name="Other Co",
        trade_name="Other",
        pan="AABCB5678D",
        scheme="REGULAR",
        aato=1_00_00_000,
    )
    db.add(company_b)
    db.flush()

    foreign_party = models.Party(
        company_id=company_b.id,
        kind="CUSTOMER",
        name="Foreign Customer",
        gstin="27AABCB5678D1Z5",
        state_code="27",
        place_of_supply="27",
        city="Mumbai",
        pincode="400001",
        address1="1 Other Street",
    )
    db.add(foreign_party)
    db.commit()

    body = _invoice_body(gstin.id, foreign_party.id, inv_date)

    try:
        update_invoice(
            invoice_id,
            body,
            user=user,
            db=db,
        )
        assert False, "Cross-company customer must be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Customer not found"

    db.expire_all()
    inv = db.get(models.Invoice, invoice_id)
    assert inv.party_id == party.id
    assert inv.party_name == party.name

def test_locked_create_rejects():
    db = _session()
    user, gstin, party = _setup(db)
    inv_date = date(2026, 4, 10)
    _lock_period(db, user.company_id, gstin.id, period_of(inv_date))

    try:
        create_invoice(_invoice_body(gstin.id, party.id, inv_date), user=user, db=db)
        assert False, "expected HTTP 400"
    except HTTPException as exc:
        _assert_locked(exc)

    assert db.query(models.Invoice).count() == 0


def test_unlocked_create_succeeds():
    db = _session()
    user, gstin, party = _setup(db)
    inv_date = date(2026, 4, 10)

    out = create_invoice(_invoice_body(gstin.id, party.id, inv_date), user=user, db=db)
    assert out["id"]
    assert out["status"] == "ISSUED"
    assert out["invoice_date"] == inv_date.isoformat()

    inv = db.get(models.Invoice, out["id"])
    assert inv is not None
    assert inv.period == period_of(inv_date)
    assert inv.locked is False


def test_locked_update_rejects_target_period():
    db = _session()
    user, gstin, party = _setup(db)
    open_date = date(2026, 4, 10)
    locked_date = date(2026, 5, 15)

    out = create_invoice(_invoice_body(gstin.id, party.id, open_date), user=user, db=db)
    invoice_id = out["id"]
    original_date = db.get(models.Invoice, invoice_id).invoice_date
    original_number = db.get(models.Invoice, invoice_id).number

    _lock_period(db, user.company_id, gstin.id, period_of(locked_date))

    try:
        update_invoice(
            invoice_id,
            _invoice_body(gstin.id, party.id, locked_date),
            user=user,
            db=db,
        )
        assert False, "expected HTTP 400"
    except HTTPException as exc:
        _assert_locked(exc)

    db.expire_all()
    inv = db.get(models.Invoice, invoice_id)
    assert inv.invoice_date == original_date
    assert inv.number == original_number
    assert inv.period == period_of(open_date)


def test_locked_duplicate_rejects():
    db = _session()
    user, gstin, party = _setup(db)
    src_date = date.today() - timedelta(days=40)
    out = create_invoice(_invoice_body(gstin.id, party.id, src_date), user=user, db=db)
    _lock_period(db, user.company_id, gstin.id, period_of(date.today()))

    count_before = db.query(models.Invoice).count()
    try:
        duplicate_invoice(out["id"], user=user, db=db)
        assert False, "expected HTTP 400"
    except HTTPException as exc:
        _assert_locked(exc)

    assert db.query(models.Invoice).count() == count_before


def test_locked_credit_note_rejects():
    db = _session()
    user, gstin, party = _setup(db)
    src_date = date.today() - timedelta(days=40)
    out = create_invoice(_invoice_body(gstin.id, party.id, src_date), user=user, db=db)
    _lock_period(db, user.company_id, gstin.id, period_of(date.today()))

    count_before = db.query(models.Invoice).count()
    try:
        credit_note_from(out["id"], user=user, db=db)
        assert False, "expected HTTP 400"
    except HTTPException as exc:
        _assert_locked(exc)

    assert db.query(models.Invoice).count() == count_before
    assert db.query(models.Invoice).filter(models.Invoice.invoice_type == "CREDIT_NOTE").count() == 0

def test_non_owner_cannot_create_user():
    db = _session()
    user, _, _ = _setup(db)
    user.role = "ACCOUNTANT"
    db.commit()

    body = schemas.UserIn(
        name="Blocked User",
        email="blocked@test.example",
        password="Blocked@123",
        role="VIEWER",
    )

    from app.main import create_user

    try:
        create_user(body, user=user, db=db)
        assert False, "Non-owner must not create users"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Only owner can add users"

    assert db.query(models.User).filter(models.User.email == "blocked@test.example").count() == 0

def test_gstin_of_rejects_gstin_from_another_company():
    db = _session()
    user, _, _ = _setup(db)

    company_b = models.Company(
        legal_name="Other Co",
        trade_name="Other",
        pan="AABCB5678D",
        scheme="REGULAR",
        aato=1_00_00_000,
    )
    db.add(company_b)
    db.flush()

    foreign_gstin = models.Gstin(
        company_id=company_b.id,
        gstin="27AABCB5678D1Z5",
        legal_name="Other Co",
        trade_name="Other",
        address1="1 Other Street",
        city="Mumbai",
        state_code="27",
        pincode="400001",
    )
    db.add(foreign_gstin)
    db.commit()

    from app.main import gstin_of

    try:
        gstin_of(db, user, foreign_gstin.id)
        assert False, "Cross-company GSTIN must be rejected"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "GSTIN not found"

def test_user_out_does_not_expose_password_hash():
    db = _session()
    user, _, _ = _setup(db)

    from app.serialize import user_out

    output = user_out(user)

    assert output["id"] == user.id
    assert output["email"] == user.email
    assert output["company_id"] == user.company_id
    assert "password_hash" not in output
    assert "password" not in output
