# backend/app/config.py
"""Central configuration combining all settings from p4, p5, and p6."""
import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Identity
    APP_NAME: str = "Hifazat"
    APP_LABEL: str = "PROTOTYPE"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "PROTOTYPE"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./hifazat.db")

    # Security & JWT
    SECRET_KEY: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod-hifazat-2026"))
    JWT_SECRET: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod-hifazat-2026"))
    ALGORITHM: str = "HS256"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    JWT_EXPIRE_MINUTES: int = 480

    # Public API Key
    API_KEY: str = os.getenv("API_KEY", "hifazat-demo-key-2026")

    # AI Providers
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_FALLBACK: str = "gemini-1.5-flash"

    # AI Decision Routing Thresholds
    AUTO_HANDLE_MIN: float = 0.85
    ASK_MORE_PROOF_MIN: float = 0.60
    HIGH_RISK_KEYWORDS: List[str] = [
        "OTP", "PIN", "password", "send money", "urgent", "lottery",
        "Bait-ul-Maal", "BISP", "fee", "processing", "Raast", "JazzCash", "Easypaisa"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
