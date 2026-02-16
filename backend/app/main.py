from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as notes_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="AI Engineering Notes API", version="0.1.0")

origins = [origin.strip() for origin in settings.backend_cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
