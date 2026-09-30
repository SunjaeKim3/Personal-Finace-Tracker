from datetime import date
from decimal import Decimal

import pytest

from app.models import Account, Item, Transaction, User
from app.services import analytics
from app.services.analytics import classify


@pytest.mark.parametrize(
    "amount, primary, detailed, override, expected",
    [
        (-2500, "INCOME", "INCOME_WAGES", None, ("income", "INCOME")),
        (4.5, "FOOD_AND_DRINK", "FOOD_AND_DRINK_COFFEE", None, ("spending", "FOOD_AND_DRINK")),
        # Refund: inflow in a spending category stays in spending and reduces it.
        (-20, "GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_OTHER", None, ("spending", "GENERAL_MERCHANDISE")),
        (500, "TRANSFER_OUT", "TRANSFER_OUT_SAVINGS", None, (None, "TRANSFER_OUT")),
        (-500, "TRANSFER_IN", "TRANSFER_IN_SAVINGS", None, (None, "TRANSFER_IN")),
        # Card payment would double-count the card's purchases.
        (300, "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT", None, (None, "LOAN_PAYMENTS")),
        # Other loan payments (mortgage, car) are real spending.
        (1800, "LOAN_PAYMENTS", "LOAN_PAYMENTS_MORTGAGE_PAYMENT", None, ("spending", "LOAN_PAYMENTS")),
        # User override wins in both directions.
        (300, "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT", "RENT_AND_UTILITIES", ("spending", "RENT_AND_UTILITIES")),
        (60, "FOOD_AND_DRINK", "FOOD_AND_DRINK_GROCERIES", "TRANSFER_OUT", (None, "TRANSFER_OUT")),
        (-100, "GENERAL_SERVICES", None, "INCOME", ("income", "INCOME")),
        # Uncategorized inflow counts as income; uncategorized outflow as spending.
        (-75, None, None, None, ("income", "OTHER")),
        (75, None, None, None, ("spending", "OTHER")),
    ],
)
def test_classify(amount, primary, detailed, override, expected):
    assert classify(Decimal(amount), primary, detailed, override) == expected


@pytest.mark.parametrize(
    "y, m, delta, expected",
    [(2026, 1, -1, (2025, 12)), (2026, 12, 1, (2027, 1)), (2026, 9, -11, (2025, 10)), (2026, 5, 0, (2026, 5))],
)
def test_shift_month(y, m, delta, expected):
    assert analytics.shift_month(y, m, delta) == expected


def _seed(db):
    user = User(email="me@example.com")
    item = Item(user=user, plaid_item_id="item-1", access_token_enc="x")
    checking = Account(item=item, plaid_account_id="a1", name="Checking", type="depository")
    card = Account(item=item, plaid_account_id="a2", name="Card", type="credit")
    hidden = Account(item=item, plaid_account_id="a3", name="Business", type="depository", hidden=True)
    rows = [
        (checking, "2026-09-01", -3000, "INCOME", "INCOME_WAGES", None),
        (card, "2026-09-03", 120, "FOOD_AND_DRINK", "FOOD_AND_DRINK_GROCERIES", None),
        (card, "2026-09-05", 80, "FOOD_AND_DRINK", "FOOD_AND_DRINK_RESTAURANT", None),
        (card, "2026-09-06", -30, "FOOD_AND_DRINK", "FOOD_AND_DRINK_RESTAURANT", None),  # refund
        (checking, "2026-09-07", 1500, "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT", None),
        (checking, "2026-09-20", 170, "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT", None),  # excluded
        (card, "2026-09-20", -170, "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT", None),  # excluded
        (checking, "2026-09-21", 1000, "TRANSFER_OUT", "TRANSFER_OUT_SAVINGS", None),  # excluded
        (checking, "2026-09-22", 40, "GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_OTHER", "ENTERTAINMENT"),
        (hidden, "2026-09-10", 999, "GENERAL_SERVICES", "GENERAL_SERVICES_OTHER", None),  # hidden account
        (checking, "2026-08-01", -3000, "INCOME", "INCOME_WAGES", None),
        (checking, "2026-08-07", 1500, "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT", None),
    ]
    for i, (acct, d, amount, primary, detailed, override) in enumerate(rows):
        db.add(
            Transaction(
                account=acct,
                plaid_transaction_id=f"t{i}",
                date=date.fromisoformat(d),
                name=f"t{i}",
                amount=Decimal(amount),
                pfc_primary=primary,
                pfc_detailed=detailed,
                category_override=override,
            )
        )
    db.commit()
    return user


def test_totals_excludes_transfers_card_payments_and_hidden(db):
    user = _seed(db)
    t = analytics.totals(db, user.id, *analytics.month_bounds(2026, 9))
    assert t.income == Decimal(3000)
    assert t.by_category == {
        "FOOD_AND_DRINK": Decimal(170),  # 120 + 80 - 30 refund
        "RENT_AND_UTILITIES": Decimal(1500),
        "ENTERTAINMENT": Decimal(40),
    }
    assert t.spending == Decimal(1710)
    assert t.net == Decimal(1290)


def test_monthly_cashflow_includes_empty_months(db):
    user = _seed(db)
    flow = analytics.monthly_cashflow(db, user.id, 2026, 9, 3)
    assert [p["month"] for p in flow] == ["2026-07", "2026-08", "2026-09"]
    assert flow[0]["income"] == 0 and flow[0]["spending"] == 0
    assert flow[1]["income"] == 3000 and flow[1]["spending"] == 1500 and flow[1]["net"] == 1500
    assert flow[2]["spending"] == 1710
