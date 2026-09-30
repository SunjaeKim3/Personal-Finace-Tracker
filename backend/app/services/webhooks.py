"""Plaid webhook verification: https://plaid.com/docs/api/webhooks/webhook-verification/"""

import hashlib
import hmac
import json
import time

import jwt
from jwt.algorithms import ECAlgorithm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item
from app.plaid_client import PlaidService
from app.services.sync import LOGIN_REQUIRED_CODES as SYNC_LOGIN_CODES
from app.services.sync import sync_item

MAX_AGE_SECONDS = 5 * 60
_JWK_FIELDS = ("alg", "crv", "kid", "kty", "use", "x", "y")
_key_cache: dict[str, dict] = {}


class WebhookVerificationError(Exception):
    pass


def _public_key(plaid: PlaidService, kid: str):
    jwk = _key_cache.get(kid)
    if jwk is None:
        jwk = plaid.webhook_verification_key(kid)
        if jwk.get("expired_at") is None:
            _key_cache[kid] = jwk
    if jwk.get("expired_at") is not None:
        raise WebhookVerificationError("verification key expired")
    return ECAlgorithm.from_jwk(json.dumps({k: jwk[k] for k in _JWK_FIELDS if k in jwk}))


def verify(plaid: PlaidService, body: bytes, token: str | None, now: float | None = None) -> None:
    if not token:
        raise WebhookVerificationError("missing Plaid-Verification header")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise WebhookVerificationError(f"malformed JWT: {e}") from e
    if header.get("alg") != "ES256" or not header.get("kid"):
        raise WebhookVerificationError("unexpected JWT header")

    try:
        claims = jwt.decode(token, _public_key(plaid, header["kid"]), algorithms=["ES256"], options={"require": ["iat"]})
    except jwt.PyJWTError as e:
        raise WebhookVerificationError(f"invalid signature: {e}") from e

    if (now or time.time()) - claims["iat"] > MAX_AGE_SECONDS:
        raise WebhookVerificationError("webhook too old")
    expected = claims.get("request_body_sha256", "")
    if not hmac.compare_digest(expected, hashlib.sha256(body).hexdigest()):
        raise WebhookVerificationError("body hash mismatch")


# --- Event handling --------------------------------------------------------------------------

SYNC_CODES = {"SYNC_UPDATES_AVAILABLE", "RECURRING_TRANSACTIONS_UPDATE"}
LOGIN_REQUIRED_CODES = {"PENDING_EXPIRATION", "PENDING_DISCONNECT"}
REVOKED_CODES = {"USER_PERMISSION_REVOKED", "USER_ACCOUNT_REVOKED"}


def handle(db: Session, plaid: PlaidService, payload: dict) -> str:
    """Apply a verified webhook. Returns a short description of what was done (for logs/tests)."""
    item = db.scalar(select(Item).where(Item.plaid_item_id == payload.get("item_id")))
    if item is None:
        return "unknown item"
    wtype, code = payload.get("webhook_type"), payload.get("webhook_code")

    if wtype == "TRANSACTIONS" and code in SYNC_CODES:
        sync_item(db, plaid, item)
        return "synced"
    if wtype == "ITEM":
        if code == "ERROR":
            error_code = (payload.get("error") or {}).get("error_code")
            item.status = "login_required" if error_code in SYNC_LOGIN_CODES else "error"
            item.error_code = error_code
        elif code in LOGIN_REQUIRED_CODES:
            item.status, item.error_code = "login_required", code
        elif code in REVOKED_CODES:
            item.status, item.error_code = "error", code
        elif code == "LOGIN_REPAIRED":
            sync_item(db, plaid, item)
            return "synced"
        else:
            return "ignored"
        db.commit()
        return f"status={item.status}"
    return "ignored"
