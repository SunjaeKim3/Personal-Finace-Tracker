from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.crypto import decrypt
from app.db import get_db
from app.models import Account, Item, User
from app.plaid_client import PlaidError, PlaidService, get_plaid
from app.routers.plaid import get_user_item
from app.schemas import AccountOut, AccountPatch, ItemOut, SyncResultOut, UserOut
from app.services.sync import sync_all, sync_item

router = APIRouter(prefix="/api/v1", tags=["accounts"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)):
    return user


@router.get("/items", response_model=list[ItemOut])
def list_items(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return db.scalars(select(Item).where(Item.user_id == user.id).order_by(Item.institution_name)).all()


@router.post("/items/{item_id}/sync", response_model=SyncResultOut)
def sync_one(
    item_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    plaid: PlaidService = Depends(get_plaid),
):
    return asdict(sync_item(db, plaid, get_user_item(db, user, item_id)))


@router.post("/sync", response_model=list[SyncResultOut])
def sync_everything(
    user: User = Depends(require_user), db: Session = Depends(get_db), plaid: PlaidService = Depends(get_plaid)
):
    return [asdict(r) for r in sync_all(db, plaid, user.id)]


@router.delete("/items/{item_id}")
def remove_item(
    item_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    plaid: PlaidService = Depends(get_plaid),
):
    item = get_user_item(db, user, item_id)
    try:
        plaid.item_remove(decrypt(item.access_token_enc))
    except PlaidError as e:
        if e.code not in {"ITEM_NOT_FOUND", "INVALID_ACCESS_TOKEN"}:
            raise HTTPException(502, f"Plaid: {e.code} {e.message}")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, body: AccountPatch, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    account = db.get(Account, account_id)
    if account is None or account.item.user_id != user.id:
        raise HTTPException(404, "Account not found")
    account.hidden = body.hidden
    db.commit()
    return account
