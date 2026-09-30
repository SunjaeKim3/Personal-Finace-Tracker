import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.crypto import decrypt, encrypt
from app.db import SessionLocal, get_db
from app.models import Item, User
from app.plaid_client import PlaidError, PlaidService, get_plaid
from app.schemas import ItemOut
from app.services import webhooks
from app.services.sync import sync_item

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/plaid", tags=["plaid"])


def get_user_item(db: Session, user: User, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, "Item not found")
    return item


class LinkTokenIn(BaseModel):
    item_id: int | None = None  # set to open Link in update mode (reconnect)


class LinkTokenOut(BaseModel):
    link_token: str


@router.post("/link-token", response_model=LinkTokenOut)
def link_token(
    body: LinkTokenIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    plaid: PlaidService = Depends(get_plaid),
):
    access_token = decrypt(get_user_item(db, user, body.item_id).access_token_enc) if body.item_id else None
    try:
        return {"link_token": plaid.create_link_token(user.id, access_token)}
    except PlaidError as e:
        raise HTTPException(502, f"Plaid: {e.code} {e.message}")


class ExchangeIn(BaseModel):
    public_token: str
    institution_id: str | None = None
    institution_name: str | None = None


@router.post("/exchange", response_model=ItemOut)
def exchange(
    body: ExchangeIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    plaid: PlaidService = Depends(get_plaid),
):
    try:
        access_token, plaid_item_id = plaid.exchange_public_token(body.public_token)
    except PlaidError as e:
        raise HTTPException(502, f"Plaid: {e.code} {e.message}")
    item = db.scalar(select(Item).where(Item.plaid_item_id == plaid_item_id))
    if item is None:
        item = Item(user_id=user.id, plaid_item_id=plaid_item_id)
        db.add(item)
    item.access_token_enc = encrypt(access_token)
    item.institution_id = body.institution_id
    item.institution_name = body.institution_name
    db.commit()
    sync_item(db, plaid, item)
    db.refresh(item)
    return item


def _handle_webhook_in_background(payload: dict, plaid: PlaidService) -> None:
    with SessionLocal() as db:
        result = webhooks.handle(db, plaid, payload)
        log.info("Webhook %s/%s: %s", payload.get("webhook_type"), payload.get("webhook_code"), result)


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, background: BackgroundTasks, plaid: PlaidService = Depends(get_plaid)):
    body = await request.body()
    try:
        await run_in_threadpool(webhooks.verify, plaid, body, request.headers.get("plaid-verification"))
    except webhooks.WebhookVerificationError as e:
        log.warning("Rejected webhook: %s", e)
        raise HTTPException(401, "invalid webhook")
    # Respond fast; Plaid retries slow webhooks.
    background.add_task(_handle_webhook_in_background, json.loads(body), plaid)
    return {"ok": True}
