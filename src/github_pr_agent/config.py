"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str
    github_token: str

    # Defaults
    default_repo: str | None = None  # e.g., "owner/repo"
    claude_model: str = "claude-sonnet-4-20250514"
    max_tool_iterations: int = 10


def get_settings() -> Settings:
    """Load and return settings. Raises ValidationError if required vars missing."""
    return Settings()