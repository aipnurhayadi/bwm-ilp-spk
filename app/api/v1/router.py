from fastapi import APIRouter

from app.api.v1.endpoints import scheduling, users

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(scheduling.router, prefix="/simulation", tags=["simulation"])
