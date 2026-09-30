from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    env: str = "development"  # "production" enables secure cookies and disables dev login
    app_url: str = "http://localhost:5173"
    timezone: str = "America/New_York"  # used for "today" in balance snapshots and month boundaries

    database_url: str = "sqlite:///./dev.db"

    session_secret: str
    encryption_key: str  # Fernet key for Plaid access tokens
    allowed_emails: str = ""  # comma-separated
    cron_secret: str = ""
    dev_login_email: str = ""  # development only: enables /auth/dev-login

    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox | production
    plaid_redirect_uri: str = ""  # must be registered in the Plaid Dashboard before setting
    plaid_webhook_url: str = ""  # defaults to APP_URL/api/v1/plaid/webhook when APP_URL is public

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def allowed_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()}

    @property
    def webhook_url(self) -> str | None:
        if self.plaid_webhook_url:
            return self.plaid_webhook_url
        if "localhost" in self.app_url or "127.0.0.1" in self.app_url:
            return None  # Plaid can't reach localhost; use a tunnel and set PLAID_WEBHOOK_URL
        return f"{self.app_url}/api/v1/plaid/webhook"

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Neon/Render hand out postgres:// or postgresql:// URLs; use the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
