"""Central configuration loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Elasticsearch
    es_host: str = "http://localhost:9200"
    es_index: str = "cars"
    es_user: str = ""
    es_password: str = ""

    # Local Ollama settings for Timebox 3 RAG / LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    # Legacy Anthropic support (optional)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # API
    cors_origins: str = "*"


settings = Settings()
