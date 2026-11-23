from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    APP_NAME: str = "DevPilot"
    ENVIRONMENT: str = "development"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_API_KEY: SecretStr
    OPENROUTER_API_KEY: SecretStr

    # Sandbox execution
    SANDBOX_IMAGE: str = "devpilot-sandbox:py312"
    USE_PREBUILT_IMAGE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()