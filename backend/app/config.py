from pathlib import Path
from typing import Any, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "neura"
    DB_USER: str = Field(default="root", min_length=1)
    DB_PASSWORD: str = ""
    SECRET_KEY: str = Field(default="neura-dev-secret-key-change-me", min_length=1)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    FACULTY_DOMAIN: str = "faculty.class.com"
    TEACHER_DOMAIN: str = "teacher.class.com"
    STUDENT_DOMAIN: str = "student.class.com"
    USE_REAL_AI: bool = False
    GEMINI_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    STORAGE_DIR: str = "storage"

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    @field_validator(
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "SECRET_KEY",
        "JWT_ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "FACULTY_DOMAIN",
        "TEACHER_DOMAIN",
        "STUDENT_DOMAIN",
        "USE_REAL_AI",
        "STORAGE_DIR",
        mode="before",
    )
    @classmethod
    def _empty_str_to_default(cls, v: Any, info: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            field_info = cls.model_fields.get(info.field_name)
            if field_info is not None:
                return field_info.default
        return v

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query={"charset": "utf8mb4"},
        )

    @property
    def storage_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / self.STORAGE_DIR

    @property
    def private_books_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "private_storage" / "books"


settings = Settings()
