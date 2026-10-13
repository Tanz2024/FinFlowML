from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://finflowml:finflowml@localhost:5432/finflowml"
    auth_secret: str = "local-development-only-change-me"
    access_token_minutes: int = 15
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
