# Finance Tracker

A private app that connects your bank, card, and investment accounts through Plaid. It shows spending and income, monthly budgets, recurring charges, and net worth over time.

- **backend/**: FastAPI, SQLAlchemy and Alembic, plaid-python. Every calculation happens here. The web app, and a future iOS app, only display results.
- **frontend/**: Vite, React, TypeScript, TanStack Query, and Recharts. API types are generated from the backend's OpenAPI spec.
- **Deploy**: one Docker service on Render, with FastAPI also serving the built React app. The database is Postgres on Neon. A daily GitHub Action runs the sync.

## Run it locally

Requires Python 3.11 and Node 22. `.env` lives at the repo root; copy `.env.example` and fill it in.

```sh
# backend (terminal 1)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.demo          # optional: a year of fake data to explore
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (terminal 2)
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

Open http://localhost:5173 and choose **Continue with dev login**. This works when `DEV_LOGIN_EMAIL` is set and `ENV=development`. Remove the demo data with `python -m app.demo --clear`; the demo bank can't sync.

Tests: `cd backend && .venv/bin/pytest`. After changing an API model, run `npm run gen:api` in `frontend/` to regenerate `src/api/schema.d.ts`.

## Connect Plaid (Sandbox)

1. Sign up at https://dashboard.plaid.com.
2. Copy your `client_id` and Sandbox secret from **Developers > Keys** into `PLAID_CLIENT_ID` and `PLAID_SECRET`.
3. Restart the backend. On **Accounts**, click **Connect an account**, pick any bank, and sign in with `user_transactions_dynamic` and any password.
4. Optional: to test OAuth banks such as "Platypus OAuth Bank", add `http://localhost:5173/plaid-oauth` under **Developers > API > Allowed redirect URIs**. Then set `PLAID_REDIRECT_URI` to that URL.

Plaid can't send webhooks to localhost. Use **Refresh** in the sidebar, or run a tunnel (for example `cloudflared tunnel --url http://localhost:8000`) and set `PLAID_WEBHOOK_URL=https://<tunnel>/api/v1/plaid/webhook`.

## Sign in with Google or GitHub

Only emails listed in `ALLOWED_EMAILS` can sign in. The list is checked on every request, so removing an email revokes access immediately.

- **Google**: at https://console.cloud.google.com/apis/credentials, create an OAuth client ID of type "Web application". Add redirect URIs `http://localhost:5173/auth/callback/google` and `https://<your-app>/auth/callback/google`. Then set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
- **GitHub**: at https://github.com/settings/developers, create a new OAuth App with callback `https://<your-app>/auth/callback/github`. GitHub allows one callback per app, so create a second app for localhost. Then set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.

## Deploy (Render + Neon)

1. **Neon** (https://neon.tech): create a project and copy the connection string. That becomes `DATABASE_URL`.
2. Push this repo to GitHub.
3. **Render**: go to New > Blueprint and pick the repo; it reads `render.yaml`. Fill in the blank env vars:
   - `APP_URL`: your `https://…onrender.com` URL.
   - `ENCRYPTION_KEY`: generate one with `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`. **Keep a copy.** If you lose it, every bank has to be reconnected.
   - `CRON_SECRET`: any long random string.
   - The Plaid and OAuth keys.
4. **Plaid Dashboard**: add `https://<your-app>/plaid-oauth` as an allowed redirect URI, then set `PLAID_REDIRECT_URI` to it. Webhooks go to `APP_URL/api/v1/plaid/webhook` automatically.
5. **GitHub**: go to repo Settings > Secrets > Actions and add `APP_URL` and `CRON_SECRET`. The **Daily sync** workflow then runs every morning. It also records the daily balance point for net worth history. You can run it by hand from the Actions tab.

The free Render plan sleeps when idle, so the first request takes about a minute. The cron job retries through the wake-up, and Plaid retries webhooks. Upgrade to `starter` if the delay bothers you.

## Real accounts (Plaid Production)

In the Plaid Dashboard, request Production access: complete the company profile and the security questionnaire. Then set `PLAID_ENV=production` and swap in the Production secret.

- OAuth banks (Chase, Bank of America, Wells Fargo, Capital One, and others) need extra registration in the dashboard, which can take days to weeks.
- Transactions is billed per connected institution per month once you're past the free tier. Check Plaid's current pricing.
- Sandbox connections don't carry over. Disconnect them and connect your real banks.

## How the numbers work

- Plaid amounts are **positive for money out** and negative for money in.
- **Transfers between your accounts and credit card payments are excluded** from both spending and income, so nothing is counted twice. Excluded rows appear muted on the Transactions page.
- Refunds reduce spending in their category. Changing a transaction's category overrides Plaid's label, and syncing never undoes your change.
- Hiding an account (Accounts page) removes it from every total.
- Net worth is assets minus what you owe on cards and loans. Plaid doesn't provide past balances, so history starts the day you connect.

## Security

- Plaid access tokens are encrypted at rest with Fernet.
- The Plaid secret and access tokens never reach the browser.
- Webhooks are checked for Plaid's signature, their age, and a hash of the request body.
- The cron endpoint requires `CRON_SECRET`.
- Session cookies are signed, `HttpOnly`, `SameSite=Lax`, and `Secure` in production.

## Future iOS app

The API is versioned under `/api/v1`, and `require_user` already accepts `Authorization: Bearer <token>` (see the `api_tokens` table). Steps:

1. Add a `POST /api/v1/auth/mobile` endpoint. It verifies a native Google or Apple ID token, checks the allowlist, and returns an API token.
2. Generate a Swift client from `/api/v1/openapi.json` with `swift-openapi-generator`.
3. Use Plaid LinkKit with a universal-link redirect URI.

The App Store requires Sign in with Apple when an app offers Google or GitHub sign-in. Installing only for yourself through Xcode or TestFlight doesn't.
