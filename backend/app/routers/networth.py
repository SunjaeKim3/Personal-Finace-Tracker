from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import User
from app.schemas import NetWorthCurrent, NetWorthPoint
from app.services import networth
from app.services.sync import today

router = APIRouter(prefix="/api/v1/networth", tags=["networth"])


@router.get("/history", response_model=list[NetWorthPoint])
def history(
    days: int | None = Query(None, ge=1, description="Omit for all history"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    start = today() - timedelta(days=days) if days else None
    return networth.history(db, user.id, start)


@router.get("/current", response_model=NetWorthCurrent)
def current(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return networth.current(db, user.id)
