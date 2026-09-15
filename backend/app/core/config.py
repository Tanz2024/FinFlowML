from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://finflowml:finflowml@localhost:5432/finflowml"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
