import datetime
import os
import shutil
from typing import List
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File, logger
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models.database import get_db
from models.knowledge_models import KnowledgeBase, KnowledgeFile
from schemas.knowledge_schemas import KnowledgeBaseCreate, KnowledgeBaseResponse, KnowledgeBaseUpdate
from services import knowlege_service
from utils.file_handle import UPLOAD_DIR, document_processor
from pathlib import Path

app = APIRouter()
templates = Jinja2Templates(directory="templates")

@app.post("/api/knowledge-bases/", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    db: Session = Depends(get_db)
):
    """创建知识库"""
    create_knowledge = await knowlege_service.create_knowledge_record(db, kb_data)
    if not create_knowledge["success"]:
        raise HTTPException(status_code=400, detail=create_knowledge["message"])
    
    
    # 在ChromaDB中创建集合
    document_processor.chromadb_client.get_or_create_collection(
        name=create_knowledge["knowledge_base"].collection_name
    )

    return create_knowledge["knowledge_base"]

@app.get("/api/knowledge-bases/", response_model=List[KnowledgeBaseResponse])
async def list_knowledge_bases(db: Session = Depends(get_db)):
    """获取所有知识库"""
    kbs = await knowlege_service.get_all_knowledge(db)
    return kbs

@app.get("/knowledge-detail", response_class=HTMLResponse)
async def knowledge_detail(request: Request, kb_id: str):
    kb_id = request.session.get("kb_id", kb_id)
    return templates.TemplateResponse("knowledge_detail.html", {"request": request, "kb_id": kb_id})

@app.get("/api/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(kb_id: str, db: Session = Depends(get_db)):
    """获取单个知识库详情"""
    
    kb = await knowlege_service.get_knowledge_base_by_id(kb_id = kb_id, db=db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    print(f"单个知识库kb: {kb}")
    return kb

@app.put("/api/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge(
    kb_id: str,
    kb_data: KnowledgeBaseUpdate,
    db: Session = Depends(get_db)
):
    """更新知识库"""
    kb = await knowlege_service.update_knowledge_base(db, kb_id, kb_data)
    return kb

@app.post("/api/knowledge-bases/{kb_id}/upload")
async def upload_document(
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传文档到知识库"""
    # 检查知识库是否存在

    result = await knowlege_service.upload_document(kb_id, file, background_tasks, db)
    return result

@app.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge(kb_id: str, db: Session = Depends(get_db)):
    """删除知识库及其所有文件"""
    kb = await knowlege_service.delete_knowledge_base(db, kb_id)
    return kb



@app.delete("/api/knowledge-bases/{kb_id}/files/{file_id}")
async def delete_file(
    kb_id: str,
    file_id: str,
    db: Session = Depends(get_db)
):
    """从知识库中删除单个文件"""
    # 这里需要实现从ChromaDB中删除特定文件的所有向量
    # 由于ChromaDB不支持按metadata批量删除，这里简化为删除整个集合重新构建
    # 实际生产环境需要考虑更优的实现
    
    file_record = db.query(KnowledgeFile).filter(
        KnowledgeFile.id == file_id,
        KnowledgeFile.knowledge_base_id == kb_id
    ).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # TODO: 实现从ChromaDB中删除特定文件的向量
    # 当前简化实现：删除文件记录，实际需要重建集合
    
    # 删除文件记录
    db.delete(file_record)
    
    # 删除物理文件
    if os.path.exists(file_record.file_path):
        os.remove(file_record.file_path)
    
    db.commit()
    
    return {"message": "文件删除成功"}

@app.get("/api/knowledge-bases/{kb_id}/collection-info")
async def get_collection_info(kb_id: str, db: Session = Depends(get_db)):
    """获取知识库的向量集合信息"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    info = document_processor.get_collection_info(kb.collection_name)
    if not info:
        raise HTTPException(status_code=404, detail="向量集合不存在")
    
    return info

@app.get("/api/knowledge-bases/{kb_id}/files")
async def get_knowledge_files(kb_id: str, db: Session = Depends(get_db)):
    """获取知识库下的所有文件"""
    # 检查知识库是否存在
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 获取知识库下的所有文件
    files = db.query(KnowledgeFile).filter(
        KnowledgeFile.knowledge_base_id == kb_id
    ).order_by(KnowledgeFile.created_at.desc()).all()
    
    return files


@app.get("/api/files/{file_id}/preview")
async def preview_file(file_id: str, db: Session = Depends(get_db)):
    """预览文件 - 在新标签页打开"""
    try:
        # 1. 从数据库获取文件记录
        file_record = db.query(KnowledgeFile).filter(KnowledgeFile.id == file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        current_file = Path(__file__).resolve()
        
        project_root = current_file.parent.parent.parent  # 上三级到 fastapi 目录
        print(f"项目根目录: {project_root}")
        
        # 4. 处理文件路径
        original_path = file_record.file_path
        
        # 如果是相对路径（如 "./uploads\xxx.pdf"）
        if original_path.startswith("./"):
            # 提取相对路径部分（去掉"./"）
            relative_path = original_path[2:]

            if os.name == 'nt':  # Windows
                relative_path = relative_path.replace('/', '\\')
            else:  # Linux/Mac
                relative_path = relative_path.replace('\\', '/')
            
            # 构建完整路径
            full_path = project_root / relative_path
        else:
            full_path = Path(original_path)
        

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="文件不存在或已被删除")
        

        return FileResponse(
            path=full_path,
            filename=file_record.filename,  # 设置下载时的文件名
            media_type="application/pdf",  # 假设都是PDF，如果其他类型需要扩展

        )
        
    except Exception as e:
        print(f"文件预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件预览失败: {str(e)}")
    