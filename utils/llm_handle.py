import asyncio
import functools
import json
from typing import AsyncGenerator

from requests import Session
from sqlalchemy import func
from models.chat import Conversation, Message
from prompts.prompts import get_prompt
from langchain.chat_models import init_chat_model
import os

# 模型初始化（延迟加载）
@functools.lru_cache(maxsize=1)
def _get_cached_llm_model():
    """初始化并缓存大语言模型实例"""


    
    print("初始化LLM模型")
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    
    model = init_chat_model(
        model="deepseek-chat",
        model_provider="deepseek",
        api_key=api_key,
        temperature=0.7,
        timeout=30,  # 添加超时
        max_retries=2  # 添加重试
    )
    return model

async def call_llm_model(prompt: str) -> AsyncGenerator[str, None]:
    """异步调用LLM模型并流式返回token（优化后）"""
    model = _get_cached_llm_model()
    full_response = ""
    
    try:
        # 添加超时控制
        async with asyncio.timeout(180):  # 总超时

            async for token in model.astream(prompt):  
                yield token.content
                full_response += token.content
                # 控制速率
                await asyncio.sleep(0.001)
                
    except asyncio.TimeoutError:
        yield "[错误：生成响应超时]"
        import logging
        logging.warning(f"LLM生成超时，prompt长度: {len(prompt)}")
    except Exception as e:
        yield f"[错误：生成失败 - {str(e)}]"
        import logging
        logging.error(f"LLM调用异常: {e}", exc_info=True)
    finally:
        # 可选：记录完整响应（用于分析或调试）
        if full_response:
            import logging
            logging.debug(f"完整响应长度: {len(full_response)}")


async def generate_response(request, prompt, conversation_id, is_new_conversation, message, db):
    ai_response = ""
    full_response_saved = False
    
    try:
        words = call_llm_model(prompt)
        async for token in words:
            # 检查客户端是否断开连接
            if await request.is_disconnected():
                print("客户端已断开连接")
                break
                
            ai_response += token
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0.02)
    except GeneratorExit:
        # 处理客户端断开连接
        print("流式响应被中断")
    finally:


    
        # 保存响应
        print(f"AI响应结束，长度: {ai_response}")

        if ai_response and not full_response_saved:
            await save_ai_response(ai_response, conversation_id, db)
            full_response_saved = True
  
            yield "data: [DONE]\n\n"
        if is_new_conversation:
            await generate_and_update_title(message, conversation_id, db)

async def save_ai_response(content, conversation_id, db: Session):
    """保存AI响应到数据库"""
    if content:
        ai_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content
        )
        db.add(ai_message)
        try:
            db.commit()
            print("保存AI消息成功")
        except Exception as e:
            db.rollback()
            print(f"保存消息失败: {e}")
        
        # 更新对话时间
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation:
            conversation.updated_at = func.now()
            try:
                db.commit()
            except:
                db.rollback()
    

async def generate_and_update_title(user_message: str, conversation_id: str, db: Session):
    """异步生成并更新对话标题"""
    try:
        title_prompt = get_prompt(scenario="title_generation", question=user_message)
        # 注意：call_llm_model 现在是异步生成器
        title_tokens = []
        async for token in call_llm_model(title_prompt):
            title_tokens.append(token)
        
        title_str = ''.join(title_tokens)
        # 清理标题
        import re
        title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\s]', '', title_str).strip()
        
        if len(title) > 10:
            title = title[:10] + "..."
        
        # 获取对话实例
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        # 更新数据库
        conversation.title = title
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # logger.info(f"对话标题已更新: {title}")
    except Exception as e:
        # logger.error(f"生成标题失败: {e}")
        # 失败时设置默认标题
        conversation.title = user_message[:20] + "..."
        db.commit()