from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/func_main")
async def func_main(request: Request):
    username = request.session.get("username")
    if username is None:
        # return templates.TemplateResponse("login.html",{"request": request, "error": "用户会话已失效，请重新登录"})
        # 重定向到登录页面
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return response
    return templates.TemplateResponse("func_main.html",{"request": request, "username": username})
