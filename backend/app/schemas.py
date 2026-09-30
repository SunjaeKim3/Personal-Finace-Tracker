"""API response/request models. Money is sent as JSON numbers (floats) for easy client use."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORM):
    id: int
    email: str
    name: str | None


class AccountOut(ORM):
    id: int
    name: str
    official_name: str | None
    mask: str | None
    type: str
    subtype: str | None
    current_balance: float | None
    available_balance: float | None
    credit_limit: float | None
    currency: str | None
    hidden: bool


class ItemOut(ORM):
    id: int
    institution_name: str | None
    status: str
    error_code: str | None
    last_synced_at: datetime | None
    accounts: list[AccountOut]


class AccountPatch(BaseModel):
    hidden: bool


class SyncResultOut(BaseModel):
    item_id: int
    added: int
    modified: int
    removed: int
    error: str | None
    warnings: list[str]


class TransactionOut(ORM):
    id: int
    account_id: int
    date: date
    name: str
    merchant_name: str | None
    amount: float
    pending: bool
    category: str
    counted: bool
    pfc_primary: str | None
    pfc_detailed: str | None
    category_override: str | None
    logo_url: str | None


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


class TransactionPatch(BaseModel):
    category_override: str | None


class CategoryTotal(BaseModel):
    category: str
    amount: float
    count: int


class SummaryOut(BaseModel):
    month: str
    income: float
    spending: float
    net: float
    savings_rate: float | None
    categories: list[CategoryTotal]


class CashflowPoint(BaseModel):
    month: str
    income: float
    spending: float
    net: float


class BudgetIn(BaseModel):
    monthly_limit: float


class BudgetOut(BaseModel):
    id: int
    category: str
    monthly_limit: float
    spent: float
    remaining: float


class RecurringOut(ORM):
    id: int
    account_id: int
    direction: str
    description: str | None
    merchant_name: str | None
    frequency: str | None
    average_amount: float | None
    last_amount: float | None
    last_date: date | None
    predicted_next_date: date | None
    is_active: bool
    status: str | None
    category: str | None
    monthly_amount: float


class RecurringSummary(BaseModel):
    streams: list[RecurringOut]
    monthly_outflow: float
    monthly_inflow: float


class NetWorthPoint(BaseModel):
    date: date
    assets: float
    liabilities: float
    net_worth: float


class NetWorthAccount(BaseModel):
    account_id: int
    name: str
    mask: str | None
    type: str
    subtype: str | None
    institution: str | None
    balance: float
    signed_balance: float


class NetWorthCurrent(BaseModel):
    assets: float
    liabilities: float
    net_worth: float
    accounts: list[NetWorthAccount]
