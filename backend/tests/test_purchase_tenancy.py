from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app import models, schemas
from app.main import create_purchase
from app.security import hash_password


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


def _company(db, pan, email):
    company = models.Company(
        legal_name=f"Company {pan}",
        trade_name=f"Company {pan}",
        pan=pan,
        scheme="REGULAR",
        aato=1_00_00_000,
    )
    db.add(company)
    db.flush()

    gstin = models.Gstin(
        company_id=company.id,
        gstin=f"29{pan}1ZB",
        legal_name=company.legal_name,
        trade_name=company.trade_name,
        address1="1 Main",
        city="Bengaluru",
        state_code="29",
        pincode="560001",
    )
    db.add(gstin)

    user = models.User(
        company_id=company.id,
        name="Owner",
        email=email,
        password_hash=hash_password("Owner@123"),
        role="OWNER",
    )
    db.add(user)
    db.flush()

    return company, gstin, user


def test_purchase_rejects_vendor_from_another_company():
    db = _session()

    company_a, gstin_a, user_a = _company(
        db, "AABCA1111C", "owner-a@test.example"
    )
    company_b, _, _ = _company(
        db, "AABCB2222C", "owner-b@test.example"
    )

    vendor_b = models.Party(
        company_id=company_b.id,
        kind="VENDOR",
        name="Foreign Vendor",
        gstin="27AABCB2222C1Z5",
        state_code="27",
        place_of_supply="27",
        city="Mumbai",
        pincode="400001",
        address1="1 Other Street",
    )
    db.add(vendor_b)
    db.commit()
    db.refresh(vendor_b)

    body = schemas.PurchaseIn.model_validate({
        "gstin_id": gstin_a.id,
        "vendor_id": vendor_b.id,
        "number": "P/0001",
        "invoice_date": date.today().isoformat(),
        "place_of_supply": "27",
        "purchase_type": "TAXABLE",
        "gst_preset": "REG_18",
        "lines": [
            {
                "description": "Test Purchase",
                "hsn_sac": "998314",
                "unit": "NOS",
                "qty": 1,
                "rate": 1000,
                "discount": 0,
            }
        ],
    })

    try:
        create_purchase(body, user=user_a, db=db)
        assert False, "Cross-company vendor must be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Vendor not found"
