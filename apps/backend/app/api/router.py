"""Aggregate API routers."""

from fastapi import APIRouter

from app.api.routes import advisor, app_control, auth, cron, crops, farms, favourites, health, prices, records, weather

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(farms.router)
api_router.include_router(records.router)
api_router.include_router(favourites.router)
api_router.include_router(prices.router)
api_router.include_router(weather.router)
api_router.include_router(crops.router)
api_router.include_router(cron.router)
api_router.include_router(advisor.router)
api_router.include_router(app_control.router)
