"""
Central app configuration.

Everything here is loaded from environment variables (see .env.example).
Nothing here should be hardcoded secrets — this file just defines
WHAT settings exist and their defaults; actual values come from .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM provider config — abstracted so Ollama (free, self-hosted) and
    # Groq (free-tier hosted API, much faster on constrained hardware)
    # can be swapped via config alone, no code changes (see Section 8).
    model_provider: str = "ollama"  # "ollama" or "groq"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    # MCP server location (the enrichment tool server)
    mcp_server_url: str = "http://localhost:8100"

    app_env: str = "development"
    log_level: str = "INFO"


# Single shared settings instance, imported wherever config is needed.
settings = Settings()
