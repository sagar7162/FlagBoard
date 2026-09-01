"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routers.auth_router import router as auth_router
from app.routers.evaluate_router import router as evaluate_router
from app.routers.flags_router import router as flags_router
from app.routers.orgs_router import router as orgs_router
from app.routers.ws_router import router as ws_router


app = FastAPI(title="FlagBoard")
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(flags_router)
app.include_router(evaluate_router)
app.include_router(ws_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return the service health status."""

    return {"status": "ok"}
