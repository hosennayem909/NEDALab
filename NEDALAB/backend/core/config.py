from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./nedalab.db"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: str = "null,http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500"

    @field_validator("DATABASE_URL", "JWT_SECRET")
    @classmethod
    def validate_required_fields(cls, v: str, info):
        value = (v or "").strip()
        if not value:
            raise ValueError(f"{info.field_name} cannot be empty")
        return value

    @property
    def cors_list(self):
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
