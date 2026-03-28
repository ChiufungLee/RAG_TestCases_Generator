import functools
import logging
import os
from threading import Lock
from typing import Any, Dict, List

import chromadb
from fastapi import Depends
from langchain_core.documents import Document
from openai import OpenAI
from sqlalchemy.orm import Session

from models.database import get_db
from services import knowlege_service

logger = logging.getLogger(__name__)

ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")
ALIYUN_BASE_URL = os.getenv("ALIYUN_BASE_URL")


class ChromaRetriever:
    def __init__(
        self,
        collection_name: str,
        chroma_client: chromadb.Client,
        model_name: str = "text-embedding-v4",
        embedding_dimensions: int = 1024,
        encoding_format: str = "float",
    ):
        self.collection_name = collection_name
        self.chroma_client = chroma_client
        self.model_name = model_name
        self.embedding_dimensions = embedding_dimensions
        self.encoding_format = encoding_format
        self.openai_client = OpenAI(
            api_key=ALIYUN_API_KEY,
            base_url=ALIYUN_BASE_URL,
        )
        self.collection = self.chroma_client.get_collection(name=collection_name)

    async def embed(self, text: str) -> List[float]:
        response = self.openai_client.embeddings.create(
            model=self.model_name,
            input=text,
            dimensions=self.embedding_dimensions,
            encoding_format=self.encoding_format,
        )
        logger.debug("embedding token 使用量: %s", response.usage.total_tokens)
        return response.data[0].embedding

    async def get_relevant_documents(self, query: str, n_results: int = 3) -> List[Document]:
        query_vector = await self.embed(query)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            include=["documents", "metadatas"],
        )

        documents = []
        documents_groups = results.get("documents") or []
        metadata_groups = results.get("metadatas") or []
        for group_index, doc_list in enumerate(documents_groups):
            metadata_list = metadata_groups[group_index] if group_index < len(metadata_groups) else []
            for item_index, text in enumerate(doc_list):
                metadata = metadata_list[item_index] if item_index < len(metadata_list) else {}
                documents.append(Document(page_content=text, metadata=metadata or {}))
        return documents

    async def query(
        self,
        query_text: str,
        n_results: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        query_vector = await self.embed(query_text)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            **kwargs,
        )
        return results

    @staticmethod
    async def clear_retriever_cache(kb_id: str):
        with _retriever_lock:
            if kb_id in _retriever_cache:
                del _retriever_cache[kb_id]
                logger.info("已清除知识库 %s 的检索器缓存", kb_id)
                return True
            return False

    @staticmethod
    async def clear_all_retriever_caches():
        with _retriever_lock:
            _retriever_cache.clear()
            logger.info("已清除所有检索器缓存")


_retriever_lock = Lock()
_retriever_cache = {}


@functools.lru_cache(maxsize=2)
def _get_cached_chroma_client():
    rag_db_path = os.getenv("RAG_DB_PATH", "./chroma_db")
    logger.info("初始化Chroma客户端，路径: %s", rag_db_path)
    return chromadb.PersistentClient(path=rag_db_path)


def get_rag_retriever(scenario: str):
    collection_map = {
        "devops_tool": "devops_tool",
        "product_manual": "product_manual",
    }

    if scenario not in collection_map:
        return None

    collection_name = collection_map[scenario]

    with _retriever_lock:
        if scenario in _retriever_cache:
            return _retriever_cache[scenario]

        try:
            chroma_client = _get_cached_chroma_client()
            retriever = ChromaRetriever(
                collection_name=collection_name,
                chroma_client=chroma_client,
                model_name="text-embedding-v4",
            )
            _retriever_cache[scenario] = retriever
            logger.info("已为场景 %s 创建并缓存检索器", scenario)
            return retriever
        except Exception as e:
            logger.error("创建 %s 场景检索器失败: %s", scenario, e, exc_info=True)
            return None


async def get_rag_retriever_by_kb(kb_id: str = "", db: Session = Depends(get_db), user_id: int | None = None):
    with _retriever_lock:
        if kb_id in _retriever_cache:
            logger.info("从缓存获取知识库 %s 的检索器", kb_id)
            return _retriever_cache[kb_id]

    try:
        kb = await knowlege_service.get_knowledge_base_by_id(db=db, kb_id=kb_id, user_id=user_id)
        if not kb:
            return None

        collection_name = kb.collection_name
        chroma_client = _get_cached_chroma_client()

        try:
            collection = chroma_client.get_collection(name=collection_name)
            logger.info("知识库 %s 的向量集合存在，包含 %s 个向量", kb_id, collection.count())
        except Exception as e:
            logger.error("知识库 %s 的向量集合不存在: %s", kb_id, e)
            return None

        retriever = ChromaRetriever(
            collection_name=collection_name,
            chroma_client=chroma_client,
            model_name="text-embedding-v4",
        )

        with _retriever_lock:
            _retriever_cache[kb_id] = retriever

        logger.info("已为知识库 %s 创建检索器，集合名称: %s", kb_id, collection_name)
        return retriever
    except Exception as e:
        logger.error("创建知识库 %s 的检索器失败: %s", kb_id, e, exc_info=True)
        return None
