# app/api/v1/api.py
from fastapi import APIRouter
from api.endpoints import func
# from api.endpoints import users, auth, chat
from api.endpoints import knowledg_api as kn

api_router = APIRouter()
# api_router.include_router(users.router, prefix="/users", tags=["用户"])
# api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(func.router, prefix="/func", tags=["功能"])
# api_router.include_router(kn.app, tags=["知识库"])