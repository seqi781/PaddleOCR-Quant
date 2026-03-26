from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="PaddleOCR-Quant", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    db_path: Path = Field(default=Path("./data/paddleocr_quant.db"), alias="DB_PATH")
    object_store_root: Path = Field(default=Path("./data/object_store"), alias="OBJECT_STORE_ROOT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


def get_settings() -> Settings:
    return Settings()
