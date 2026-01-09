# app/api/v1/api.py
from fastapi import APIRouter
# from api.endpoints import users, auth, chat

api_router = APIRouter()
# api_router.include_router(users.router, prefix="/users", tags=["用户"])
# api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
# api_router.include_router(chat.router, prefix="/chat", tags=["认证"])