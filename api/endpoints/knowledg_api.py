import logging
import os
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.knowledge_models import KnowledgeBase
from schemas.knowledge_schemas import KnowledgeBaseCreate, KnowledgeBaseResponse, KnowledgeBaseUpdate
from services import knowlege_service
from utils.file_handle import document_processor

app = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def _get_current_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return user_id


@app.post("/api/knowledge-bases/", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    request: Request,
    kb_data: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
):
    user_id = _get_current_user_id(request)
    create_knowledge = await knowlege_service.create_knowledge_record(db, kb_data, owner_user_id=user_id)
    if not create_knowledge["success"]:
        raise HTTPException(status_code=400, detail=create_knowledge["message"])

    document_processor.chromadb_client.get_or_create_collection(
        name=create_knowledge["knowledge_base"].collection_name
    )

    return create_knowledge["knowledge_base"]


@app.get("/api/knowledge-bases/", response_model=List[KnowledgeBaseResponse])
async def list_knowledge_bases(request: Request, db: Session = Depends(get_db)):
    user_id = _get_current_user_id(request)
    kbs = await knowlege_service.get_all_knowledge(db, user_id=user_id)
    return kbs


@app.get("/knowledge-detail", response_class=HTMLResponse)
async def knowledge_detail(request: Request, kb_id: str):
    kb_id = request.session.get("kb_id", kb_id)
    return templates.TemplateResponse("knowledge_detail.html", {"request": request, "kb_id": kb_id})


@app.get("/api/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(request: Request, kb_id: str, db: Session = Depends(get_db)):
    user_id = _get_current_user_id(request)
    kb = await knowlege_service.get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@app.put("/api/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge(
    request: Request,
    kb_id: str,
    kb_data: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
):
    user_id = _get_current_user_id(request)
    kb = await knowlege_service.update_knowledge_base(db, kb_id, kb_data, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@app.post("/api/knowledge-bases/{kb_id}/upload")
async def upload_document(
    request: Request,
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user_id = _get_current_user_id(request)
    result = await knowlege_service.upload_document(kb_id, file, background_tasks, db, user_id=user_id)
    return result


@app.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge(request: Request, kb_id: str, db: Session = Depends(get_db)):
    user_id = _get_current_user_id(request)
    kb = await knowlege_service.delete_knowledge_base(db, kb_id, user_id=user_id)
    return kb


@app.delete("/api/knowledge-bases/{kb_id}/files/{file_id}")
async def delete_file(
    request: Request,
    kb_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    user_id = _get_current_user_id(request)
    kb = await knowlege_service.get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    file_record = await knowlege_service.get_knowledge_file(db, file_id=file_id, user_id=user_id)
    if not file_record or file_record.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="文件不存在")

    full_path = knowlege_service.resolve_upload_path(file_record.file_path)

    db.delete(file_record)
    if os.path.exists(full_path):
        os.remove(full_path)

    kb.file_count = max((kb.file_count or 1) - 1, 0)
    db.commit()

    return {"message": "文件删除成功"}


@app.get("/api/knowledge-bases/{kb_id}/collection-info")
async def get_collection_info(request: Request, kb_id: str, db: Session = Depends(get_db)):
    user_id = _get_current_user_id(request)
    kb = await knowlege_service.get_knowledge_base_by_id(kb_id=kb_id, db=db, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    info = document_processor.get_collection_info(kb.collection_name)
    if not info:
        raise HTTPException(status_code=404, detail="向量集合不存在")

    return info


@app.get("/api/knowledge-bases/{kb_id}/files")
async def get_knowledge_files(request: Request, kb_id: str, db: Session = Depends(get_db)):
    user_id = _get_current_user_id(request)
    kb, files = await knowlege_service.get_knowledge_files_by_kb(db, kb_id=kb_id, user_id=user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    return files


@app.get("/api/files/{file_id}/preview")
async def preview_file(request: Request, file_id: str, db: Session = Depends(get_db)):
    user_id = _get_current_user_id(request)
    try:
        file_record = await knowlege_service.get_knowledge_file(db, file_id=file_id, user_id=user_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        full_path = knowlege_service.resolve_upload_path(file_record.file_path)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="文件不存在或已被删除")

        return FileResponse(
            path=full_path,
            filename=file_record.filename,
            media_type=knowlege_service.get_safe_media_type(file_record.filename),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("文件预览失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="文件预览失败")
