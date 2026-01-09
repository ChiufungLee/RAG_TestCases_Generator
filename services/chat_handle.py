# services/chat_handler.py
import asyncio
import json
import re
from typing import AsyncGenerator, Optional
from sqlalchemy.orm import Session

class ChatHandler:
    def __init__(self, db: Session, user_id: int, message: str, scenario: str, conversation_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self.message = message
        self.scenario = scenario
        self.conversation_id = conversation_id
        self.ai_response = ""
        self.new_conversation = None
        
    async def process(self) -> AsyncGenerator[str, None]:
        """处理聊天消息的主流程"""
        try:
            # 1. 确保对话存在
            await self._ensure_conversation()
            # 2. 保存用户消息
            await self._save_user_message()
            # 3. 获取响应并流式返回
            async for event in self._generate_stream_response():
                yield event
        except Exception as e:
            # 异常时发送错误事件
            yield self._create_error_event(e)
        finally:
            # 确保资源清理
            await self._cleanup()
    
    async def _ensure_conversation(self):
        """确保有可用的对话ID"""
        if not self.conversation_id:
            self.new_conversation = await ChatService.create_new_conversation(
                self.user_id, "新对话", self.scenario, self.db
            )
            self.conversation_id = self.new_conversation.id
    
    async def _save_user_message(self):
        """保存用户消息到数据库"""
        await ChatService.create_new_message(self.conversation_id, "user", self.message, self.db)
    
    async def _generate_stream_response(self) -> AsyncGenerator[str, None]:
        """生成流式响应"""
        # 获取对话历史和上下文
        history = await ChatService.get_conversation_history(self.conversation_id, self.db)
        context = await self._get_rag_context() if self.scenario in ["运维助手", "产品手册"] else ""
        
        # 构建提示词
        prompt = get_prompt(self.scenario, context=context, history=history, question=self.message)
        
        # 流式调用LLM
        try:
            words = call_llm_model(prompt)  # 假设已改为异步函数
            async for token in words:  # 需要 call_llm_model 支持异步迭代
                self.ai_response += token
                yield self._create_token_event(token)
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            # 处理客户端断开
            print("流式响应被客户端中断")
            raise
    
    async def _get_rag_context(self) -> str:
        """异步获取RAG上下文"""
        retriever = get_rag_retriever(self.scenario)
        if not retriever:
            return ""
        # 假设 retriever.get_relevant_documents 是异步的
        docs = await retriever.aget_relevant_documents(self.message)  # 注意异步方法
        return "\n\n".join([doc.page_content for doc in docs])
    
    def _create_token_event(self, token: str) -> str:
        """创建SSE令牌事件"""
        return f"data: {json.dumps({'token': token})}\n\n"
    
    def _create_final_event(self) -> str:
        """创建最终完成事件"""
        event_data = {'full_response': self.ai_response, 'conversation_id': self.conversation_id}
        if self.new_conversation:
            event_data.update({
                'new_conversation_id': self.conversation_id,
                'conversation_title': self.new_conversation.title
            })
        return f"data: {json.dumps(event_data)}\n\n"
    
    async def _save_and_generate_title(self):
        """保存AI响应并生成对话标题"""
        # 保存AI响应
        save_ai_response(self.ai_response, self.conversation_id, self.db)
        
        # 如果是新对话，生成标题
        if self.new_conversation:
            title_prompt = get_prompt("标题生成", question=self.message)
            title_str = ''.join(call_llm_model(title_prompt))  # 注意：应改为异步
            title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\s]', '', title_str).strip()
            
            if len(title) > 10:
                title = title[:10] + "..."
            
            self.new_conversation.title = title
            self.db.add(self.new_conversation)
            self.db.commit()
            self.db.refresh(self.new_conversation)
    
    def _create_error_event(self, error: Exception) -> str:
        """创建错误事件"""
        return f"data: {json.dumps({'error': str(error)})}\n\n"
    
    async def _cleanup(self):
        """清理资源：保存响应、生成标题、发送完成事件"""
        try:
            if self.ai_response:
                await self._save_and_generate_title()
        finally:
            # 即使保存失败，也发送完成事件
            yield self._create_final_event()
            yield "data: [DONE]\n\n"