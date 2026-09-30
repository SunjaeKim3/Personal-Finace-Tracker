from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import Budget, User
from app.routers.insights import parse_month
from app.schemas import BudgetIn, BudgetOut
from app.services import analytics

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])


def _out(b: Budget, spent: Decimal) -> BudgetOut:
    return BudgetOut(
        id=b.id,
        category=b.category,
        monthly_limit=float(b.monthly_limit),
        spent=float(spent),
        remaining=float(b.monthly_limit - spent),
    )


@router.get("", response_model=list[BudgetOut])
def list_budgets(month: str | None = None, user: User = Depends(require_user), db: Session = Depends(get_db)):
    y, m = parse_month(month)
    spent = analytics.totals(db, user.id, *analytics.month_bounds(y, m)).by_category
    budgets = db.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.category)).all()
    return [_out(b, spent.get(b.category, Decimal(0))) for b in budgets]


@router.put("/{category}", response_model=BudgetOut)
def upsert_budget(category: str, body: BudgetIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if body.monthly_limit <= 0:
        raise HTTPException(422, "monthly_limit must be positive")
    b = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category == category))
    if b is None:
        b = Budget(user_id=user.id, category=category)
        db.add(b)
    b.monthly_limit = Decimal(str(body.monthly_limit))
    db.commit()
    y, m = parse_month(None)
    spent = analytics.totals(db, user.id, *analytics.month_bounds(y, m)).by_category
    return _out(b, spent.get(category, Decimal(0)))


@router.delete("/{budget_id}")
def delete_budget(budget_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    b = db.get(Budget, budget_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "Budget not found")
    db.delete(b)
    db.commit()
    return {"ok": True}
