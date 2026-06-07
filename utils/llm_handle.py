import asyncio
import functools
import json
import logging
from typing import AsyncGenerator, List, Union

from langchain_core.messages import BaseMessage, HumanMessage

from config import get_deepseek_api_key

from sqlalchemy import func
from sqlalchemy.orm import Session

from langchain.chat_models import init_chat_model
from models.chat import Conversation, Message
from prompts.prompts import get_prompt, get_scenario_temperature

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _get_cached_llm_model():
    """初始化并缓存大语言模型实例"""
    api_key = get_deepseek_api_key()

    model = init_chat_model(
        model="deepseek-chat",
        model_provider="deepseek",
        api_key=api_key,
        temperature=0.7,
        timeout=30,
        max_retries=2,
    )
    return model



def reset_llm_state():
    _get_cached_llm_model.cache_clear()


async def call_llm_model(prompt: Union[str, List[BaseMessage]], temperature: float | None = None) -> AsyncGenerator[str, None]:
    """异步调用LLM模型并流式返回token"""
    model = _get_cached_llm_model()
    if temperature is not None:
        model = model.bind(temperature=temperature)
    full_response = ""

    llm_input: Union[str, List[BaseMessage]]
    if isinstance(prompt, str):
        llm_input = [HumanMessage(content=prompt)]
    else:
        llm_input = prompt

    try:
        aiter = model.astream(llm_input).__aiter__()
        while True:
            try:
                token = await asyncio.wait_for(aiter.__anext__(), timeout=180)
            except StopAsyncIteration:
                break
            yield token.content
            full_response += token.content

    except (asyncio.TimeoutError, asyncio.CancelledError):
        yield "[错误：生成响应超时]"
        logger.warning("LLM生成超时，prompt长度: %s", len(prompt))
    except Exception as e:
        yield f"[错误：生成失败 - {str(e)}]"
        logger.error("LLM调用异常: %s", e, exc_info=True)
    finally:
        if full_response:
            logger.debug("完整响应长度: %s", len(full_response))


async def generate_response(request, prompt: Union[str, List[BaseMessage]], conversation_id, is_new_conversation, message, db, temperature: float | None = None):
    ai_response = ""
    full_response_saved = False
    completed = False

    try:
        words = call_llm_model(prompt, temperature=temperature)
        async for token in words:
            if await request.is_disconnected():
                logger.info("客户端已断开连接")
                return

            ai_response += token
            yield f"data: {json.dumps({'token': token})}\n\n"
        completed = True
    except GeneratorExit:
        logger.info("流式响应被中断")
    finally:
        logger.info("AI响应结束，长度: %s", len(ai_response))

        if completed and ai_response and not full_response_saved:
            await save_ai_response(ai_response, conversation_id, db)
            full_response_saved = True

        if completed and is_new_conversation:
            conversation_title = await generate_and_update_title(message, conversation_id, db)
            if conversation_title:
                yield f"data: {json.dumps({'conversation_title': conversation_title})}\n\n"

        if completed:
            yield "data: [DONE]\n\n"


async def save_ai_response(content, conversation_id, db: Session):
    """保存AI响应到数据库"""
    if not content:
        return

    ai_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
    )
    db.add(ai_message)
    try:
        db.commit()
        logger.info("保存AI消息成功")
    except Exception as e:
        db.rollback()
        logger.error("保存消息失败: %s", e, exc_info=True)
        return

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.updated_at = func.now()
        try:
            db.commit()
        except Exception:
            db.rollback()


async def generate_and_update_title(user_message: str, conversation_id: str, db: Session):
    """异步生成并更新对话标题"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        logger.warning("未找到对话，无法生成标题: %s", conversation_id)
        return None

    fallback_title = (user_message[:20] + "...") if len(user_message) > 20 else user_message

    try:
        title_prompt = get_prompt(scenario="title_generation", question=user_message)
        title_temperature = get_scenario_temperature("title_generation")
        title_tokens = []
        async for token in call_llm_model(title_prompt, temperature=title_temperature):
            title_tokens.append(token)

        title_str = "".join(title_tokens)
        import re

        title = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5\s]", "", title_str).strip() or fallback_title

        if len(title) > 30:
            title = title[:30] + "..."

        conversation.title = title
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return title
    except Exception as e:
        logger.error("生成标题失败: %s", e, exc_info=True)
        conversation.title = fallback_title
        db.add(conversation)
        db.commit()
        return fallback_title
