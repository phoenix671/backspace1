from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str = Field(min_length=1)
    DB_PASSWORD: str
    SECRET_KEY: str = Field(min_length=1)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    FACULTY_DOMAIN: str
    TEACHER_DOMAIN: str
    STUDENT_DOMAIN: str
    USE_REAL_AI: bool = False
    STORAGE_DIR: str = "storage"

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

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

