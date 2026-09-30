import secrets

from app.auth import hash_token
from app.config import get_settings
from app.crypto import decrypt
from app.models import ApiToken, Item, User
from tests.conftest import account, page, txn


def test_api_requires_auth(client):
    for path in ["/api/v1/me", "/api/v1/items", "/api/v1/transactions", "/api/v1/insights/summary", "/api/v1/networth/current"]:
        assert client.get(path).status_code == 401, path


def test_dev_login_and_me(auth_client):
    r = auth_client.get("/api/v1/me")
    assert r.status_code == 200 and r.json()["email"] == "me@example.com"


def test_logout(auth_client):
    auth_client.post("/auth/logout")
    assert auth_client.get("/api/v1/me").status_code == 401


def test_allowlist_is_rechecked_on_every_request(auth_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "allowed_emails", "someone-else@example.com")
    assert auth_client.get("/api/v1/me").status_code == 401
    r = auth_client.get("/auth/dev-login", follow_redirects=False)
    assert r.headers["location"].endswith("/login?error=not_allowed")


def test_dev_login_disabled_in_production(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "env", "production")
    assert client.get("/auth/dev-login", follow_redirects=False).status_code == 404


def test_bearer_token(client, db):
    user = User(email="me@example.com")
    raw = secrets.token_urlsafe(32)
    db.add(user)
    db.flush()
    db.add(ApiToken(user_id=user.id, token_hash=hash_token(raw)))
    db.commit()
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {raw}"}).status_code == 200
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer wrong"}).status_code == 401


