import os
import tempfile

from cryptography.fernet import Fernet

# Configure before any app import (settings and engine are created at import time).
_tmp = tempfile.mkdtemp()
os.environ.update(
    ENV="development",
    APP_URL="http://localhost:5173",
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    SESSION_SECRET="test-session-secret",
    ENCRYPTION_KEY=Fernet.generate_key().decode(),
    ALLOWED_EMAILS="me@example.com",
    CRON_SECRET="cron-secret",
    DEV_LOGIN_EMAIL="me@example.com",
    PLAID_REDIRECT_URI="",
    PLAID_WEBHOOK_URL="",
    GOOGLE_CLIENT_ID="",
    GITHUB_CLIENT_ID="",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.plaid_client import get_plaid  # noqa: E402


class FakePlaid:
    """In-memory stand-in for PlaidService. Queue sync pages (or exceptions) per access token."""

    def __init__(self):
        self.sync_pages: dict[str, list] = {}
        self.accounts: dict[str, list[dict]] = {}
        self.recurring: dict[str, dict | Exception] = {}
        self.keys: dict[str, dict] = {}
        self.removed: list[str] = []
        self.link_calls: list[tuple] = []
        self.sync_calls: list[tuple] = []

    def create_link_token(self, user_id, access_token=None):
        self.link_calls.append((user_id, access_token))
        return "link-sandbox-token"

    def exchange_public_token(self, public_token):
        return f"access-{public_token}", f"item-{public_token}"

    def transactions_sync(self, access_token, cursor):
        self.sync_calls.append((access_token, cursor))
        queue = self.sync_pages.get(access_token) or []
        if not queue:
            return {"added": [], "modified": [], "removed": [], "next_cursor": cursor or "c0", "has_more": False}
        step = queue.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def accounts_get(self, access_token):
        return self.accounts.get(access_token, [])

    def recurring_get(self, access_token):
        r = self.recurring.get(access_token, {"inflow_streams": [], "outflow_streams": []})
        if isinstance(r, Exception):
            raise r
        return r

    def item_remove(self, access_token):
        self.removed.append(access_token)

    def webhook_verification_key(self, key_id):
        return self.keys[key_id]


def page(added=(), modified=(), removed=(), cursor="c1", has_more=False) -> dict:
    return {
        "added": list(added),
        "modified": list(modified),
        "removed": [{"transaction_id": r} for r in removed],
        "next_cursor": cursor,
        "has_more": has_more,
    }


def txn(tid, amount, date="2026-09-10", primary="FOOD_AND_DRINK", detailed=None, account="acc-checking", name=None):
    return {
        "transaction_id": tid,
        "account_id": account,
        "amount": amount,
        "date": date,
        "name": name or tid,
        "merchant_name": None,
        "iso_currency_code": "USD",
        "pending": False,
        "personal_finance_category": {"primary": primary, "detailed": detailed or f"{primary}_OTHER"},
    }


def account(aid="acc-checking", type_="depository", current=1000.0, name="Checking"):
    return {
        "account_id": aid,
        "name": name,
        "mask": "0000",
        "type": type_,
        "subtype": "checking" if type_ == "depository" else "credit card",
        "balances": {"current": current, "available": current, "limit": None, "iso_currency_code": "USD"},
    }


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def fake_plaid():
    fake = FakePlaid()
    app.dependency_overrides[get_plaid] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client(fake_plaid):
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    r = client.get("/auth/dev-login", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "http://localhost:5173/"
    return client
