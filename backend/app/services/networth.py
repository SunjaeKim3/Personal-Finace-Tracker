from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, BalanceSnapshot, Item

# Plaid reports credit/loan balances as positive amounts owed.
LIABILITY_TYPES = {"credit", "loan"}


def signed_balance(account_type: str, balance: Decimal) -> Decimal:
    return -balance if account_type in LIABILITY_TYPES else balance


def history(db: Session, user_id: int, start: date | None = None) -> list[dict]:
    """Net worth per snapshot date. Accounts without a snapshot on a given date carry their
    last known balance forward, so a missed sync doesn't look like a drop."""
    q = (
        select(BalanceSnapshot.date, BalanceSnapshot.account_id, BalanceSnapshot.current_balance, Account.type)
        .join(Account, BalanceSnapshot.account_id == Account.id)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user_id, Account.hidden.is_(False))
        .order_by(BalanceSnapshot.date)
    )
    latest: dict[int, tuple[str, Decimal]] = {}
    points: dict[date, dict] = {}
    for d, account_id, balance, account_type in db.execute(q):
        latest[account_id] = (account_type, Decimal(balance))
        assets = sum((b for t, b in latest.values() if t not in LIABILITY_TYPES), Decimal(0))
        liabilities = sum((b for t, b in latest.values() if t in LIABILITY_TYPES), Decimal(0))
        points[d] = {"date": d, "assets": assets, "liabilities": liabilities, "net_worth": assets - liabilities}
    out = list(points.values())
    return [p for p in out if start is None or p["date"] >= start]


def current(db: Session, user_id: int) -> dict:
    accounts = db.scalars(
        select(Account)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user_id, Account.hidden.is_(False))
    ).all()
    assets = Decimal(0)
    liabilities = Decimal(0)
    rows = []
    for a in accounts:
        bal = a.current_balance or Decimal(0)
        if a.type in LIABILITY_TYPES:
            liabilities += bal
        else:
            assets += bal
        rows.append(
            {
                "account_id": a.id,
                "name": a.name,
                "mask": a.mask,
                "type": a.type,
                "subtype": a.subtype,
                "institution": a.item.institution_name,
                "balance": bal,
                "signed_balance": signed_balance(a.type, bal),
            }
        )
    rows.sort(key=lambda r: r["signed_balance"], reverse=True)
    return {"assets": assets, "liabilities": liabilities, "net_worth": assets - liabilities, "accounts": rows}
