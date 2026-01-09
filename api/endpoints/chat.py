from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from prompts.prompts import get_prompt
from services.chat_service import ChatService
from sqlalchemy.orm import Session
from models.database import get_db
from utils.data_handle import convert_table_to_csv, extract_table_from_markdown
from utils.llm_handle import generate_response
from utils.retriever import get_rag_retriever

app = APIRouter()
templates = Jinja2Templates(directory="templates")

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    username = request.session.get("username")
    if username is None:
        return templates.TemplateResponse("login.html",{"request": request, "error": "用户会话已失效，请重新登录"})
    return templates.TemplateResponse("index.html",{"request": request, "username": username})


# 获取对话分组记录
@app.get("/api/history")
async def get_history(request: Request, scenario: str, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    conversation_groups = await ChatService.get_conversation_groups(user_id, scenario, db)
    return {"groups": conversation_groups}


# 获取对话内容
@app.get("/api/conversation/{conversation_id}")
async def get_conversation(
    request: Request, 
    conversation_id: str, 
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    
    conversation_messages = await ChatService.get_conversation_message(conversation_id, db)

    if not conversation_messages:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})
    
    return {
        "messages": conversation_messages
    }


# 创建新对话
@app.post("/api/conversation/new")
async def create_new_conversation(
    request: Request,
    scenario: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    
    new_conversation = await ChatService.create_new_conversation(user_id, scenario, db)
    
    return {
        "conversation_id": new_conversation.id,
        "title": new_conversation.title
    }

# 聊天接口，流式响应
@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    data: dict,  
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    
    message = data.get("message")
    scenario = data.get("scenario")
    conversation_id = data.get("conversation_id")
    
    is_new_conversation = False
    if not conversation_id:
        new_conversation = await ChatService.create_new_conversation(user_id, "新对话", scenario, db)
        conversation_id = new_conversation.id
        is_new_conversation = True
    
    user_message = await ChatService.create_new_message(conversation_id, "user", message, db)

    
    # 获取对话历史
    history = await ChatService.get_conversation_history(conversation_id, db)
    
    context = ""
    # 对于需要RAG的场景，获取上下文
    if scenario in ["运维助手", "产品手册"]:
        retriever = get_rag_retriever(scenario)
        if retriever:
            docs = await retriever.get_relevant_documents(message)
            context = "\n\n".join([doc.page_content for doc in docs])
            # print(f"检索到的内容是：{context}")
    
    # 生成对话提示
    prompt = get_prompt(
        scenario,
        context=context,
        history=history,
        question=message
    )

    # 返回流式响应
    return StreamingResponse(generate_response(request,prompt,conversation_id,is_new_conversation,message,db), media_type="text/event-stream")


# 删除对话
@app.delete("/api/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    
    delete_result = await ChatService.delete_conversation(user_id, conversation_id, db)

    if not delete_result["success"]:
        return JSONResponse(status_code=400, content={"error": "删除对话失败"})
        
    return JSONResponse(content={"message": "对话删除成功"})

    
# 重命名对话
@app.post("/api/conversation/{conversation_id}/rename")
async def rename_conversation(
    conversation_id: str,
    request: Request,
    data: dict,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    
    new_title = data.get("title", "").strip()
    if not new_title:
        return JSONResponse(status_code=400, content={"error": "标题不能为空"})
    
    rename_result = await ChatService.rename_conversation(user_id, conversation_id, new_title, db)
    
    return rename_result

# 导出测试用例为CSV
@app.get("/api/export/testcases")
async def export_testcases(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    ai_messages = await ChatService.get_conversation_ai_message(conversation_id, db)
    
    if not ai_messages:
        return JSONResponse(status_code=404, content={"error": "未找到测试用例"})
    
    # 提取最新AI消息中的表格
    latest_ai_message = ai_messages[0].content
    table_data = extract_table_from_markdown(latest_ai_message)
    
    if not table_data:
        return JSONResponse(status_code=404, content={"error": "未找到表格数据"})
    
    # 转换为CSV格式
    csv_data = convert_table_to_csv(table_data)
    
    # 创建响应
    headers = {
        "Content-Disposition": f"attachment; filename=testcases_{conversation_id}.csv",
        "Content-Type": "text/csv"
    }
    return Response(content=csv_data, headers=headers)


