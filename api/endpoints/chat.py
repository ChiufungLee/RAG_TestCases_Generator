from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging

from models.database import get_db
from prompts.prompts import get_prompt
from services import knowlege_service
from services.chat_service import ChatService
from utils.data_handle import convert_table_to_csv, extract_table_from_markdown
from utils.llm_handle import generate_response
from utils.retriever import get_rag_retriever_by_kb

app = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    username = request.session.get("username")
    if username is None:
        return templates.TemplateResponse("login.html", {"request": request, "error": "用户会话已失效，请重新登录"})
    return templates.TemplateResponse("index.html", {"request": request, "username": username})


@app.get("/api/history")
async def get_history(request: Request, scenario: str, knowledge_base_id: str, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    conversation_groups = await ChatService.get_conversation_groups(user_id, scenario, knowledge_base_id, db)
    return {"groups": conversation_groups}


@app.get("/api/conversation/{conversation_id}")
async def get_conversation(
    request: Request,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    conversation_messages = await ChatService.get_conversation_message(user_id, conversation_id, db)
    if not conversation_messages:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})

    return {"messages": conversation_messages}


@app.post("/api/conversation/new")
async def create_new_conversation(
    request: Request,
    scenario: str = Form(...),
    knowledge_base_id: str = Form(None),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    title = "新对话"
    new_conversation = await ChatService.create_new_conversation(
        user_id=user_id,
        title=title,
        scenario=scenario,
        knowledge_base_id=knowledge_base_id,
        db=db,
    )

    return {
        "conversation_id": new_conversation.id,
        "title": new_conversation.title,
    }


@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    data: dict,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    message = data.get("message")
    scenario = data.get("scenario")
    conversation_id = data.get("conversation_id")
    knowledge_base_id = data.get("knowledge_base_id") or None

    if not conversation_id:
        return JSONResponse(status_code=400, content={"error": "缺少会话ID"})

    conversation = await ChatService.get_conversation_info(conversation_id, db, user_id=user_id)
    if not conversation:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})

    is_new_conversation = conversation.title == "新对话"
    await ChatService.create_new_message(conversation_id, "user", message, db)

    history = await ChatService.get_conversation_history(conversation_id, db)

    context = ""
    if knowledge_base_id:
        retriever = await get_rag_retriever_by_kb(knowledge_base_id, db, user_id=user_id)
        if retriever:
            try:
                docs = await retriever.get_relevant_documents(message)
                context = "\n\n".join([doc.page_content for doc in docs])
                logger.info("从知识库 %s 检索到 %s 个相关文档", knowledge_base_id, len(docs))
            except Exception as e:
                logger.error("检索失败: %s", e, exc_info=True)
                context = ""

    knowledge_base = await knowlege_service.get_knowledge_base_by_id(kb_id=knowledge_base_id, db=db, user_id=user_id)
    knowledge_base_name = knowledge_base.name if knowledge_base else "无"

    prompt = get_prompt(
        scenario,
        context=context,
        history=history,
        question=message,
        knowledge_base_name=knowledge_base_name,
    )
    return StreamingResponse(
        generate_response(request, prompt, conversation_id, is_new_conversation, message, db),
        media_type="text/event-stream",
    )


@app.delete("/api/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    delete_result = await ChatService.delete_conversation(user_id, conversation_id, db)
    if not delete_result:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})

    return JSONResponse(content={"message": "对话删除成功"})


@app.post("/api/conversation/{conversation_id}/rename")
async def rename_conversation(
    conversation_id: str,
    request: Request,
    data: dict,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    new_title = data.get("title", "").strip()
    if not new_title:
        return JSONResponse(status_code=400, content={"error": "标题不能为空"})

    rename_result = await ChatService.rename_conversation(user_id, conversation_id, new_title, db)
    if not rename_result:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})

    return rename_result


@app.get("/api/export/testcases")
async def export_testcases(
    request: Request,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    ai_messages = await ChatService.get_conversation_ai_message(user_id, conversation_id, db)
    if not ai_messages:
        return JSONResponse(status_code=404, content={"error": "未找到测试用例"})

    latest_ai_message = ai_messages[0].content
    table_data = extract_table_from_markdown(latest_ai_message)
    if not table_data:
        return JSONResponse(status_code=404, content={"error": "未找到表格数据"})

    csv_data = convert_table_to_csv(table_data)
    headers = {
        "Content-Disposition": f"attachment; filename=testcases_{conversation_id}.csv",
        "Content-Type": "text/csv",
    }
    return Response(content=csv_data, headers=headers)
