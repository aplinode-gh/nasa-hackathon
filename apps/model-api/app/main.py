from fastapi import FastAPI

from app.routers.detect import router as detect_router
from app.routers.forecast import router as forecast_router
from app.routers.rotations import router as rotations_router
from app.routers.vision import router as vision_router

app = FastAPI(title="AgroAI Model API", version="0.1.0")
app.include_router(rotations_router)
app.include_router(forecast_router)
app.include_router(detect_router)  # simple: POST /detect, GET /diseases
app.include_router(vision_router)  # detailed: /vision/*


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
