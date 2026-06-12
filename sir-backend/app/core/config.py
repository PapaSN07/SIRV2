from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str

    # Redis
    redis_url: str

    # JWT
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Celery
    celery_broker_url: str
    celery_result_backend: str

    # App
    environment: str = "development"
    api_version: str = "v1"
    cors_origins: list[str] = ["http://localhost:4200"]

    # SMS
    sms_gateway_url: str = ""
    sms_gateway_api_key: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
