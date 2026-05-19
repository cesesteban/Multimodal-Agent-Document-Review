from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and validated strictly using Pydantic v2.
    All properties are named in English according to global style guidelines.
    """
    PROJECT_NAME: str = "LegalMove API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # API key security layer (Optional: set to enable token authorization, leave blank to disable)
    API_KEY: Optional[str] = None
    
    # LLM Provider Configuration
    OPENAI_API_KEY: SecretStr = SecretStr("mock-key-please-configure-in-env")
    OPENAI_MODEL_NAME: str = "gpt-4o"
    
    # Langfuse Telemetry and Observability Configuration
    LANGFUSE_PUBLIC_KEY: str = "mock-key-please-configure-in-env"
    LANGFUSE_SECRET_KEY: SecretStr = SecretStr("mock-key-please-configure-in-env")
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    # API Protection Configurations
    ALLOWED_CORS_ORIGINS: str = "*"
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Singleton settings instance initialized at application startup
settings = Settings()
