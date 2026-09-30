import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import decrypt
from app.models import Account, BalanceSnapshot, Item, RecurringStream, Transaction
from app.plaid_client import PlaidError, PlaidService

log = logging.getLogger(__name__)

# Errors that mean the user has to re-authenticate through Link update mode.
LOGIN_REQUIRED_CODES = {"ITEM_LOGIN_REQUIRED", "PENDING_EXPIRATION", "PENDING_DISCONNECT"}
MUTATION_DURING_PAGINATION = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"


@dataclass
class SyncResult:
    item_id: int
    added: int = 0
    modified: int = 0
    removed: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _to_date(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _money(v) -> Decimal | None:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))


def fetch_transaction_updates(plaid: PlaidService, access_token: str, cursor: str | None):
    """Page through /transactions/sync. Nothing is written until every page is fetched,
    and a mutation during pagination restarts from the original cursor."""
    for _ in range(5):
        added, modified, removed = [], [], []
        next_cursor = cursor
        try:
            while True:
                page = plaid.transactions_sync(access_token, next_cursor)
                added += page["added"]
                modified += page["modified"]
                removed += page["removed"]
                next_cursor = page["next_cursor"]
                if not page["has_more"]:
                    return added, modified, removed, next_cursor
        except PlaidError as e:
            if e.code != MUTATION_DURING_PAGINATION:
                raise
            log.info("Sync mutated during pagination; restarting")
    raise PlaidError(MUTATION_DURING_PAGINATION, "gave up after repeated restarts")


def apply_accounts(db: Session, item: Item, accounts: list[dict], snapshot_date: date) -> None:
    existing = {a.plaid_account_id: a for a in item.accounts}
    for a in accounts:
        row = existing.get(a["account_id"])
        if row is None:
            row = Account(plaid_account_id=a["account_id"])
            item.accounts.append(row)
        bal = a.get("balances") or {}
        row.name = a.get("name") or "Account"
        row.official_name = a.get("official_name")
        row.mask = a.get("mask")
        row.type = str(a.get("type") or "other")
        row.subtype = str(a["subtype"]) if a.get("subtype") else None
        row.current_balance = _money(bal.get("current"))
        row.available_balance = _money(bal.get("available"))
        row.credit_limit = _money(bal.get("limit"))
        row.currency = bal.get("iso_currency_code")
    db.flush()

    for row in item.accounts:
        if row.current_balance is None:
            continue
        snap = db.scalar(
            select(BalanceSnapshot).where(
                BalanceSnapshot.account_id == row.id, BalanceSnapshot.date == snapshot_date
            )
        )
        if snap is None:
            db.add(BalanceSnapshot(account_id=row.id, date=snapshot_date, current_balance=row.current_balance))
        else:
            snap.current_balance = row.current_balance


def apply_transactions(db: Session, item: Item, added: list[dict], modified: list[dict], removed: list[dict]) -> None:
    account_ids = {a.plaid_account_id: a.id for a in item.accounts}
    upserts = {t["transaction_id"]: t for t in added + modified}  # later entries win

    existing: dict[str, Transaction] = {}
    ids = list(upserts)
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        for row in db.scalars(select(Transaction).where(Transaction.plaid_transaction_id.in_(chunk))):
            existing[row.plaid_transaction_id] = row

    for tid, t in upserts.items():
        account_id = account_ids.get(t["account_id"])
        if account_id is None:
            log.warning("Transaction %s references unknown account %s", tid, t["account_id"])
            continue
        row = existing.get(tid)
        if row is None:
            row = Transaction(plaid_transaction_id=tid)
            db.add(row)
        pfc = t.get("personal_finance_category") or {}
        row.account_id = account_id
        row.date = _to_date(t["date"])
        row.authorized_date = _to_date(t.get("authorized_date"))
        row.name = (t.get("name") or "")[:500]
        row.merchant_name = t.get("merchant_name")
        row.amount = _money(t["amount"])
        row.currency = t.get("iso_currency_code")
        row.pending = bool(t.get("pending"))
        row.pfc_primary = pfc.get("primary")
        row.pfc_detailed = pfc.get("detailed")
        row.logo_url = t.get("logo_url")
        # category_override is user-owned; never overwritten by sync.

    removed_ids = [r["transaction_id"] for r in removed]
    for i in range(0, len(removed_ids), 500):
        db.execute(
            delete(Transaction).where(Transaction.plaid_transaction_id.in_(removed_ids[i : i + 500]))
        )


def apply_recurring(db: Session, item: Item, data: dict) -> None:
    account_ids = {a.plaid_account_id: a.id for a in item.accounts}
    db.execute(delete(RecurringStream).where(RecurringStream.account_id.in_(list(account_ids.values()))))
    for direction, key in (("inflow", "inflow_streams"), ("outflow", "outflow_streams")):
        for s in data.get(key) or []:
            account_id = account_ids.get(s["account_id"])
            if account_id is None:
                continue
            avg = (s.get("average_amount") or {}).get("amount")
            last = (s.get("last_amount") or {}).get("amount")
            pfc = s.get("personal_finance_category") or {}
            db.add(
                RecurringStream(
                    account_id=account_id,
                    plaid_stream_id=s["stream_id"],
                    direction=direction,
                    description=s.get("description"),
                    merchant_name=s.get("merchant_name"),
                    frequency=str(s.get("frequency") or "UNKNOWN"),
                    average_amount=_money(abs(avg)) if avg is not None else None,
                    last_amount=_money(abs(last)) if last is not None else None,
                    first_date=_to_date(s.get("first_date")),
                    last_date=_to_date(s.get("last_date")),
                    predicted_next_date=_to_date(s.get("predicted_next_date")),
                    is_active=bool(s.get("is_active", True)),
                    status=str(s.get("status")) if s.get("status") else None,
                    category=pfc.get("primary"),
                )
            )


def sync_item(db: Session, plaid: PlaidService, item: Item) -> SyncResult:
    result = SyncResult(item_id=item.id)
    access_token = decrypt(item.access_token_enc)
    try:
        added, modified, removed, cursor = fetch_transaction_updates(plaid, access_token, item.sync_cursor)
        apply_accounts(db, item, plaid.accounts_get(access_token), today())
        apply_transactions(db, item, added, modified, removed)
        item.sync_cursor = cursor
        result.added, result.modified, result.removed = len(added), len(modified), len(removed)

        try:
            apply_recurring(db, item, plaid.recurring_get(access_token))
        except PlaidError as e:
            # Recurring data can lag the initial pull (PRODUCT_NOT_READY); don't fail the sync.
            result.warnings.append(f"recurring: {e.code}")

        item.status = "ok"
        item.error_code = None
        item.last_synced_at = datetime.now(timezone.utc)
        db.commit()
    except PlaidError as e:
        db.rollback()
        item.status = "login_required" if e.code in LOGIN_REQUIRED_CODES else "error"
        item.error_code = e.code
        db.commit()
        result.error = e.code
        log.warning("Sync failed for item %s: %s", item.id, e)
    return result


def sync_all(db: Session, plaid: PlaidService, user_id: int | None = None) -> list[SyncResult]:
    q = select(Item)
    if user_id is not None:
        q = q.where(Item.user_id == user_id)
    return [sync_item(db, plaid, item) for item in db.scalars(q).all()]
