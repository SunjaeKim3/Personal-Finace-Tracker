import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

Money = Numeric(14, 2)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["Item"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiToken(Base):
    """Bearer tokens for non-browser clients (future iOS app). Only the SHA-256 hash is stored."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Item(Base):
    """One Plaid Item = one login at one institution."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plaid_item_id: Mapped[str] = mapped_column(String(100), unique=True)
    access_token_enc: Mapped[str] = mapped_column(Text)
    institution_id: Mapped[str | None] = mapped_column(String(50))
    institution_name: Mapped[str | None] = mapped_column(String(200))
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | login_required | error
    error_code: Mapped[str | None] = mapped_column(String(100))
    last_synced_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="items")
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="Account.name"
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    plaid_account_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    official_name: Mapped[str | None] = mapped_column(String(200))
    mask: Mapped[str | None] = mapped_column(String(10))
    type: Mapped[str] = mapped_column(String(30))  # depository | credit | loan | investment | other
    subtype: Mapped[str | None] = mapped_column(String(50))
    current_balance: Mapped[Decimal | None] = mapped_column(Money)
    available_balance: Mapped[Decimal | None] = mapped_column(Money)
    credit_limit: Mapped[Decimal | None] = mapped_column(Money)
    currency: Mapped[str | None] = mapped_column(String(3))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    item: Mapped[Item] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["BalanceSnapshot"]] = relationship(cascade="all, delete-orphan")
    recurring_streams: Mapped[list["RecurringStream"]] = relationship(cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    plaid_transaction_id: Mapped[str] = mapped_column(String(100), unique=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    authorized_date: Mapped[dt.date | None] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(500))
    merchant_name: Mapped[str | None] = mapped_column(String(200))
    # Plaid convention: positive = money out of the account, negative = money in.
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str | None] = mapped_column(String(3))
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    pfc_primary: Mapped[str | None] = mapped_column(String(100))
    pfc_detailed: Mapped[str | None] = mapped_column(String(100))
    category_override: Mapped[str | None] = mapped_column(String(100))
    logo_url: Mapped[str | None] = mapped_column(Text)

    account: Mapped[Account] = relationship(back_populates="transactions")

    @property
    def category(self) -> str:
        return self.category_override or self.pfc_primary or "OTHER"

    @property
    def counted(self) -> bool:
        """False for transfers and card payments, which are left out of spending and income."""
        from app.services.analytics import classify

        return classify(self.amount, self.pfc_primary, self.pfc_detailed, self.category_override)[0] is not None


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"
    __table_args__ = (UniqueConstraint("account_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    current_balance: Mapped[Decimal] = mapped_column(Money)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(100))
    monthly_limit: Mapped[Decimal] = mapped_column(Money)


class RecurringStream(Base):
    __tablename__ = "recurring_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    plaid_stream_id: Mapped[str] = mapped_column(String(100), unique=True)
    direction: Mapped[str] = mapped_column(String(10))  # inflow | outflow
    description: Mapped[str | None] = mapped_column(String(500))
    merchant_name: Mapped[str | None] = mapped_column(String(200))
    frequency: Mapped[str | None] = mapped_column(String(20))
    average_amount: Mapped[Decimal | None] = mapped_column(Money)  # always positive; see direction
    last_amount: Mapped[Decimal | None] = mapped_column(Money)
    first_date: Mapped[dt.date | None] = mapped_column(Date)
    last_date: Mapped[dt.date | None] = mapped_column(Date)
    predicted_next_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str | None] = mapped_column(String(30))
    category: Mapped[str | None] = mapped_column(String(100))
