from fastapi import Depends,Request, Form, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from models.database import get_db
from fastapi import APIRouter, Request, Form, Depends, status
from services.auth_service import AuthService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# 注册页面
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_user(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
    ):

    register_result = await AuthService.create_user(db, username, password)
    if not register_result["success"]:
        return templates.TemplateResponse(
            "register.html", 
            {"request": request, "error": register_result["error"]},
            status_code=status.HTTP_400_BAD_REQUEST
        )


    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return response

# 用户登录
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    username = request.session.get("username")
    if username is None:
        return templates.TemplateResponse("login.html",{"request": request, "error": "用户会话已失效，请重新登录"})
    return RedirectResponse(url="/chat", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/login")
async def login_user(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):

    # db_user = db.query(User).filter(User.username == username).first()
    auth_result = await AuthService.login_user(db, username, password)
    if not auth_result["success"]:
        # raise HTTPException(status_code=401, detail="Invalid credentials",)
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "用户名或密码错误"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    # 登录成功，设置 session
    request.session["user_id"] = auth_result["user_id"]
    request.session["username"] = auth_result["username"]
    request.session["login_time"] = auth_result["login_time"]

    # return {"message": "Login successful", "user_id": db_user.id}
    response = RedirectResponse(url="/chat", status_code=status.HTTP_303_SEE_OTHER)
    return response

@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    request.session.clear()
    # return templates.TemplateResponse("login.html",{"request": request, })
    return RedirectResponse(url="/login?logout=true", status_code=status.HTTP_303_SEE_OTHER)