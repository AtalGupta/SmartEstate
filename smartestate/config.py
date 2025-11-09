import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/smartestate", alias="DATABASE_URL")
    elasticsearch_url: str = Field(default="http://localhost:9200", alias="ELASTICSEARCH_URL")
    elasticsearch_index: str = Field(default="properties", alias="ELASTICSEARCH_INDEX")
    # Points to Kaggle working root (contains inference_production.py and a models/ folder)
    model_dir: str = Field(default="kaggle/working", alias="MODEL_DIR")
    ocr_langs: List[str] = Field(default_factory=lambda: ["en"], alias="OCR_LANGS")
    ocr_model_dir: str = Field(default="models/easyocr", alias="OCR_MODEL_DIR")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")


def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
