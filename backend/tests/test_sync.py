from decimal import Decimal

from sqlalchemy import func, select

from app.crypto import encrypt
from app.models import BalanceSnapshot, Item, RecurringStream, Transaction, User
from app.plaid_client import PlaidError
from app.services.sync import MUTATION_DURING_PAGINATION, sync_item
from tests.conftest import account, page, txn

TOKEN = "access-test"


def _item(db) -> Item:
    item = Item(user=User(email="me@example.com"), plaid_item_id="item-1", access_token_enc=encrypt(TOKEN))
    db.add(item)
    db.commit()
    return item


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_paginates_and_stores_final_cursor(db, fake_plaid):
    item = _item(db)
    fake_plaid.accounts[TOKEN] = [account()]
    fake_plaid.sync_pages[TOKEN] = [
        page(added=[txn("t1", 10), txn("t2", 20)], cursor="c1", has_more=True),
        page(added=[txn("t3", 30)], cursor="c2"),
    ]
    result = sync_item(db, fake_plaid, item)

    assert result.error is None and result.added == 3
    assert item.sync_cursor == "c2" and item.status == "ok"
    assert [c for _, c in fake_plaid.sync_calls] == [None, "c1"]
    assert _count(db, Transaction) == 3


def test_restarts_from_original_cursor_on_mutation(db, fake_plaid):
    item = _item(db)
    item.sync_cursor = "c0"
    db.commit()
    fake_plaid.accounts[TOKEN] = [account()]
    fake_plaid.sync_pages[TOKEN] = [
        page(added=[txn("t1", 10)], cursor="c1", has_more=True),
        PlaidError(MUTATION_DURING_PAGINATION),
        page(added=[txn("t1", 10)], cursor="c1", has_more=True),
        page(added=[txn("t2", 20)], cursor="c2"),
    ]
    result = sync_item(db, fake_plaid, item)

    assert result.error is None
    assert [c for _, c in fake_plaid.sync_calls] == ["c0", "c1", "c0", "c1"]
    assert _count(db, Transaction) == 2
    assert item.sync_cursor == "c2"


def test_modified_keeps_user_override_and_removed_deletes(db, fake_plaid):
    item = _item(db)
    fake_plaid.accounts[TOKEN] = [account()]
    fake_plaid.sync_pages[TOKEN] = [page(added=[txn("t1", 10), txn("t2", 20)], cursor="c1")]
    sync_item(db, fake_plaid, item)

    t1 = db.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "t1"))
    t1.category_override = "ENTERTAINMENT"
    db.commit()

    fake_plaid.sync_pages[TOKEN] = [page(modified=[txn("t1", 12.34)], removed=["t2"], cursor="c2")]
    sync_item(db, fake_plaid, item)

    db.refresh(t1)
    assert t1.amount == Decimal("12.34")
    assert t1.category_override == "ENTERTAINMENT"
    assert _count(db, Transaction) == 1


def test_login_required_marks_item_and_keeps_cursor(db, fake_plaid):
    item = _item(db)
    item.sync_cursor = "c5"
    db.commit()
    fake_plaid.sync_pages[TOKEN] = [PlaidError("ITEM_LOGIN_REQUIRED", "reauth")]
    result = sync_item(db, fake_plaid, item)

    db.refresh(item)
    assert result.error == "ITEM_LOGIN_REQUIRED"
    assert item.status == "login_required" and item.error_code == "ITEM_LOGIN_REQUIRED"
    assert item.sync_cursor == "c5"


def test_successful_sync_clears_previous_error(db, fake_plaid):
    item = _item(db)
    item.status, item.error_code = "login_required", "ITEM_LOGIN_REQUIRED"
    db.commit()
    fake_plaid.accounts[TOKEN] = [account()]
    sync_item(db, fake_plaid, item)
    assert item.status == "ok" and item.error_code is None


def test_balance_snapshot_is_one_per_account_per_day(db, fake_plaid):
    item = _item(db)
    fake_plaid.accounts[TOKEN] = [account(current=100), account("acc-card", "credit", 50, "Card")]
    sync_item(db, fake_plaid, item)
    fake_plaid.accounts[TOKEN] = [account(current=150), account("acc-card", "credit", 75, "Card")]
    sync_item(db, fake_plaid, item)

    snaps = db.scalars(select(BalanceSnapshot).order_by(BalanceSnapshot.current_balance)).all()
    assert [s.current_balance for s in snaps] == [Decimal(75), Decimal(150)]


def test_recurring_streams_replaced_and_failure_is_only_a_warning(db, fake_plaid):
    item = _item(db)
    fake_plaid.accounts[TOKEN] = [account()]
    stream = {
        "stream_id": "s1",
        "account_id": "acc-checking",
        "description": "NETFLIX",
        "merchant_name": "Netflix",
        "frequency": "MONTHLY",
        "average_amount": {"amount": 15.49},
        "last_amount": {"amount": 15.49},
        "last_date": "2026-09-05",
        "predicted_next_date": "2026-10-05",
        "is_active": True,
        "status": "MATURE",
        "personal_finance_category": {"primary": "ENTERTAINMENT"},
    }
    fake_plaid.recurring[TOKEN] = {"inflow_streams": [], "outflow_streams": [stream]}
    sync_item(db, fake_plaid, item)
    sync_item(db, fake_plaid, item)  # replacing must not violate the unique stream id
    assert _count(db, RecurringStream) == 1

    fake_plaid.recurring[TOKEN] = PlaidError("PRODUCT_NOT_READY")
    result = sync_item(db, fake_plaid, item)
    assert result.error is None and result.warnings == ["recurring: PRODUCT_NOT_READY"]
    assert item.status == "ok"
