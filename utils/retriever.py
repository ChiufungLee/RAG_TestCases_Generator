import functools
from threading import Lock
import chromadb
from typing import List, Dict, Any
from fastapi import Depends
from openai import OpenAI  
from langchain_core.documents import Document
from dotenv import load_dotenv
import os
from models.database import get_db
from services import knowlege_service
from sqlalchemy.orm import Session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")
ALIYUN_BASE_URL = os.getenv("ALIYUN_BASE_URL")

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
RAG_DB_PATH = os.getenv("RAG_DB_PATH")



class ChromaRetriever:
    def __init__(
        self,
        collection_name: str,
        chroma_client: chromadb.Client,
        # ALIYUN_API_KEY: str,
        model_name: str = "text-embedding-v4",
        embedding_dimensions: int = 1024,
        encoding_format: str = "float"
    ):
        """
        初始化 Chroma 检索器
        :param collection_name: Chroma 数据库集合名称
        :param chroma_client: 已初始化的 Chroma 客户端
        :param openai_api_key: OpenAI API 密钥
        :param model_name: 使用的嵌入模型名称
        :param embedding_dimensions: 向量维度（仅支持 text-embedding-v3/v4）
        :param encoding_format: 向量编码格式（float 或 base64）
        """
        self.collection_name = collection_name
        self.chroma_client = chroma_client
        self.model_name = model_name
        self.embedding_dimensions = embedding_dimensions
        self.encoding_format = encoding_format

        # 初始化 OpenAI 客户端
        # self.openai_client = OpenAI(api_key=openai_api_key)
        self.openai_client = OpenAI(
            api_key=os.getenv("ALIYUN_API_KEY"), 
            base_url=os.getenv("ALIYUN_BASE_URL")
        )

        # 获取 Chroma 集合
        self.collection = self.chroma_client.get_collection(name=collection_name)

    async def embed(self, text: str) -> List[float]:
        """
        生成文本的嵌入向量
        :param text: 输入文本
        :return: 嵌入向量
        """
        response = self.openai_client.embeddings.create(
            model=self.model_name,
            input=text,
            dimensions=self.embedding_dimensions,
            encoding_format=self.encoding_format
        )
        print(f"使用的 token 数量为：{response.usage.total_tokens}")
        return response.data[0].embedding  # 返回向量数据

    async def get_relevant_documents(self, query: str, n_results: int = 3) -> List[Document]:
        """LangChain标准接口方法"""
        query_vector = await self.embed(query)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            include=["documents", "metadatas"]
        )
        
        # 将结果转换为LangChain Document对象
        documents = []
        if results.get('documents'):
            for doc_list in results['documents']:
                for i, text in enumerate(doc_list):
                    metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                    documents.append(Document(page_content=text, metadata=metadata))
        return documents
    
    async def query(
        self,
        query_text: str,
        n_results: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行向量检索
        :param query_text: 查询文本
        :param n_results: 返回结果数量
        :param kwargs: 其他查询参数（传递给 chroma 的 query 方法）
        :return: 查询结果（包含文档和元数据）
        """
        query_vector = self.embed(query_text)
        results = self.collection.query(
            query_embeddings=query_vector,
            n_results=n_results,
            **kwargs
        )
        return results
    
    @staticmethod
    async def clear_retriever_cache(kb_id: str):
        """清除指定知识库的检索器缓存"""
        with _retriever_lock:
            if kb_id in _retriever_cache:
                del _retriever_cache[kb_id]
                logger.info(f"已清除知识库 {kb_id} 的检索器缓存")
                return True
            return False

    @staticmethod
    async def clear_all_retriever_caches():
        """清除所有检索器缓存"""
        with _retriever_lock:
            _retriever_cache.clear()
            logger.info("已清除所有检索器缓存")

# 缓存检索器
_retriever_lock = Lock()
_retriever_cache = {}

@functools.lru_cache(maxsize=2)  # 最多缓存2个不同场景的检索器
def _get_cached_chroma_client():
    """缓存的Chroma客户端单例（进程级别）"""
    RAG_DB_PATH = os.getenv("RAG_DB_PATH", "./chroma_db")
    print(f"初始化Chroma客户端，路径: {RAG_DB_PATH}")
    return chromadb.PersistentClient(path=RAG_DB_PATH)



def get_rag_retriever(scenario: str):
    """根据场景获取对应的RAG检索器（优化后）"""
    COLLECTION_MAP = {  # 常量用大写
        "devops_tool": "devops_tool",
        "product_manual": "product_manual"
    }
    
    if scenario not in COLLECTION_MAP:
        return None
    
    collection_name = COLLECTION_MAP[scenario]
    
    # 检查缓存
    with _retriever_lock:
        if scenario in _retriever_cache:
            return _retriever_cache[scenario]
        
        try:
            # 使用缓存的客户端
            chroma_client = _get_cached_chroma_client()
            
            retriever = ChromaRetriever(
                collection_name=collection_name,
                chroma_client=chroma_client,
                model_name="text-embedding-v4"
            )
            
            # 存入缓存
            _retriever_cache[scenario] = retriever
            print(f"已为场景 '{scenario}' 创建并缓存检索器")
            return retriever
            
        except Exception as e:
            # 使用logging模块替代print
            import logging
            logging.error(f"创建 {scenario} 场景检索器失败: {e}", exc_info=True)
            return None
        
async def get_rag_retriever_by_kb(kb_id: str = "", db: Session = Depends(get_db)):
    """根据知识库ID获取检索器"""

    # 检查缓存
    with _retriever_lock:
        if kb_id in _retriever_cache:
            logger.info(f"从缓存获取知识库 {kb_id} 的检索器")
            return _retriever_cache[kb_id]

    # 获取知识库信息    
    try:
        # kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        kb = await knowlege_service.get_knowledge_base_by_id(db=db, kb_id=kb_id)
        if not kb:
            return None
        
        collection_name = kb.collection_name
        
        # 获取 ChromaDB 客户端
        chroma_client = _get_cached_chroma_client()
        
        # 检查集合是否存在
        try:
            # 尝试获取集合，如果不存在会抛出异常
            collection = chroma_client.get_collection(name=collection_name)
            logger.info(f"知识库 {kb_id} 的向量集合存在，包含 {collection.count()} 个向量")
        except Exception as e:
            logger.error(f"知识库 {kb_id} 的向量集合不存在: {e}")
            return None
        
        # 创建检索器
        retriever = ChromaRetriever(
            collection_name=collection_name,
            chroma_client=chroma_client,
            model_name="text-embedding-v4"
        )
                
        # 存入缓存
        with _retriever_lock:
            _retriever_cache[kb_id] = retriever
        
        logger.info(f"已为知识库 {kb_id} 创建检索器，集合名称: {collection_name}")
        return retriever
    except Exception as e:
        import logging
        logging.error(f"创建知识库 {kb_id} 的检索器失败: {e}", exc_info=True)
        return None
    
