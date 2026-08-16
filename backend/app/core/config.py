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
    GROQ_MODEL: str = "qwen/qwen3.8-27b"

    # External Data Sources
    GITHUB_TOKEN: Optional[str] = None

    # Additional AI Providers (Fallback & Task Division)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "nvidia/nemotron-3.5-lightning:free"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-flash-latest"

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
