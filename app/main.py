"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routers.auth_router import router as auth_router


app = FastAPI(title="FlagBoard")
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return the service health status."""

    return {"status": "ok"}
