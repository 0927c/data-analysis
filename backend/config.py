from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./backend/data/complaints.db"

    # Auth
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRY_DAYS: int = 7
    AUTH_MODE: str = "local"

    # IAM
    IAM_ISSUER: str = ""
    IAM_CLIENT_ID: str = ""
    IAM_CLIENT_SECRET: str = ""
    IAM_REDIRECT_URI: str = ""

    # LLM
    LLM_PROVIDER: str = "claude"
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6-20250514"
    LLM_API_KEY: str = ""
    LLM_OPENAI_BASE_URL: str = "http://localhost:8080/v1"
    LLM_OPENAI_MODEL: str = "qwen2.5-7b-instruct"
    LLM_OPENAI_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Data Source
    TICKET_EXCEL_PATH: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
