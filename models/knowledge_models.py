
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from models.database import Base
from sqlalchemy.orm import relationship


class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    collection_name = Column(String(100), unique=True, nullable=False)  # ChromaDB集合名
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    file_count = Column(Integer, default=0)
    
        # 关联文件
    files = relationship("KnowledgeFile", back_populates="knowledge_base", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, name='{self.name}')>"
    
class KnowledgeFile(Base):
    """知识库文件表"""
    __tablename__ = "knowledge_files"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer)  # 文件大小（字节）
    file_type = Column(String(50))  # 文件类型：pdf, docx, txt等
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0)  # 文档分片数量
    uploaded_at = Column(DateTime, default=func.now())
    processed_at = Column(DateTime)
    
    # 关联知识库
    knowledge_base = relationship("KnowledgeBase", back_populates="files")
    
    def __repr__(self):
        return f"<KnowledgeFile(id={self.id}, filename='{self.filename}')>"