"""Central configuration loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Elasticsearch
    es_host: str = "http://localhost:9200"
    es_index: str = "cars"
    es_user: str = ""
    es_password: str = ""

    # LLM (Jerry's NL spike / Timebox 3)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # API
    cors_origins: str = "*"


settings = Settings()
