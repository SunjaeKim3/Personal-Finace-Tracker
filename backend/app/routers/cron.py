import hmac
from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.plaid_client import PlaidService, get_plaid
from app.schemas import SyncResultOut
from app.services.sync import sync_all

router = APIRouter(prefix="/api/v1/cron", tags=["cron"])


@router.post("/sync", response_model=list[SyncResultOut])
def cron_sync(
    authorization: str = Header(""),
    db: Session = Depends(get_db),
    plaid: PlaidService = Depends(get_plaid),
):
    """Daily job (GitHub Actions): sync every Item, which also records today's balance snapshot."""
    secret = get_settings().cron_secret
    if not secret or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(401, "invalid cron secret")
    return [asdict(r) for r in sync_all(db, plaid)]
