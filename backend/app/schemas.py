from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class LoginIn(BaseModel):
    email: str
    password: str


class LineIn(BaseModel):
    item_id: Optional[int] = None
    custom: bool = False
    description: str = ""
    hsn_sac: str = ""
    unit: str = "NOS"
    qty: float = 1
    rate: float = 0
    discount: float = 0


class InvoiceIn(BaseModel):
    gstin_id: int
    party_id: Optional[int] = None
    invoice_type: str = "TAX_INVOICE"
    invoice_date: date
    due_date: Optional[date] = None
    place_of_supply: str = ""
    reverse_charge: bool = False
    gst_preset: str = "REG_18"
    notes: str = ""
    round_off: float = 0
    custom_mode: bool = False
    original_invoice_id: Optional[int] = None
    lines: list[LineIn] = Field(default_factory=list)


class PartyIn(BaseModel):
    kind: str = "CUSTOMER"
    name: str
    trade_name: str = ""
    gstin: str = ""
    pan: str = ""
    email: str = ""
    phone: str = ""
    address1: str = ""
    address2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    place_of_supply: str = ""
    sez: bool = False
    notes: str = ""


class ItemIn(BaseModel):
    kind: str = "SERVICE"
    code: str = ""
    description: str
    hsn_sac: str = ""
    unit: str = "NOS"
    rate: float = 0
    taxability: str = "TAXABLE"
    gst_preset: str = "REG_18"


class CompanyIn(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    pan: Optional[str] = None
    scheme: Optional[str] = None
    aato: Optional[float] = None
    logo_data: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_branch: Optional[str] = None
    terms: Optional[str] = None


class GstinIn(BaseModel):
    gstin: str
    legal_name: str
    trade_name: str = ""
    address1: str = ""
    address2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    email: str = ""
    phone: str = ""
    invoice_prefix: str = "INV"
    is_primary: bool = False


class UserIn(BaseModel):
    name: str
    email: str
    password: str
    role: str = "ACCOUNTANT"


class PurchaseIn(BaseModel):
    gstin_id: int
    vendor_id: Optional[int] = None
    number: str
    invoice_date: date
    vendor_name: str = ""
    vendor_gstin: str = ""
    place_of_supply: str = ""
    reverse_charge: bool = False
    taxable_value: float = 0
    cgst: float = 0
    sgst: float = 0
    igst: float = 0
    total: float = 0
    itc_eligible: bool = True
    notes: str = ""


class Gstr2bIn(BaseModel):
    gstin_id: int
    period: str
    vendor_gstin: str = ""
    vendor_name: str = ""
    invoice_number: str = ""
    invoice_date: Optional[date] = None
    taxable_value: float = 0
    cgst: float = 0
    sgst: float = 0
    igst: float = 0
    total: float = 0
    irn: str = ""
    source: str = "2B"
