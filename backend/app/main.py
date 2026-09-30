import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from app import auth
from app.config import get_settings
from app.routers import accounts, budgets, cron, insights, networth, plaid, recurring, transactions

logging.basicConfig(level=logging.INFO)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Finance Tracker", openapi_url="/api/v1/openapi.json", docs_url="/api/docs", redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=s.session_secret,
        session_cookie="ft_session",
        max_age=30 * 24 * 3600,
        same_site="lax",
        https_only=s.is_production,
    )

    app.include_router(auth.router)
    for r in (plaid, accounts, transactions, insights, budgets, recurring, networth, cron):
        app.include_router(r.router)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    # In production FastAPI serves the built React app; unknown paths fall back to index.html
    # so client-side routes (e.g. /transactions, /plaid-oauth) work on reload.
    if FRONTEND_DIST.exists():

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith(("api/", "auth/")):
                raise HTTPException(404)
            file = (FRONTEND_DIST / path).resolve()
            if path and file.is_file() and FRONTEND_DIST in file.parents:
                return FileResponse(file)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