def _connect(auth_client, fake_plaid):
    token = "access-public-sandbox-1"
    fake_plaid.accounts[token] = [account(current=2500), account("acc-card", "credit", 400, "Card")]
    fake_plaid.sync_pages[token] = [
        page(
            added=[
                txn("pay", -3000, "2026-09-01", "INCOME", "INCOME_WAGES"),
                txn("coffee", 5.5, "2026-09-02", "FOOD_AND_DRINK", account="acc-card"),
                txn("groceries", 94.5, "2026-09-03", "FOOD_AND_DRINK", account="acc-card"),
                txn("cc-pay", 400, "2026-09-15", "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
            ]
        )
    ]
    r = auth_client.post(
        "/api/v1/plaid/exchange",
        json={"public_token": "public-sandbox-1", "institution_id": "ins_109508", "institution_name": "First Platypus Bank"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_full_flow(auth_client, fake_plaid, db):
    assert auth_client.post("/api/v1/plaid/link-token", json={}).json() == {"link_token": "link-sandbox-token"}

    item = _connect(auth_client, fake_plaid)
    assert item["institution_name"] == "First Platypus Bank" and item["status"] == "ok"
    assert {a["name"] for a in item["accounts"]} == {"Checking", "Card"}

    # Access token is stored encrypted, never returned.
    stored = db.get(Item, item["id"])
    assert decrypt(stored.access_token_enc) == "access-public-sandbox-1"
    assert "access-public-sandbox-1" not in auth_client.get("/api/v1/items").text

    txns = auth_client.get("/api/v1/transactions").json()
    assert txns["total"] == 4
    assert {t["name"]: t["counted"] for t in txns["items"]}["cc-pay"] is False
    assert {t["name"]: t["counted"] for t in txns["items"]}["coffee"] is True
    assert auth_client.get("/api/v1/transactions", params={"search": "coff"}).json()["total"] == 1

    s = auth_client.get("/api/v1/insights/summary", params={"month": "2026-09"}).json()
    assert s["income"] == 3000 and s["spending"] == 100 and s["net"] == 2900
    assert s["categories"] == [{"category": "FOOD_AND_DRINK", "amount": 100.0, "count": 2}]

    # Recategorize groceries; summary follows.
    groceries = next(t for t in txns["items"] if t["name"] == "groceries")
    r = auth_client.patch(f"/api/v1/transactions/{groceries['id']}", json={"category_override": "GENERAL_MERCHANDISE"})
    assert r.json()["category"] == "GENERAL_MERCHANDISE"
    s = auth_client.get("/api/v1/insights/summary", params={"month": "2026-09"}).json()
    assert {c["category"] for c in s["categories"]} == {"FOOD_AND_DRINK", "GENERAL_MERCHANDISE"}

    flow = auth_client.get("/api/v1/insights/cashflow", params={"months": 2, "end_month": "2026-09"}).json()
    assert [p["month"] for p in flow] == ["2026-08", "2026-09"]

    nw = auth_client.get("/api/v1/networth/current").json()
    assert nw["assets"] == 2500 and nw["liabilities"] == 400 and nw["net_worth"] == 2100
    hist = auth_client.get("/api/v1/networth/history").json()
    assert len(hist) == 1 and hist[0]["net_worth"] == 2100

    # Hiding the card removes it from net worth.
    card = next(a for a in item["accounts"] if a["name"] == "Card")
    auth_client.patch(f"/api/v1/accounts/{card['id']}", json={"hidden": True})
    assert auth_client.get("/api/v1/networth/current").json()["net_worth"] == 2500

    # Update-mode link token passes the Item's access token to Plaid.
    auth_client.post("/api/v1/plaid/link-token", json={"item_id": item["id"]})
    assert fake_plaid.link_calls[-1][1] == "access-public-sandbox-1"

    assert auth_client.delete(f"/api/v1/items/{item['id']}").json() == {"ok": True}
    assert fake_plaid.removed == ["access-public-sandbox-1"]
    assert auth_client.get("/api/v1/items").json() == []
    assert auth_client.get("/api/v1/transactions").json()["total"] == 0


def test_budgets(auth_client, fake_plaid):
    _connect(auth_client, fake_plaid)
    r = auth_client.put("/api/v1/budgets/FOOD_AND_DRINK", json={"monthly_limit": 250})
    assert r.status_code == 200
    budgets = auth_client.get("/api/v1/budgets", params={"month": "2026-09"}).json()
    assert budgets == [{"id": budgets[0]["id"], "category": "FOOD_AND_DRINK", "monthly_limit": 250.0, "spent": 100.0, "remaining": 150.0}]
    assert auth_client.put("/api/v1/budgets/FOOD_AND_DRINK", json={"monthly_limit": 0}).status_code == 422
    auth_client.delete(f"/api/v1/budgets/{budgets[0]['id']}")
    assert auth_client.get("/api/v1/budgets").json() == []


def test_recurring_monthly_equivalents(auth_client, fake_plaid):
    token = "access-public-sandbox-1"
    fake_plaid.recurring[token] = {
        "inflow_streams": [
            {"stream_id": "pay", "account_id": "acc-checking", "frequency": "BIWEEKLY", "average_amount": {"amount": -1200}, "is_active": True}
        ],
        "outflow_streams": [
            {"stream_id": "gym", "account_id": "acc-checking", "frequency": "MONTHLY", "average_amount": {"amount": 40}, "is_active": True},
            {"stream_id": "domain", "account_id": "acc-checking", "frequency": "ANNUALLY", "average_amount": {"amount": 120}, "is_active": True},
            {"stream_id": "old", "account_id": "acc-checking", "frequency": "MONTHLY", "average_amount": {"amount": 9}, "is_active": False},
        ],
    }
    _connect(auth_client, fake_plaid)
    r = auth_client.get("/api/v1/recurring").json()
    assert len(r["streams"]) == 3
    assert r["monthly_outflow"] == 50.0  # 40 + 120/12
    assert round(r["monthly_inflow"], 2) == 2600.0  # 1200 * 26 / 12
    assert len(auth_client.get("/api/v1/recurring", params={"include_inactive": True}).json()["streams"]) == 4


def test_cannot_touch_another_users_item(auth_client, fake_plaid, db):
    other = User(email="other@example.com")
    db.add(Item(user=other, plaid_item_id="item-x", access_token_enc="x"))
    db.commit()
    item_id = db.query(Item).filter_by(plaid_item_id="item-x").one().id
    assert auth_client.delete(f"/api/v1/items/{item_id}").status_code == 404
    assert auth_client.post(f"/api/v1/items/{item_id}/sync").status_code == 404
    assert auth_client.post("/api/v1/plaid/link-token", json={"item_id": item_id}).status_code == 404


def test_cron_requires_secret(client, fake_plaid):
    assert client.post("/api/v1/cron/sync").status_code == 401
    assert client.post("/api/v1/cron/sync", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/v1/cron/sync", headers={"Authorization": "Bearer cron-secret"}).json() == []
