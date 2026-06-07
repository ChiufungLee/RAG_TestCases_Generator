import functools
import logging
from threading import Lock
from typing import Any, Dict, List

import chromadb
from fastapi import Depends
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from config import get_embedding_client, get_rag_db_path
from models.database import get_db
from services import knowlege_service

logger = logging.getLogger(__name__)


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
        self.openai_client = get_embedding_client()
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

    async def get_relevant_documents(
        self,
        query: str,
        n_results: int = 3,
        distance_threshold: float = 1.2,
    ) -> List[Document]:
        """从ChromaDB中检索与查询相关的文档。

        先请求两倍数量的候选结果，再根据距离阈值过滤掉不相关的文档，
        最终返回最多 n_results 条高相关度结果。

        Args:
            query: 用户查询文本。
            n_results: 最终返回的最大文档数量，默认3。
            distance_threshold: L2距离阈值，超过此值的结果被视为不相关而被过滤。
                ChromaDB默认使用L2距离（值越小越相关），同主题文档通常在0.3-0.8之间，
                超过1.2基本不相关。可根据实际检索效果调整。
        """
        query_vector = await self.embed(query)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(n_results * 2, self.collection.count() or n_results * 2),
            include=["documents", "metadatas", "distances"],
        )

        documents = []
        documents_groups = results.get("documents") or []
        metadata_groups = results.get("metadatas") or []
        distance_groups = results.get("distances") or []
        for group_index, doc_list in enumerate(documents_groups):
            metadata_list = metadata_groups[group_index] if group_index < len(metadata_groups) else []
            distance_list = distance_groups[group_index] if group_index < len(distance_groups) else []
            for item_index, text in enumerate(doc_list):
                distance = distance_list[item_index] if item_index < len(distance_list) else float("inf")
                if distance > distance_threshold:
                    logger.debug("过滤低相关文档: distance=%.4f > threshold=%.4f", distance, distance_threshold)
                    continue
                metadata = metadata_list[item_index] if item_index < len(metadata_list) else {}
                documents.append(Document(page_content=text, metadata=metadata or {}))
                if len(documents) >= n_results:
                    break
            if len(documents) >= n_results:
                break

        logger.info("检索结果: 请求%d个, 阈值过滤后%d个 (threshold=%.2f)", n_results, len(documents), distance_threshold)
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


def _build_kb_cache_key(kb_id: str) -> str:
    return kb_id


@functools.lru_cache(maxsize=2)
def _get_cached_chroma_client():
    rag_db_path = get_rag_db_path()
    logger.info("初始化Chroma客户端，路径: %s", rag_db_path)
    return chromadb.PersistentClient(path=rag_db_path)



def reset_retriever_state():
    with _retriever_lock:
        _retriever_cache.clear()
    _get_cached_chroma_client.cache_clear()
    get_embedding_client.cache_clear()



async def get_rag_retriever_by_kb(
    kb_or_id,
    db: Session = Depends(get_db),
):
    try:
        if isinstance(kb_or_id, str):
            kb_id = kb_or_id
            cache_key = _build_kb_cache_key(kb_id)
            with _retriever_lock:
                if cache_key in _retriever_cache:
                    logger.info("从缓存获取知识库 %s 的检索器", kb_id)
                    return _retriever_cache[cache_key]

            kb = await knowlege_service.get_knowledge_base_by_id(db=db, kb_id=kb_id)
            if not kb:
                return None
        else:
            kb = kb_or_id
            kb_id = kb.id
            cache_key = _build_kb_cache_key(kb_id)
            with _retriever_lock:
                if cache_key in _retriever_cache:
                    logger.info("从缓存获取知识库 %s 的检索器", kb_id)
                    return _retriever_cache[cache_key]

        chroma_client = _get_cached_chroma_client()

        try:
            collection = chroma_client.get_collection(name=kb.collection_name)
            logger.info("知识库 %s 的向量集合存在，包含 %s 个向量", kb_id, collection.count())
        except Exception as e:
            logger.error("知识库 %s 的向量集合不存在: %s", kb_id, e)
            return None

        retriever = ChromaRetriever(
            collection_name=kb.collection_name,
            chroma_client=chroma_client,
            model_name="text-embedding-v4",
        )

        with _retriever_lock:
            _retriever_cache[cache_key] = retriever

        logger.info("已为知识库 %s 创建检索器，集合名称: %s", kb_id, kb.collection_name)
        return retriever
    except Exception as e:
        logger.error("创建知识库 %s 的检索器失败: %s", kb_id, e, exc_info=True)
        return None
