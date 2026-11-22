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
    GITHUB_TOKENS: Optional[str] = None  # Comma-separated list for token rotation
    JINA_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None

    # Multi-Provider AI Support (Groq, Cerebras, GitHub Models, SambaNova, Gemini, OpenRouter, OpenAI, Mistral, Anthropic)
    CEREBRAS_API_KEY: Optional[str] = None
    CEREBRAS_MODEL: str = "llama-3.3-70b"

    GITHUB_MODELS_TOKEN: Optional[str] = None
    GITHUB_MODELS_MODEL: str = "gpt-4o-mini"

    SAMBANOVA_API_KEY: Optional[str] = None
    SAMBANOVA_MODEL: str = "Meta-Llama-3.3-70B-Instruct"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "google/gemma-4-31b-it:free"

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-small-latest"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    # System 1: Fast Reflex Triage (Groq Fast Tier / Deterministic Anchors)
    ENABLE_SYSTEM1: bool = True
    SYSTEM1_ALLOW_CONTRADICTION: bool = False  # Keep triage contradiction off by default to prevent false negatives on partial chunks
    SYSTEM1_MODEL_PATH: Optional[str] = None
    SYSTEM1_MODEL_NAME: str = "qwen/qwen3.8-27b"  # Fast reflex model (Groq 8B / Qwen)
    SYSTEM1_ENTAILMENT_THRESHOLD: float = 0.70
    SYSTEM1_CONTRADICTION_THRESHOLD: float = 0.88

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
