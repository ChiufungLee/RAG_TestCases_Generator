from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from prompts.prompts import get_prompt
from services import knowlege_service
from services.chat_service import ChatService
from sqlalchemy.orm import Session
from models.database import get_db
from utils.data_handle import convert_table_to_csv, extract_table_from_markdown
from utils.llm_handle import generate_response, generate_and_update_title
from utils.retriever import get_rag_retriever, get_rag_retriever_by_kb
import logging

app = APIRouter()
templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    username = request.session.get("username")
    if username is None:
        return templates.TemplateResponse("login.html",{"request": request, "error": "用户会话已失效，请重新登录"})
    return templates.TemplateResponse("index.html",{"request": request, "username": username})


# 获取对话分组记录
@app.get("/api/history")
async def get_history(request: Request, scenario: str, knowledge_base_id: str, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    conversation_groups = await ChatService.get_conversation_groups(user_id, scenario, knowledge_base_id, db)
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
    knowledge_base_id: str = Form(None),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    
    title = '新对话'
    new_conversation = await ChatService.create_new_conversation(user_id = user_id, title = title, scenario = scenario, knowledge_base_id = knowledge_base_id, db = db)
    
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
    knowledge_base_id = data.get("knowledge_base_id")
    
    is_new_conversation = False
    # if not conversation_id:
    #     new_conversation = await ChatService.create_new_conversation(user_id, scenario, scenario, knowledge_base_id, db)
    #     conversation_id = new_conversation.id
    #     is_new_conversation = True
    
    conversation = await ChatService.get_conversation_info(conversation_id,db)
    print(f"conversation{conversation.title}")
    if conversation.title == "新对话":
        is_new_conversation = True
        generate_and_update_title(user_message=message, conversation_id=conversation_id, db=db)
        print(f"conversation{conversation}")
    await ChatService.create_new_message(conversation_id, "user", message, db)

    
    # 获取对话历史
    history = await ChatService.get_conversation_history(conversation_id, db)
    
    # 获取检索器并检索相关文档
    context = ""
    if knowledge_base_id:
        retriever = await get_rag_retriever_by_kb(knowledge_base_id, db)
        if retriever:
            try:
                docs = await retriever.get_relevant_documents(message)
                context = "\n\n".join([doc.page_content for doc in docs])
                logger.info(f"从知识库 {knowledge_base_id} 检索到 {len(docs)} 个相关文档")
            except Exception as e:
                logger.error(f"检索失败: {e}")
                context = ""
    
    knowledge_base = await knowlege_service.get_knowledge_base_by_id(kb_id=knowledge_base_id, db=db)
    if not knowledge_base:
        knowledge_base_name = "无"
    else:
        knowledge_base_name = knowledge_base.name

    # 生成对话提示
    prompt = get_prompt(
        scenario,
        context=context,
        history=history,
        question=message,
        knowledge_base_name=knowledge_base_name

    )
    print(f"最终传给模型的prompt是：{prompt}")
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


