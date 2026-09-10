from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "doyoularp"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    FRONTEND_URL: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./larp_checker.db"

    # AI Provider: Groq
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # External Data Sources
    GITHUB_TOKEN: Optional[str] = None

    # Multi-Provider AI Support (Groq, OpenRouter, Gemini, OpenAI, Mistral, Anthropic)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "google/gemma-4-31b-it:free"

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-small-latest"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    # Scoring & Intensity
    ROAST_INTENSITY: int = 3  # 0 to 4

    # Security & Limits
    MAX_PDF_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    REQUEST_TIMEOUT_SECONDS: int = 15
    MAX_CONCURRENT_GITHUB_REQS: int = 5

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
