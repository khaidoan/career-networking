"""Aggregates every version-1 router; mounted under ``/api/v1`` by the app factory."""

from fastapi import APIRouter

from src.api.v1 import auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
