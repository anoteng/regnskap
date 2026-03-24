from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours

    # WebAuthn / Passkey settings
    rp_id: str = "localhost"
    rp_name: str = "Privatregnskap.eu"
    # Comma-separated list of allowed Android origins (release and/or debug)
    webauthn_android_origins: str = ""

    # Email settings (Brevo API)
    brevo_api_key: str = ""
    email_from: str = ""
    email_from_name: str = "Privatregnskap.eu"

    # AI / OCR (Anthropic) — only used for Premium subscribers
    anthropic_api_key: str = ""

    # Internal API key for scheduled tasks (nightly bank sync)
    sync_api_key: str = ""

    # Bank integration settings
    frontend_url: str = "http://localhost:8002"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
