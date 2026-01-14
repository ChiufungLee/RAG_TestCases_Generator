from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import secrets
from models.database import init_db
from api.api_v1 import api_router
from api.endpoints import auth, chat, knowledg_api as kb

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32))

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")


# 初始化数据库
init_db()

app.include_router(api_router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(chat.app)
app.include_router(kb.app)
