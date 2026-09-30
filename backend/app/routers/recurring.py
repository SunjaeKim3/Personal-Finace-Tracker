from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import Account, Item, RecurringStream, User
from app.schemas import RecurringOut, RecurringSummary

router = APIRouter(prefix="/api/v1/recurring", tags=["recurring"])

# Multiplier to convert one occurrence into a monthly-equivalent amount.
PER_MONTH = {"WEEKLY": 52 / 12, "BIWEEKLY": 26 / 12, "SEMI_MONTHLY": 2, "MONTHLY": 1, "ANNUALLY": 1 / 12}


def monthly_amount(s: RecurringStream) -> float:
    return float(s.average_amount or 0) * PER_MONTH.get(s.frequency or "", 1)


def _out(s: RecurringStream) -> RecurringOut:
    fields = {k: getattr(s, k) for k in RecurringOut.model_fields if k != "monthly_amount"}
    return RecurringOut(**fields, monthly_amount=monthly_amount(s))


@router.get("", response_model=RecurringSummary)
def list_recurring(
    include_inactive: bool = False, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    q = (
        select(RecurringStream)
        .join(Account, RecurringStream.account_id == Account.id)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user.id, Account.hidden.is_(False))
        .order_by(RecurringStream.predicted_next_date)
    )
    if not include_inactive:
        q = q.where(RecurringStream.is_active.is_(True))
    out = [_out(s) for s in db.scalars(q).all()]
    return RecurringSummary(
        streams=out,
        monthly_outflow=sum(r.monthly_amount for r in out if r.direction == "outflow"),
        monthly_inflow=sum(r.monthly_amount for r in out if r.direction == "inflow"),
    )
