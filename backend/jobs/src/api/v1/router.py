"""Aggregates every version-1 router; mounted under ``/api/v1`` by the app factory."""

from fastapi import APIRouter, Depends

from src.api.v1 import auth, companies, contacts, health, jobs, preferences
from src.auth.dependencies import get_current_user

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(preferences.router, dependencies=[Depends(get_current_user)])
api_router.include_router(jobs.router, dependencies=[Depends(get_current_user)])
api_router.include_router(companies.router, dependencies=[Depends(get_current_user)])
api_router.include_router(contacts.router, dependencies=[Depends(get_current_user)])
