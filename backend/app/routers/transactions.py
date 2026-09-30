from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import Account, Item, Transaction, User
from app.schemas import TransactionOut, TransactionPage, TransactionPatch

router = APIRouter(prefix="/api/v1", tags=["transactions"])

# Plaid personal_finance_category primaries, offered as recategorization targets.
CATEGORIES = [
    "INCOME",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "LOAN_PAYMENTS",
    "BANK_FEES",
    "ENTERTAINMENT",
    "FOOD_AND_DRINK",
    "GENERAL_MERCHANDISE",
    "HOME_IMPROVEMENT",
    "MEDICAL",
    "PERSONAL_CARE",
    "GENERAL_SERVICES",
    "GOVERNMENT_AND_NON_PROFIT",
    "TRANSPORTATION",
    "TRAVEL",
    "RENT_AND_UTILITIES",
    "OTHER",
]

effective_category = func.coalesce(Transaction.category_override, Transaction.pfc_primary, "OTHER")


@router.get("/categories", response_model=list[str])
def categories(user: User = Depends(require_user), db: Session = Depends(get_db)):
    used = db.scalars(
        select(effective_category)
        .join(Account, Transaction.account_id == Account.id)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user.id)
        .distinct()
    ).all()
    return sorted(set(CATEGORIES) | set(used))


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    search: str | None = None,
    account_id: int | None = None,
    category: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    q = (
        select(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user.id)
    )
    if search:
        like = f"%{search}%"
        q = q.where(or_(Transaction.name.ilike(like), Transaction.merchant_name.ilike(like)))
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if category:
        q = q.where(effective_category == category)
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).offset(offset)).all()
    return {"items": rows, "total": total}


@router.patch("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: int, body: TransactionPatch, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    t = db.get(Transaction, transaction_id)
    if t is None or t.account.item.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    t.category_override = body.category_override or None
    db.commit()
    return t
