import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, model_validator
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
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    
    # API Protection Configurations
    ALLOWED_CORS_ORIGINS: str = "*"
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def clean_quotes(self) -> "Settings":
        """
        Clean potential double/single quotes wrapping environment values from .env files
        and ensure values are stripped of external string literals.
        """
        if isinstance(self.LANGFUSE_PUBLIC_KEY, str):
            self.LANGFUSE_PUBLIC_KEY = self.LANGFUSE_PUBLIC_KEY.strip('"').strip("'")
        if isinstance(self.LANGFUSE_BASE_URL, str):
            self.LANGFUSE_BASE_URL = self.LANGFUSE_BASE_URL.strip('"').strip("'")
        if isinstance(self.API_KEY, str):
            self.API_KEY = self.API_KEY.strip('"').strip("'")
            
        if self.OPENAI_API_KEY:
            val = self.OPENAI_API_KEY.get_secret_value().strip('"').strip("'")
            self.OPENAI_API_KEY = SecretStr(val)
        if self.LANGFUSE_SECRET_KEY:
            val = self.LANGFUSE_SECRET_KEY.get_secret_value().strip('"').strip("'")
            self.LANGFUSE_SECRET_KEY = SecretStr(val)
            
        return self

# Singleton settings instance initialized at application startup
settings = Settings()

# Export config to os.environ so that third-party SDKs like Langfuse can read them automatically.
os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY.get_secret_value()
os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY.get_secret_value()
