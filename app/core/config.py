from pydantic_settings import BaseSettings,SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    APP_NAME: str = "DevPilot"
    ENVIRONMENT: str = "developement"
    GROQ_MODEL: str =  "openai/gpt-oss-120b"
    GROQ_API_KEY: SecretStr

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
settings = Settings()