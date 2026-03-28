import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api.api_v1 import api_router
from api.endpoints import auth, chat, knowledg_api as kb
from models.database import init_db

load_dotenv()

app = FastAPI()

session_secret = os.getenv("SESSION_SECRET_KEY", "dev-session-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=session_secret)

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def on_startup():
    # 初始化数据库
    init_db()


app.include_router(api_router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(chat.app)
app.include_router(kb.app)
