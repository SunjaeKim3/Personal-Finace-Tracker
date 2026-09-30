from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import User
from app.schemas import CashflowPoint, CategoryTotal, SummaryOut
from app.services import analytics
from app.services.sync import today

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


def parse_month(month: str | None) -> tuple[int, int]:
    if not month:
        t = today()
        return t.year, t.month
    try:
        y, m = month.split("-")
        return int(y), int(m)
    except ValueError:
        raise HTTPException(422, "month must be YYYY-MM")


def category_list(t: analytics.Totals) -> list[CategoryTotal]:
    rows = [CategoryTotal(category=c, amount=float(a), count=t.counts[c]) for c, a in t.by_category.items()]
    return sorted(rows, key=lambda r: r.amount, reverse=True)


@router.get("/summary", response_model=SummaryOut)
def summary(month: str | None = None, user: User = Depends(require_user), db: Session = Depends(get_db)):
    y, m = parse_month(month)
    t = analytics.totals(db, user.id, *analytics.month_bounds(y, m))
    return SummaryOut(
        month=f"{y:04d}-{m:02d}",
        income=float(t.income),
        spending=float(t.spending),
        net=float(t.net),
        savings_rate=float(t.net / t.income) if t.income > 0 else None,
        categories=category_list(t),
    )


@router.get("/cashflow", response_model=list[CashflowPoint])
def cashflow(
    months: int = Query(12, ge=1, le=36),
    end_month: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    y, m = parse_month(end_month)
    return analytics.monthly_cashflow(db, user.id, y, m, months)


@router.get("/categories", response_model=list[CategoryTotal])
def categories(start: date, end: date, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return category_list(analytics.totals(db, user.id, start, end))
