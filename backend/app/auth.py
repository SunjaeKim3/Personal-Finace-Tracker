import hashlib
from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ApiToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
PROVIDERS: list[str] = []
_settings = get_settings()
if _settings.google_client_id:
    PROVIDERS.append("google")
    oauth.register(
        name="google",
        client_id=_settings.google_client_id,
        client_secret=_settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
if _settings.github_client_id:
    PROVIDERS.append("github")
    oauth.register(
        name="github",
        client_id=_settings.github_client_id,
        client_secret=_settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )


def is_allowed(email: str | None) -> bool:
    return bool(email) and email.lower() in get_settings().allowed_email_set


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Accepts the web session cookie or an `Authorization: Bearer <api token>` header."""
    user = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(auth[7:].strip())))
        if token:
            token.last_used_at = datetime.now(timezone.utc)
            db.commit()
            user = db.get(User, token.user_id)
    elif uid := request.session.get("uid"):
        user = db.get(User, uid)

    # Re-check the allowlist so removing an email revokes access immediately.
    if user is None or not is_allowed(user.email):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _login(request: Request, db: Session, email: str, name: str | None, provider: str) -> RedirectResponse:
    app_url = get_settings().app_url
    if not is_allowed(email):
        return RedirectResponse(f"{app_url}/login?error=not_allowed")
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        user = User(email=email.lower())
        db.add(user)
    user.name = name or user.name
    user.provider = provider
    db.commit()
    request.session.clear()
    request.session["uid"] = user.id
    return RedirectResponse(f"{app_url}/")


@router.get("/providers")
def providers():
    s = get_settings()
    return {
        "providers": PROVIDERS,
        "dev_login": not s.is_production and bool(s.dev_login_email),
        "plaid_env": s.plaid_env,
    }


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(404, f"{provider} login is not configured")
    redirect_uri = f"{get_settings().app_url}/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request, db: Session = Depends(get_db)):
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(404)
    app_url = get_settings().app_url
    try:
        token = await client.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(f"{app_url}/login?error=oauth_failed")

    if provider == "google":
        info = token.get("userinfo") or {}
        if not info.get("email_verified"):
            return RedirectResponse(f"{app_url}/login?error=unverified_email")
        return _login(request, db, info["email"], info.get("name"), provider)

    # GitHub: use the primary verified email (the profile email can be hidden or unverified).
    emails = (await client.get("user/emails", token=token)).json()
    primary = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
    if primary is None:
        return RedirectResponse(f"{app_url}/login?error=unverified_email")
    profile = (await client.get("user", token=token)).json()
    return _login(request, db, primary, profile.get("name") or profile.get("login"), provider)


@router.get("/dev-login")
def dev_login(request: Request, db: Session = Depends(get_db)):
    """Local-only shortcut so you can try the app before setting up Google/GitHub OAuth."""
    s = get_settings()
    if s.is_production or not s.dev_login_email:
        raise HTTPException(404)
    return _login(request, db, s.dev_login_email, "Dev User", "dev")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
