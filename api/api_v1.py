from fastapi import APIRouter

from api.endpoints import func

api_router = APIRouter()
api_router.include_router(func.router, tags=["功能"])
