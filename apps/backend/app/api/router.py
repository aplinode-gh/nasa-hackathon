"""Aggregate API routers."""

from fastapi import APIRouter

from app.api.routes import (
    advisor,
    app_control,
    auth,
    cron,
    crops,
    detect,
    farms,
    favourites,
    health,
    pest,
    prices,
    profit_loss,
    records,
    weather,
)

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
api_router.include_router(profit_loss.router)
api_router.include_router(detect.router)
api_router.include_router(pest.router)
