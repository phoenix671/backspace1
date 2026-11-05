from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.errors import register_error_handlers

# Create required storage folders before creating the app
(settings.storage_path / "uploads").mkdir(parents=True, exist_ok=True)
(settings.storage_path / "attempts").mkdir(parents=True, exist_ok=True)
(settings.storage_path / "gifs").mkdir(parents=True, exist_ok=True)
settings.private_books_path.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Neura API", lifespan=lifespan)

register_error_handlers(app)

app.mount("/files", StaticFiles(directory=settings.storage_path), name="files")


@app.get("/health")
def health():
    return {"status": "ok"}

