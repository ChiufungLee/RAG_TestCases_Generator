
# 创建知识库记录
from contextlib import contextmanager
from datetime import datetime
import os
import shutil
import uuid
from models.chat import Conversation
from utils.file_handle import document_processor
from fastapi import HTTPException
import logging
from models.database import SessionLocal, get_db
from models.knowledge_models import KnowledgeBase, KnowledgeFile
from utils.file_handle import UPLOAD_DIR
from utils.retriever import ChromaRetriever


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_knowledge_record(db, record_data):
    collection_name = f"kb_{uuid.uuid4().hex[:16]}"
    kb = KnowledgeBase(
        name=record_data.name,
        description=record_data.description,
        collection_name=collection_name
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return {
        "success": True,
        "message": "知识库创建成功",
        "knowledge_base": kb
    }

# 获取所有知识库记录
async def get_all_knowledge(db):
    return db.query(KnowledgeBase).all()

# 根据ID获取单个知识库记录
async def get_knowledge_base_by_id(kb_id, db):
    return db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

# 更新知识库记录
async def update_knowledge_base(db, kb_id, kb_data):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        return {
            "success": False,
            "message": "知识库创建失败，知识库不存在",
            "knowledge_base": kb
        }
    
    # 更新字段
    if kb_data.name is not None:
        kb.name = kb_data.name
    if kb_data.description is not None:
        kb.description = kb_data.description
    
    kb.updated_at = datetime.now()
    db.commit()
    db.refresh(kb)
    return kb

# 上传文档到知识库
async def upload_document(kb_id, file, background_tasks, db):
    # from utils.file_handle import save_document_to_knowledge_base

    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise Exception("知识库不存在")
    
    # 保存文件到本地临时目录
    # file_location = f"temp_uploads/{uuid.uuid4().hex}_{file.filename}"
    # with open(file_location, "wb") as buffer:
    #     shutil.copyfileobj(file.file, buffer)
        
    
    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    
    # 保存路径
    save_path = os.path.join(UPLOAD_DIR, unique_filename)
    print(f"保存路径: {save_path}")
    # 使用后台任务处理文件上传和分片保存
    # background_tasks.add_task(
    #     save_document_to_knowledge_base,
    #     kb,
    #     file_location,
    #     db
    # )

    try:
        # 保存文件
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 验证文件保存成功
        if not os.path.exists(save_path):
            raise HTTPException(status_code=500, detail="文件保存失败")
        
        # 获取文件大小
        file_size = os.path.getsize(save_path)
        
        # 创建文件记录
        file_record = KnowledgeFile(
            knowledge_base_id=kb_id,
            filename=file.filename,
            file_path=save_path,
            file_size=file_size,
            file_type="pdf",
            status="pending"
        )
        
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        
        # 启动后台任务处理文档
        background_tasks.add_task(
            process_document_async,
            file_record.id,
            kb_id
        )
        
        return {
            "success": True,
            "message": "文件上传成功，正在后台处理",
            "file_id": file_record.id,
            "filename": file.filename
        }
        
    except Exception as e:
        # 清理已保存的文件（如果存在）
        if os.path.exists(save_path):
            os.remove(save_path)
        # logger.error(f"文件上传失败: {e}")
        print(f"文件上传失败: {e}")
        # raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
        return {
            "success": False,
            "message": "文件上传失败"
        }

# 删除知识库记录
async def delete_knowledge_base(db, kb_id):
    from utils.file_handle import UPLOAD_DIR, document_processor
    
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    try:
        conversations = db.query(Conversation).filter(
            Conversation.knowledge_base_id == kb_id
        ).all()
        
        for conversation in conversations:
            conversation.knowledge_base_id = None

        # 1. 删除ChromaDB集合
        document_processor.delete_collection(kb.collection_name)
        
        # 2. 清除检索器缓存
        await ChromaRetriever.clear_retriever_cache(kb_id)

        # 2. 删除数据库记录（级联删除文件记录）
        db.delete(kb)
        db.commit()
        
        # 3. 删除已上传的文件（可选）
        # 这里可以根据需要清理文件系统中的文件
        
        return {
            "success": True,
            "message": "知识库删除成功"
        }
        
    except Exception as e:
        db.rollback()
        print(f"删除知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    
@contextmanager
def get_db_context():
    """用于后台任务的数据库会话上下文管理器"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def process_document_async(file_id: str, kb_id: str):
    """后台处理文档（向量化）"""
    
    with get_db_context() as db:
        try:
            # 获取文件记录
            file_record = db.query(KnowledgeFile).filter(
                KnowledgeFile.id == file_id,
                KnowledgeFile.knowledge_base_id == kb_id
            ).first()
            
            if not file_record:
                logger.error(f"文件记录不存在: {file_id}")
                return
            
            # 更新状态为处理中
            file_record.status = "processing"
            db.commit()
            
            # 加载PDF
            docs = document_processor.load_pdf(file_record.file_path)
            
            # 分割文档
            splits = document_processor.split_documents(docs)
            
            # 准备文件元数据
            file_metadata = {
                "file_id": file_record.id,
                "filename": file_record.filename,
                "knowledge_base_id": kb_id,
                "processed_at": datetime.now().isoformat()
            }
            
            # 获取知识库
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise Exception("知识库不存在")
            
            # 保存到ChromaDB
            chunk_count = document_processor.save_to_chroma(
                splits=splits,
                collection_name=kb.collection_name,
                file_metadata=file_metadata
            )
            
            # 更新文件记录
            file_record.status = "completed"
            file_record.chunk_count = chunk_count
            file_record.processed_at = datetime.now()
            db.commit()

            # 更新知识库文件计数
            new_count  = db.query(KnowledgeFile).filter(
                KnowledgeFile.knowledge_base_id == kb_id,
                KnowledgeFile.status == "completed"
            ).count()
            
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            kb.file_count = new_count
            kb.updated_at = datetime.now()
            
            db.commit()
            logger.info(f"文档处理完成: {file_record.filename}, 分片数: {chunk_count}")
            
        except Exception as e:
            # 更新状态为失败
            if file_record:
                file_record.status = "failed"
                db.commit()
            logger.error(f"文档处理失败: {e}")
            raise