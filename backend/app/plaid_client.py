"""Thin wrapper over plaid-python that returns plain dicts and raises PlaidError.

Keeping the rest of the app on dicts makes the sync/analytics code easy to test with a fake.
"""

import json
from functools import lru_cache

import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

from app.config import get_settings


class PlaidError(Exception):
    def __init__(self, code: str, message: str = "", error_type: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.error_type = error_type


def _wrap(fn):
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except plaid.ApiException as e:
            try:
                body = json.loads(e.body or "{}")
            except ValueError:
                body = {}
            raise PlaidError(
                body.get("error_code", "UNKNOWN"),
                body.get("error_message", str(e)),
                body.get("error_type", ""),
            ) from e

    return inner


class PlaidService:
    def __init__(self, api: plaid_api.PlaidApi):
        self.api = api

    @_wrap
    def create_link_token(self, user_id: int, access_token: str | None = None) -> str:
        s = get_settings()
        kwargs = dict(
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            client_name="Finance Tracker",
            country_codes=[CountryCode("US")],
            language="en",
        )
        if access_token:
            kwargs["access_token"] = access_token  # update mode (reconnect)
        else:
            kwargs["products"] = [Products("transactions")]
            kwargs["transactions"] = LinkTokenTransactions(days_requested=730)
        if s.plaid_redirect_uri:
            kwargs["redirect_uri"] = s.plaid_redirect_uri
        if s.webhook_url:
            kwargs["webhook"] = s.webhook_url
        return self.api.link_token_create(LinkTokenCreateRequest(**kwargs)).link_token

    @_wrap
    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        resp = self.api.item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=public_token)
        )
        return resp.access_token, resp.item_id

    @_wrap
    def transactions_sync(self, access_token: str, cursor: str | None) -> dict:
        kwargs = {"access_token": access_token, "count": 500}
        if cursor:
            kwargs["cursor"] = cursor
        return self.api.transactions_sync(TransactionsSyncRequest(**kwargs)).to_dict()

    @_wrap
    def accounts_get(self, access_token: str) -> list[dict]:
        resp = self.api.accounts_get(AccountsGetRequest(access_token=access_token))
        return resp.to_dict()["accounts"]

    @_wrap
    def recurring_get(self, access_token: str) -> dict:
        req = TransactionsRecurringGetRequest(access_token=access_token)
        return self.api.transactions_recurring_get(req).to_dict()

    @_wrap
    def item_remove(self, access_token: str) -> None:
        self.api.item_remove(ItemRemoveRequest(access_token=access_token))

    @_wrap
    def webhook_verification_key(self, key_id: str) -> dict:
        req = WebhookVerificationKeyGetRequest(key_id=key_id)
        return self.api.webhook_verification_key_get(req).to_dict()["key"]


@lru_cache
def _plaid_service() -> PlaidService:
    s = get_settings()
    host = plaid.Environment.Production if s.plaid_env == "production" else plaid.Environment.Sandbox
    config = plaid.Configuration(
        host=host,
        api_key={"clientId": s.plaid_client_id, "secret": s.plaid_secret, "plaidVersion": "2020-09-14"},
    )
    return PlaidService(plaid_api.PlaidApi(plaid.ApiClient(config)))


def get_plaid() -> PlaidService:
    """FastAPI dependency; override in tests."""
    return _plaid_service()
