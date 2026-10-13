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
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
