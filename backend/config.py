from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # WebAuthn / Passkey settings
    rp_id: str = "localhost"
    rp_name: str = "Regnskap"

    # SMTP settings for password reset emails
    smtp_host: str = "smtp.altibox.no"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Bank integration settings
    frontend_url: str = "http://localhost:8002"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
