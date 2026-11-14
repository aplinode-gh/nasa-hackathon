from fastapi import FastAPI

from app.routers.forecast import router as forecast_router
from app.routers.rotations import router as rotations_router

app = FastAPI(title="Agropioo Rotation Model API", version="0.0.0")
app.include_router(rotations_router)
app.include_router(forecast_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
