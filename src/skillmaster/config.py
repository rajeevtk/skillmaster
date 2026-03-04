from enum import Enum

from pydantic_settings import BaseSettings


class StorageMode(str, Enum):
    ENV = "env"  # Use bucket name from SKILLMASTER_GCS_BUCKET env var
    DB = "db"  # Multi-tenant: look up bucket per org/team from NeonDB


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    skillmaster_storage_mode: StorageMode = StorageMode.ENV
    skillmaster_gcs_bucket: str = "skillmaster-skills"
    skillmaster_gcs_project: str = ""
    neondb_url: str = ""
    skillmaster_port: int = 8080
    skillmaster_log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
