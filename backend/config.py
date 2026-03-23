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
    webauthn_android_origin: str = ""

    # Email settings (Brevo API)
    brevo_api_key: str = ""
    email_from: str = ""
    email_from_name: str = "Privatregnskap.eu"

    # Bank integration settings
    frontend_url: str = "http://localhost:8002"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
