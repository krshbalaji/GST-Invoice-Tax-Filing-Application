from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    legal_name = Column(String(200), nullable=False)
    trade_name = Column(String(200), nullable=False)
    pan = Column(String(10), nullable=False, unique=True)
    scheme = Column(String(20), default="REGULAR")
    aato = Column(Float, default=0)
    logo_data = Column(Text, default="")
    bank_name = Column(String(120), default="")
    bank_account = Column(String(40), default="")
    bank_ifsc = Column(String(20), default="")
    bank_branch = Column(String(120), default="")
    terms = Column(Text, default="Goods once sold will not be taken back. Payment due as per invoice terms.")
    created_at = Column(DateTime, default=datetime.utcnow)
    gstins = relationship("Gstin", back_populates="company", cascade="all, delete-orphan")
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")


class Gstin(Base):
    __tablename__ = "gstins"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    gstin = Column(String(15), unique=True, nullable=False)
    legal_name = Column(String(200), nullable=False)
    trade_name = Column(String(200), nullable=False)
    address1 = Column(String(200), default="")
    address2 = Column(String(200), default="")
    city = Column(String(80), default="")
    state_code = Column(String(2), nullable=False)
    pincode = Column(String(10), default="")
    email = Column(String(120), default="")
    phone = Column(String(20), default="")
    invoice_prefix = Column(String(20), default="INV")
    next_number = Column(Integer, default=1)
    cn_prefix = Column(String(20), default="CN")
    cn_next = Column(Integer, default=1)
    dn_prefix = Column(String(20), default="DN")
    dn_next = Column(Integer, default=1)
    bos_prefix = Column(String(20), default="BOS")
    bos_next = Column(Integer, default=1)
    is_primary = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    company = relationship("Company", back_populates="gstins")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default="ACCOUNTANT")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("Company", back_populates="users")


class Party(Base):
    __tablename__ = "parties"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    kind = Column(String(20), default="CUSTOMER")
    name = Column(String(200), nullable=False)
    trade_name = Column(String(200), default="")
    gstin = Column(String(15), default="")
    pan = Column(String(10), default="")
    email = Column(String(120), default="")
    phone = Column(String(20), default="")
    address1 = Column(String(200), default="")
    address2 = Column(String(200), default="")
    city = Column(String(80), default="")
    state_code = Column(String(2), default="")
    pincode = Column(String(10), default="")
    place_of_supply = Column(String(2), default="")
    sez = Column(Boolean, default=False)
    notes = Column(Text, default="")
    active = Column(Boolean, default=True)


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    kind = Column(String(20), default="SERVICE")
    code = Column(String(40), default="")
    description = Column(String(300), nullable=False)
    hsn_sac = Column(String(10), default="")
    unit = Column(String(20), default="NOS")
    rate = Column(Float, default=0)
    taxability = Column(String(20), default="TAXABLE")
    gst_preset = Column(String(20), default="REG_18")
    active = Column(Boolean, default=True)


class GstPreset(Base):
    __tablename__ = "gst_presets"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    code = Column(String(20), nullable=False)
    name = Column(String(80), nullable=False)
    scheme = Column(String(20), default="REGULAR")
    rate = Column(Float, default=0)
    composition = Column(Boolean, default=False)
    exempt = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    gstin_id = Column(Integer, ForeignKey("gstins.id"), nullable=False)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=True)
    invoice_type = Column(String(20), default="TAX_INVOICE")
    number = Column(String(40), nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    place_of_supply = Column(String(2), default="")
    supply_type = Column(String(20), default="INTRA")
    reverse_charge = Column(Boolean, default=False)
    gst_preset = Column(String(20), default="REG_18")
    scheme = Column(String(20), default="REGULAR")
    party_name = Column(String(200), default="")
    party_gstin = Column(String(15), default="")
    party_address = Column(Text, default="")
    party_state = Column(String(2), default="")
    taxable_value = Column(Float, default=0)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    round_off = Column(Float, default=0)
    total = Column(Float, default=0)
    notes = Column(Text, default="")
    status = Column(String(20), default="DRAFT")
    einvoice_status = Column(String(20), default="NOT_REQUIRED")
    irn = Column(String(64), default="")
    irn_date = Column(DateTime, nullable=True)
    ack_no = Column(String(40), default="")
    signed_qr = Column(Text, default="")
    cancel_reason = Column(String(200), default="")
    period = Column(String(6), default="")
    fy = Column(String(8), default="")
    custom_mode = Column(Boolean, default=False)
    original_invoice_id = Column(Integer, nullable=True)
    locked = Column(Boolean, default=False)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    gstin = relationship("Gstin")
    party = relationship("Party")
    lines = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("gstin_id", "number", name="uq_gstin_inv_no"),)


class LineItem(Base):
    __tablename__ = "line_items"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    custom = Column(Boolean, default=False)
    description = Column(String(300), default="")
    hsn_sac = Column(String(10), default="")
    unit = Column(String(20), default="NOS")
    qty = Column(Float, default=1)
    rate = Column(Float, default=0)
    discount = Column(Float, default=0)
    taxable_value = Column(Float, default=0)
    gst_rate = Column(Float, default=0)
    cgst_rate = Column(Float, default=0)
    sgst_rate = Column(Float, default=0)
    igst_rate = Column(Float, default=0)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    total = Column(Float, default=0)
    invoice = relationship("Invoice", back_populates="lines")


class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    gstin_id = Column(Integer, ForeignKey("gstins.id"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("parties.id"), nullable=True)
    number = Column(String(40), nullable=False)
    invoice_date = Column(Date, nullable=False)
    vendor_name = Column(String(200), default="")
    vendor_gstin = Column(String(15), default="")
    place_of_supply = Column(String(2), default="")
    supply_type = Column(String(20), default="INTRA")
    reverse_charge = Column(Boolean, default=False)
    taxable_value = Column(Float, default=0)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    total = Column(Float, default=0)
    itc_eligible = Column(Boolean, default=True)
    period = Column(String(6), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Gstr2bRow(Base):
    __tablename__ = "gstr2b_rows"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    gstin_id = Column(Integer, ForeignKey("gstins.id"), nullable=False)
    period = Column(String(6), nullable=False)
    vendor_gstin = Column(String(15), default="")
    vendor_name = Column(String(200), default="")
    invoice_number = Column(String(40), default="")
    invoice_date = Column(Date, nullable=True)
    taxable_value = Column(Float, default=0)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    total = Column(Float, default=0)
    irn = Column(String(64), default="")
    source = Column(String(20), default="2B")


class ReturnPeriod(Base):
    __tablename__ = "return_periods"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    gstin_id = Column(Integer, ForeignKey("gstins.id"), nullable=False)
    period = Column(String(6), nullable=False)
    gstr1_status = Column(String(20), default="OPEN")
    gstr3b_status = Column(String(20), default="OPEN")
    gstr1_json = Column(Text, default="")
    gstr3b_json = Column(Text, default="")
    locked = Column(Boolean, default=False)
    filed_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("gstin_id", "period", name="uq_gstin_period"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(80), nullable=False)
    entity = Column(String(40), default="")
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
