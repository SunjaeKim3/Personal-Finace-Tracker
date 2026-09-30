"""Spending/income math.

Plaid sign convention: amount > 0 is money leaving an account, amount < 0 is money arriving.

Every transaction lands in one bucket based on its effective category
(user override, else Plaid's personal_finance_category.primary):
  - excluded: transfers between your own accounts and credit card payments. Counting them would
    double-count (the card purchases are already spending; moving money isn't income).
  - income:   INCOME, plus uncategorized inflows. value = -amount (paychecks are positive income).
  - spending: everything else. value = amount, so refunds (negative) reduce that category.
"""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Item, Transaction

TRANSFER_CATEGORIES = {"TRANSFER_IN", "TRANSFER_OUT"}
EXCLUDED_DETAILED = {"LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"}
INCOME = "INCOME"
UNCATEGORIZED = "OTHER"


def classify(amount: Decimal, pfc_primary: str | None, pfc_detailed: str | None, override: str | None):
    """Return (bucket, category) where bucket is 'income', 'spending', or None (excluded)."""
    category = override or pfc_primary or UNCATEGORIZED
    if category in TRANSFER_CATEGORIES:
        return None, category
    if override is None and pfc_detailed in EXCLUDED_DETAILED:
        return None, category
    if category == INCOME or (category == UNCATEGORIZED and amount < 0):
        return "income", category
    return "spending", category


@dataclass
class Totals:
    income: Decimal
    spending: Decimal
    by_category: dict[str, Decimal]
    counts: dict[str, int]

    @property
    def net(self) -> Decimal:
        return self.income - self.spending


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _rows(db: Session, user_id: int, start: date, end: date):
    q = (
        select(
            Transaction.date,
            Transaction.amount,
            Transaction.pfc_primary,
            Transaction.pfc_detailed,
            Transaction.category_override,
        )
        .join(Account, Transaction.account_id == Account.id)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user_id, Account.hidden.is_(False))
        .where(Transaction.date >= start, Transaction.date <= end)
    )
    return db.execute(q).all()


def totals(db: Session, user_id: int, start: date, end: date) -> Totals:
    income = Decimal(0)
    spending = Decimal(0)
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    for _, amount, primary, detailed, override in _rows(db, user_id, start, end):
        amount = Decimal(amount)
        bucket, category = classify(amount, primary, detailed, override)
        if bucket == "income":
            income += -amount
        elif bucket == "spending":
            spending += amount
            by_category[category] += amount
            counts[category] += 1
    return Totals(income, spending, dict(by_category), dict(counts))


def monthly_cashflow(db: Session, user_id: int, end_year: int, end_month: int, months: int) -> list[dict]:
    start_y, start_m = shift_month(end_year, end_month, -(months - 1))
    start, _ = month_bounds(start_y, start_m)
    _, end = month_bounds(end_year, end_month)

    buckets = {}
    for i in range(months):
        y, m = shift_month(start_y, start_m, i)
        buckets[(y, m)] = {"month": f"{y:04d}-{m:02d}", "income": Decimal(0), "spending": Decimal(0)}

    for d, amount, primary, detailed, override in _rows(db, user_id, start, end):
        amount = Decimal(amount)
        bucket, _ = classify(amount, primary, detailed, override)
        b = buckets[(d.year, d.month)]
        if bucket == "income":
            b["income"] += -amount
        elif bucket == "spending":
            b["spending"] += amount

    out = list(buckets.values())
    for b in out:
        b["net"] = b["income"] - b["spending"]
    return out
