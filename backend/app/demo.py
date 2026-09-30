"""Load a year of realistic fake data so you can explore the UI before connecting Plaid.

    python -m app.demo          # load (replaces any previous demo data)
    python -m app.demo --clear  # remove it

Development only. The demo institution can't sync (it has no real Plaid token).
"""

import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.crypto import encrypt
from app.db import SessionLocal
from app.models import Account, BalanceSnapshot, Budget, Item, RecurringStream, Transaction, User
from app.services.sync import today

DEMO_ITEM_ID = "demo-item"


def _user(db) -> User:
    s = get_settings()
    email = (s.dev_login_email or next(iter(s.allowed_email_set), "")).lower()
    if not email:
        sys.exit("Set DEV_LOGIN_EMAIL or ALLOWED_EMAILS first.")
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name="Dev User", provider="dev")
        db.add(user)
        db.flush()
    return user


def clear(db) -> None:
    item = db.scalar(select(Item).where(Item.plaid_item_id == DEMO_ITEM_ID))
    if item:
        db.delete(item)
    db.commit()


def load(db) -> None:
    clear(db)
    rng = random.Random(42)
    user = _user(db)
    end = today()
    start = date(end.year - 1, end.month, 1)

    item = Item(
        user_id=user.id,
        plaid_item_id=DEMO_ITEM_ID,
        access_token_enc=encrypt("demo-not-a-real-token"),
        institution_name="Demo Bank",
        status="ok",
    )
    db.add(item)
    checking = Account(item=item, plaid_account_id="demo-checking", name="Everyday Checking", mask="4821", type="depository", subtype="checking", current_balance=Decimal("3240.18"), available_balance=Decimal("3190.18"), currency="USD")
    savings = Account(item=item, plaid_account_id="demo-savings", name="High Yield Savings", mask="9012", type="depository", subtype="savings", current_balance=Decimal("12500.00"), currency="USD")
    card = Account(item=item, plaid_account_id="demo-card", name="Rewards Card", mask="3377", type="credit", subtype="credit card", current_balance=Decimal("845.62"), credit_limit=Decimal("8000"), currency="USD")
    brokerage = Account(item=item, plaid_account_id="demo-brokerage", name="Brokerage", mask="5566", type="investment", subtype="brokerage", current_balance=Decimal("18310.44"), currency="USD")
    db.add_all([checking, savings, card, brokerage])
    db.flush()

    n = 0

    def add(acct, d, name, amount, primary, detailed=None, merchant=None):
        nonlocal n
        if d > end:
            return
        n += 1
        db.add(
            Transaction(
                account_id=acct.id,
                plaid_transaction_id=f"demo-{n}",
                date=d,
                name=name,
                merchant_name=merchant,
                amount=Decimal(str(round(amount, 2))),
                currency="USD",
                pending=(end - d).days < 2 and amount > 0,
                pfc_primary=primary,
                pfc_detailed=detailed or f"{primary}_OTHER",
            )
        )

    # Paychecks every other Friday.
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    while d <= end:
        add(checking, d, "ACME CORP PAYROLL", -2150.00, "INCOME", "INCOME_WAGES", "Acme Corp")
        d += timedelta(days=14)

    m = start
    while m <= end:
        y, mo = m.year, m.month
        day = lambda dd: date(y, mo, min(dd, 28))  # noqa: E731
        add(checking, day(1), "RENT PAYMENT", 1450.00, "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT")
        add(checking, day(12), "EVERSOURCE ENERGY", rng.uniform(70, 135), "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY", "Eversource")
        add(checking, day(18), "COMCAST XFINITY", 65.00, "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_INTERNET_AND_CABLE", "Xfinity")
        add(checking, day(3), "TRANSFER TO SAVINGS", 500.00, "TRANSFER_OUT", "TRANSFER_OUT_SAVINGS")
        add(savings, day(3), "TRANSFER FROM CHECKING", -500.00, "TRANSFER_IN", "TRANSFER_IN_SAVINGS")
        add(savings, day(28), "INTEREST PAYMENT", -round(rng.uniform(38, 46), 2), "INCOME", "INCOME_INTEREST_EARNED")

        card_total = 0.0

        def charge(dd, name, amount, primary, detailed=None, merchant=None):
            nonlocal card_total
            card_total += amount
            add(card, day(dd), name, amount, primary, detailed, merchant)

        charge(5, "NETFLIX.COM", 15.49, "ENTERTAINMENT", "ENTERTAINMENT_TV_AND_MOVIES", "Netflix")
        charge(9, "SPOTIFY USA", 11.99, "ENTERTAINMENT", "ENTERTAINMENT_MUSIC_AND_AUDIO", "Spotify")
        charge(2, "PLANET FITNESS", 40.00, "PERSONAL_CARE", "PERSONAL_CARE_GYMS_AND_FITNESS_CENTERS", "Planet Fitness")
        for w in range(4):
            charge(3 + w * 7, "TRADER JOE'S", rng.uniform(55, 140), "FOOD_AND_DRINK", "FOOD_AND_DRINK_GROCERIES", "Trader Joe's")
        for _ in range(rng.randint(4, 9)):
            place = rng.choice(["Sweetgreen", "Chipotle", "Tatte Bakery", "Shake Shack", "Pho Basil"])
            charge(rng.randint(1, 28), place.upper(), rng.uniform(12, 58), "FOOD_AND_DRINK", "FOOD_AND_DRINK_RESTAURANT", place)
        for _ in range(rng.randint(6, 12)):
            charge(rng.randint(1, 28), "DUNKIN", rng.uniform(3.5, 8), "FOOD_AND_DRINK", "FOOD_AND_DRINK_COFFEE", "Dunkin'")
        for _ in range(rng.randint(2, 6)):
            charge(rng.randint(1, 28), "UBER TRIP", rng.uniform(11, 34), "TRANSPORTATION", "TRANSPORTATION_TAXIS_AND_RIDE_SHARES", "Uber")
        charge(1, "MBTA CHARLIECARD", 90.00, "TRANSPORTATION", "TRANSPORTATION_PUBLIC_TRANSIT", "MBTA")
        for _ in range(rng.randint(1, 4)):
            charge(rng.randint(1, 28), "AMAZON MKTPLACE", rng.uniform(14, 120), "GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_ONLINE_MARKETPLACES", "Amazon")
        if rng.random() < 0.35:
            add(card, day(rng.randint(1, 28)), "AMAZON REFUND", -rng.uniform(15, 60), "GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_ONLINE_MARKETPLACES", "Amazon")
        if mo in (3, 7, 12):
            charge(14, "JETBLUE AIRWAYS", rng.uniform(220, 410), "TRAVEL", "TRAVEL_FLIGHTS", "JetBlue")
        # Card bill paid from checking: excluded from spending on both sides.
        add(checking, day(22), "RWDS CARD AUTOPAY", round(card_total, 2), "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT")
        add(card, day(22), "AUTOPAY PAYMENT THANK YOU", -round(card_total, 2), "LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT")

        m = date(y + (mo == 12), mo % 12 + 1, 1)

    # 120 days of balance snapshots with a gentle upward drift.
    balances = {checking.id: 2600.0, savings.id: 10500.0, card.id: 1200.0, brokerage.id: 16200.0}
    finals = {checking.id: 3240.18, savings.id: 12500.0, card.id: 845.62, brokerage.id: 18310.44}
    days = 120
    for i in range(days + 1):
        d = end - timedelta(days=days - i)
        for acct_id, final in finals.items():
            start_bal = balances[acct_id]
            noise = rng.uniform(-0.012, 0.012) * final if acct_id == brokerage.id else rng.uniform(-120, 120)
            value = start_bal + (final - start_bal) * i / days + (noise if i < days else 0)
            db.add(BalanceSnapshot(account_id=acct_id, date=d, current_balance=Decimal(str(round(max(value, 0), 2)))))

    def next_on(dd: int) -> date:
        cand = date(end.year, end.month, dd)
        return cand if cand > end else date(end.year + (end.month == 12), end.month % 12 + 1, dd)

    streams = [
        ("netflix", card, "outflow", "Netflix", "MONTHLY", 15.49, 5, "ENTERTAINMENT"),
        ("spotify", card, "outflow", "Spotify", "MONTHLY", 11.99, 9, "ENTERTAINMENT"),
        ("gym", card, "outflow", "Planet Fitness", "MONTHLY", 40.00, 2, "PERSONAL_CARE"),
        ("rent", checking, "outflow", "Rent payment", "MONTHLY", 1450.00, 1, "RENT_AND_UTILITIES"),
        ("xfinity", checking, "outflow", "Xfinity", "MONTHLY", 65.00, 18, "RENT_AND_UTILITIES"),
        ("mbta", card, "outflow", "MBTA", "MONTHLY", 90.00, 1, "TRANSPORTATION"),
        ("pay", checking, "inflow", "Acme Corp", "BIWEEKLY", 2150.00, 0, "INCOME"),
    ]
    for sid, acct, direction, name, freq, amount, dd, cat in streams:
        nxt = end + timedelta(days=(4 - end.weekday()) % 7 or 7) if dd == 0 else next_on(dd)
        db.add(
            RecurringStream(
                account_id=acct.id, plaid_stream_id=f"demo-{sid}", direction=direction, description=name.upper(),
                merchant_name=name, frequency=freq, average_amount=Decimal(str(amount)), last_amount=Decimal(str(amount)),
                first_date=start, last_date=nxt - timedelta(days=14 if freq == "BIWEEKLY" else 30),
                predicted_next_date=nxt, is_active=True, status="MATURE", category=cat,
            )
        )

    for cat, limit in [("FOOD_AND_DRINK", 600), ("ENTERTAINMENT", 60), ("GENERAL_MERCHANDISE", 200), ("TRANSPORTATION", 180)]:
        if not db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category == cat)):
            db.add(Budget(user_id=user.id, category=cat, monthly_limit=Decimal(limit)))

    db.commit()
    print(f"Loaded demo data for {user.email}: {n} transactions, 4 accounts.")


if __name__ == "__main__":
    if get_settings().is_production:
        sys.exit("Refusing to load demo data with ENV=production.")
    with SessionLocal() as session:
        if "--clear" in sys.argv:
            clear(session)
            print("Removed demo data.")
        else:
            load(session)
