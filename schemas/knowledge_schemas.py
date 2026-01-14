
### knowledge pydantic 验证
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]

class KnowledgeFileResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: str
    status: str
    chunk_count: int
    uploaded_at: datetime

class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str
    collection_name: str
    file_count: int
    created_at: datetime
    updated_at: datetime
    files: List[KnowledgeFileResponse] = []