from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://finflowml:finflowml@localhost:5432/finflowml"
    auth_secret: str = "local-development-only-change-me"
    access_token_minutes: int = 15
    upload_root: str = "./data/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    extraction_max_retries: int = 3
    extraction_lease_seconds: int = 300
    worker_version: str = "stage5c-local-1"
    model_id: str = "Qwen/Qwen3-4B-Instruct-2507"
    model_revision: str = "cdbee75f17c01a7cc42f958dc650907174af0554"
    adapter_path: str = ""
    mock_extraction: bool = False
    environment: str = "local"
    cors_origins: str = ""
    rate_limit_per_minute: int = 60
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def require_secure_non_local_secret(self):
        insecure = {"", "local-development-only-change-me", "replace-with-at-least-32-random-characters"}
        if self.environment not in {"local", "test"} and (self.auth_secret in insecure or len(self.auth_secret) < 32):
            raise ValueError("AUTH_SECRET must be a random value of at least 32 characters outside local/test")
        if self.environment not in {"local", "test", "mock"} and self.mock_extraction:
            raise ValueError("FINFLOW_MOCK_EXTRACTION must be false outside local/test/mock")
        return self


settings = Settings()
