import hashlib
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.crypto import encrypt
from app.models import Item, User
from app.services import webhooks
from tests.conftest import account, page, txn

KID = "test-key"


@pytest.fixture
def signing_key(fake_plaid):
    webhooks._key_cache.clear()
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    fake_plaid.keys[KID] = {**jwk, "alg": "ES256", "kid": KID, "use": "sig", "created_at": 0, "expired_at": None}
    return key


def sign(key, body: bytes, iat: float | None = None, kid: str = KID) -> str:
    claims = {"iat": int(iat or time.time()), "request_body_sha256": hashlib.sha256(body).hexdigest()}
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})


BODY = json.dumps({"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": "item-1"}).encode()


def test_valid_signature(fake_plaid, signing_key):
    webhooks.verify(fake_plaid, BODY, sign(signing_key, BODY))


def test_rejects_wrong_key(fake_plaid, signing_key):
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(webhooks.WebhookVerificationError, match="signature"):
        webhooks.verify(fake_plaid, BODY, sign(other, BODY))


def test_rejects_stale(fake_plaid, signing_key):
    with pytest.raises(webhooks.WebhookVerificationError, match="too old"):
        webhooks.verify(fake_plaid, BODY, sign(signing_key, BODY, iat=time.time() - 600))


def test_rejects_tampered_body(fake_plaid, signing_key):
    token = sign(signing_key, BODY)
    with pytest.raises(webhooks.WebhookVerificationError, match="hash"):
        webhooks.verify(fake_plaid, BODY.replace(b"item-1", b"item-2"), token)


def test_rejects_missing_header(fake_plaid):
    with pytest.raises(webhooks.WebhookVerificationError, match="missing"):
        webhooks.verify(fake_plaid, BODY, None)


def test_rejects_expired_key(fake_plaid, signing_key):
    fake_plaid.keys[KID]["expired_at"] = 1
    with pytest.raises(webhooks.WebhookVerificationError, match="expired"):
        webhooks.verify(fake_plaid, BODY, sign(signing_key, BODY))


def _item(db, token="access-test"):
    item = Item(user=User(email="me@example.com"), plaid_item_id="item-1", access_token_enc=encrypt(token))
    db.add(item)
    db.commit()
    return item


def test_endpoint_syncs_item(client, db, fake_plaid, signing_key):
    item = _item(db)
    fake_plaid.accounts["access-test"] = [account()]
    fake_plaid.sync_pages["access-test"] = [page(added=[txn("t1", 10)])]

    r = client.post("/api/v1/plaid/webhook", content=BODY, headers={"Plaid-Verification": sign(signing_key, BODY)})
    assert r.status_code == 200
    db.refresh(item)
    assert item.last_synced_at is not None and item.sync_cursor == "c1"


def test_endpoint_rejects_unsigned(client):
    r = client.post("/api/v1/plaid/webhook", content=BODY)
    assert r.status_code == 401


@pytest.mark.parametrize(
    "payload, status, error_code",
    [
        ({"webhook_type": "ITEM", "webhook_code": "ERROR", "error": {"error_code": "ITEM_LOGIN_REQUIRED"}}, "login_required", "ITEM_LOGIN_REQUIRED"),
        ({"webhook_type": "ITEM", "webhook_code": "PENDING_EXPIRATION"}, "login_required", "PENDING_EXPIRATION"),
        ({"webhook_type": "ITEM", "webhook_code": "USER_PERMISSION_REVOKED"}, "error", "USER_PERMISSION_REVOKED"),
    ],
)
def test_item_status_webhooks(db, fake_plaid, payload, status, error_code):
    item = _item(db)
    webhooks.handle(db, fake_plaid, {**payload, "item_id": "item-1"})
    db.refresh(item)
    assert (item.status, item.error_code) == (status, error_code)


def test_login_repaired_resyncs(db, fake_plaid):
    item = _item(db)
    item.status = "login_required"
    db.commit()
    assert webhooks.handle(db, fake_plaid, {"webhook_type": "ITEM", "webhook_code": "LOGIN_REPAIRED", "item_id": "item-1"}) == "synced"
    assert item.status == "ok"
