
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.chat import Conversation, Message
from sqlalchemy import desc
from fastapi.responses import JSONResponse

from models.knowledge_models import KnowledgeBase



class ChatService:
    
    @staticmethod
    async def get_conversation_groups(user_id: int, scenario: str, knowledge_base_id: str, db: Session):
        # 获取用户的对话历史记录的逻辑
        
        today = datetime.now().date()
        three_days_ago = today - timedelta(days=3)
        one_week_ago = today - timedelta(days=7)
        filter_condition = [Conversation.user_id == user_id, Conversation.scenario == scenario]
        if knowledge_base_id:
            filter_condition.append(Conversation.knowledge_base_id == knowledge_base_id)
        conversations = db.query(Conversation).filter(
            *filter_condition
        ).order_by(desc(Conversation.updated_at)).all()
        
        # 按时间分组
        groups = []
        today_group = {"time_group": "今日", "conversations": []}
        fewdays_group = {"time_group": "3日内", "conversations": []}
        week_group = {"time_group": "最近7天", "conversations": []}
        older_group = {"time_group": "更早", "conversations": []}
        
        for conv in conversations:
            conv_date = conv.updated_at.date()
            conv_data = {
                "id": conv.id,
                "title": conv.title,
                "updated_at": conv.updated_at.isoformat()
            }
            
            if conv_date == today:
                today_group["conversations"].append(conv_data)
            elif conv_date >= three_days_ago:
                fewdays_group["conversations"].append(conv_data)
            elif conv_date >= one_week_ago:
                week_group["conversations"].append(conv_data)
            else:
                older_group["conversations"].append(conv_data)
        
        # 只添加有对话的分组
        if today_group["conversations"]:
            groups.append(today_group)
        if fewdays_group["conversations"]:
            groups.append(fewdays_group)
        if week_group["conversations"]:
            groups.append(week_group)
        if older_group["conversations"]:
            groups.append(older_group)

        return groups
    
    @staticmethod
    async def create_new_conversation(user_id: int, title: str, scenario: str, knowledge_base_id: str, db: Session) -> Conversation:
        # 如果提供了 knowledge_base_id，验证其存在性
        if knowledge_base_id:
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id).first()
            if not kb:
                knowledge_base_id = None  # 设置为 None

        new_conversation = Conversation(
            user_id=user_id,
            title=title,
            scenario=scenario,
            knowledge_base_id=knowledge_base_id
        )
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        return new_conversation
    
    @staticmethod
    async def create_new_message(conversation_id: int, role: str, content: str, db: Session) -> Message:
        user_message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        return user_message

    @staticmethod
    async def get_conversation_history(conversation_id: int, db: Session):
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.asc()).limit(7).all()
        
        history = [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
            for msg in messages[:-1]
        ]
        
        return history

    @staticmethod
    async def get_conversation_message(conversation_id: int, db: Session) -> Conversation:
        conversation_message = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            # Message.user_id == user_id
        ).all()

        if not conversation_message:
            return JSONResponse(status_code=404, content={"error": "对话不存在"})

        return conversation_message
    
    @staticmethod
    async def rename_conversation(user_id: int, conversation_id: str, new_title: str, db: Session) -> Conversation:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()

        if not conversation:
            return JSONResponse(status_code=404, content={"error": "对话不存在"})
        
        conversation.title = new_title
        db.commit()
        db.refresh(conversation)

        return {
            "success": True,
            "message": "对话重命名成功",
            "conversation": conversation
        }
    
    @staticmethod
    async def delete_conversation(user_id: int, conversation_id: str, db: Session) -> Conversation:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()

        if not conversation:
            return JSONResponse(status_code=404, content={"error": "对话不存在"})
        
        db.delete(conversation)
        db.commit()
        
        return {
            "success": True,
            "message": "对话删除成功",
        }
    

        
    @staticmethod
    async def get_conversation_ai_message(conversation_id: str, db: Session):
        ai_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.role == "assistant"
        ).all()
        return ai_messages
