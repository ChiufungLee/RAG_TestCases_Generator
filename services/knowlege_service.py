from contextlib import contextmanager
from datetime import datetime
import logging
import mimetypes
import os
from pathlib import Path
import shutil
import uuid

from fastapi import HTTPException

from models.chat import Conversation
from models.database import SessionLocal
from models.knowledge_models import KnowledgeBase, KnowledgeFile
from utils.file_handle import UPLOAD_DIR, document_processor
from utils.retriever import ChromaRetriever

logger = logging.getLogger(__name__)
UPLOAD_ROOT = Path(UPLOAD_DIR).resolve()


def resolve_upload_path(file_path: str) -> Path:
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = (UPLOAD_ROOT / candidate.name).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(UPLOAD_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="文件路径非法") from exc

    return candidate


async def create_knowledge_record(db, record_data, owner_user_id: int):
    collection_name = f"kb_{uuid.uuid4().hex[:16]}"
    kb = KnowledgeBase(
        name=record_data.name,
        description=record_data.description,
        collection_name=collection_name,
        owner_user_id=owner_user_id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return {
        "success": True,
        "message": "知识库创建成功",
        "knowledge_base": kb,
    }


async def get_all_knowledge(db, user_id: int):
    return db.query(KnowledgeBase).filter(KnowledgeBase.owner_user_id == user_id).all()


async def get_knowledge_base_by_id(kb_id, db, user_id: int | None = None):
    if not kb_id:
        return None

    query = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id)
    if user_id is not None:
        query = query.filter(KnowledgeBase.owner_user_id == user_id)
    return query.first()


async def update_knowledge_base(db, kb_id, kb_data, user_id: int):
    kb = await get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        return None

    if kb_data.name is not None:
        kb.name = kb_data.name
    if kb_data.description is not None:
        kb.description = kb_data.description

    kb.updated_at = datetime.now()
    db.commit()
    db.refresh(kb)
    return kb


async def upload_document(kb_id, file, background_tasks, db, user_id: int):
    kb = await get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    save_path = (UPLOAD_ROOT / unique_filename).resolve()

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not save_path.exists():
            raise HTTPException(status_code=500, detail="文件保存失败")

        file_size = save_path.stat().st_size
        file_type = (file_ext.lstrip(".") or (file.content_type or "unknown").split("/")[-1]).lower()

        file_record = KnowledgeFile(
            knowledge_base_id=kb_id,
            filename=file.filename,
            file_path=str(save_path),
            file_size=file_size,
            file_type=file_type,
            status="pending",
        )

        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        background_tasks.add_task(
            process_document_async,
            file_record.id,
            kb_id,
        )

        return {
            "success": True,
            "message": "文件上传成功，正在后台处理",
            "file_id": file_record.id,
            "filename": file.filename,
        }

    except HTTPException:
        if save_path.exists():
            save_path.unlink()
        raise
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        logger.error("文件上传失败: %s", e, exc_info=True)
        return {
            "success": False,
            "message": "文件上传失败",
        }


async def delete_knowledge_base(db, kb_id, user_id: int):
    kb = await get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        conversations = db.query(Conversation).filter(Conversation.knowledge_base_id == kb_id).all()
        for conversation in conversations:
            conversation.knowledge_base_id = None

        document_processor.delete_collection(kb.collection_name)
        await ChromaRetriever.clear_retriever_cache(kb_id)

        db.delete(kb)
        db.commit()

        return {
            "success": True,
            "message": "知识库删除成功",
        }

    except Exception as e:
        db.rollback()
        logger.error("删除知识库失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


async def get_knowledge_file(db, file_id: str, user_id: int):
    return (
        db.query(KnowledgeFile)
        .join(KnowledgeBase, KnowledgeFile.knowledge_base_id == KnowledgeBase.id)
        .filter(KnowledgeFile.id == file_id, KnowledgeBase.owner_user_id == user_id)
        .first()
    )


async def get_knowledge_files_by_kb(db, kb_id: str, user_id: int):
    kb = await get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        return None, None

    files = (
        db.query(KnowledgeFile)
        .filter(KnowledgeFile.knowledge_base_id == kb_id)
        .order_by(KnowledgeFile.uploaded_at.desc())
        .all()
    )
    return kb, files


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
        file_record = None
        try:
            file_record = (
                db.query(KnowledgeFile)
                .filter(KnowledgeFile.id == file_id, KnowledgeFile.knowledge_base_id == kb_id)
                .first()
            )

            if not file_record:
                logger.error("文件记录不存在: %s", file_id)
                return

            file_record.status = "processing"
            db.commit()

            file_path = resolve_upload_path(file_record.file_path)
            if not file_path.exists():
                logger.warning("文件已不存在，跳过后台处理: %s", file_path)
                db.delete(file_record)
                db.commit()
                return

            docs = document_processor.load_pdf(str(file_path))
            splits = document_processor.split_documents(docs)

            file_metadata = {
                "file_id": file_record.id,
                "filename": file_record.filename,
                "knowledge_base_id": kb_id,
                "processed_at": datetime.now().isoformat(),
            }

            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise Exception("知识库不存在")

            chunk_count = document_processor.save_to_chroma(
                splits=splits,
                collection_name=kb.collection_name,
                file_metadata=file_metadata,
            )

            file_record.status = "completed"
            file_record.chunk_count = chunk_count
            file_record.processed_at = datetime.now()
            db.commit()

            new_count = (
                db.query(KnowledgeFile)
                .filter(KnowledgeFile.knowledge_base_id == kb_id, KnowledgeFile.status == "completed")
                .count()
            )

            kb.file_count = new_count
            kb.updated_at = datetime.now()
            db.commit()
            logger.info("文档处理完成: %s, 分片数: %s", file_record.filename, chunk_count)

        except Exception as e:
            db.rollback()
            refreshed_record = (
                db.query(KnowledgeFile)
                .filter(KnowledgeFile.id == file_id, KnowledgeFile.knowledge_base_id == kb_id)
                .first()
            )

            if isinstance(e, FileNotFoundError):
                if refreshed_record is not None:
                    db.delete(refreshed_record)
                    db.commit()
                logger.warning("文件在后台处理期间已被删除: %s", file_id)
                return

            if refreshed_record is not None:
                refreshed_record.status = "failed"
                db.commit()
            logger.error("文档处理失败: %s", e, exc_info=True)
            return


def get_safe_media_type(filename: str) -> str:
    media_type, _ = mimetypes.guess_type(filename)
    return media_type or "application/octet-stream"
