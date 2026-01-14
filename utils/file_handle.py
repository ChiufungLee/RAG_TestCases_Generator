# from langchain_community.document_loaders import PyPDFLoader
import logging
from typing import List, Optional
import uuid
from langchain.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
import os
import chromadb
from langchain_core.documents import Document
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")
ALIYUN_BASE_URL = os.getenv("ALIYUN_BASE_URL")
RAG_DB_PATH = os.getenv("RAG_DB_PATH")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
TEMP_UPLOAD_DIR = os.getenv("TEMP_UPLOAD_DIR", "./temp_uploads")

# 确保上传目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

client = OpenAI(
    api_key=ALIYUN_API_KEY,
    base_url=ALIYUN_BASE_URL
)


# 初始化 ChromaDB 客户端
chromadb_client = chromadb.PersistentClient(path=RAG_DB_PATH)

class DocumentProcessor:
    def __init__(self):
        self.client = client
        self.chromadb_client = chromadb_client
    # def __init__(self):
    #     # 延迟初始化客户端，避免在导入时就需要环境变量
    #     self.client = None
    #     self.chromadb_client = None
        
    # def _init_clients(self):
    #     """延迟初始化客户端"""
    #     if self.client is None:
    #         self.client = OpenAI(
    #             api_key=ALIYUN_API_KEY,
    #             base_url=ALIYUN_BASE_URL
    #         )
    #     if self.chromadb_client is None:
    #         self.chromadb_client = chromadb.PersistentClient(path=RAG_DB_PATH)
            
    def embed(self, text: str) -> List[float]:
        """生成文本的嵌入向量"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-v4",
                input=text,
                dimensions=1024,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding生成失败: {e}")
            return []

    def load_pdf(self, file_path: str) -> List[Document]:
        """加载PDF文件并返回文档列表"""
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.page_content = doc.page_content.replace('\n', ' ').strip()
            return docs
        except Exception as e:
            print(f"PDF加载失败: {e}")
            raise

    def split_documents(self, docs: list[Document],
                        chunk_size: int = 1000,
                        chunk_overlap: int = 200) -> list[Document]:
        """文档分块"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True
        )
        return text_splitter.split_documents(docs)
    
    def save_to_chroma(self, 
                      splits: List[Document], 
                      collection_name: str,
                      file_metadata: Optional[dict] = None) -> int:
        """保存文档分片到ChromaDB"""
        try:
            # 获取或创建集合
            collection = self.chromadb_client.get_or_create_collection(
                name=collection_name
            )
            
            chunk_count = 0
            for i, split in enumerate(splits):
                # 生成唯一ID
                doc_id = f"{collection_name}_{uuid.uuid4().hex}"
                
                # 准备元数据
                metadata = split.metadata.copy() if split.metadata else {}
                if file_metadata:
                    metadata.update(file_metadata)
                
                # 生成向量
                vector = self.embed(split.page_content)
                
                # 添加到集合
                collection.add(
                    ids=[doc_id],
                    documents=[split.page_content],
                    embeddings=[vector],
                    metadatas=[metadata]
                )
                chunk_count += 1
            
            logger.info(f"成功保存 {chunk_count} 个分片到集合 {collection_name}")
            return chunk_count
            
        except Exception as e:
            logger.error(f"保存到ChromaDB失败: {e}")
            raise

    def delete_collection(self, collection_name: str) -> bool:
        """删除ChromaDB集合"""
        try:
            self.chromadb_client.delete_collection(name=collection_name)
            logger.info(f"成功删除集合: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[dict]:
        """获取集合信息"""
        try:
            collection = self.chromadb_client.get_collection(name=collection_name)
            return {
                "name": collection_name,
                "count": collection.count(),
                "metadata": collection.metadata
            }
        except Exception:
            return None

# 全局处理器实例
document_processor = DocumentProcessor()

# rag_collections = {
#     "运维助手": chromadb_client.get_or_create_collection(name="devops_tool"),
#     "产品手册": chromadb_client.get_or_create_collection(name="product_manual")
# }

# def load_pdf(file_path: str) -> list[str]:
#     loader = PyPDFLoader(file_path)
#     docs = loader.load()
#     for doc in docs:
#         doc.page_content = doc.page_content.replace('\n', ' ')
#         # print(f"加载啊啊啊啊啊啊啊啊啊啊啊啊啊{doc}")
#     return docs

# def split_documents(docs: list[any]) -> list[any]:
#     text_splitter = RecursiveCharacterTextSplitter(
#         chunk_size=1000,
#         chunk_overlap=200,
#         add_start_index=True
#     )
#     all_splits = text_splitter.split_documents(docs)
#     return all_splits

# def embed(text: str) -> list[float]:
#     embedding = client.embeddings.create(
#         model="text-embedding-v4",
#         input=text,
#         dimensions=1024,
#         encoding_format="float"
#     )
#     return embedding.data[0].embedding

# def save_to_chroma(splits: list[Document], collection_name: str):
#     collection = rag_collections.get(collection_name)
#     if not collection:
#         return
    
#     for i, split in enumerate(splits):
#         vector = embed(split.page_content)
#         print(f"split=========={split}")
#         collection.add(
#             ids=str(i),
#             documents=[split.page_content],
#             embeddings=[vector],
#             metadatas=[split.metadata]
#         )

# def query_chroma(query: str, collection_name: str, n_results: int = 3) -> list[str]:
#     collection = rag_collections.get(collection_name)
#     if not collection:
#         return []
    
#     query_vector = embed(query)
#     results = collection.query(
#         query_embeddings=[query_vector],
#         n_results=n_results,
#     )
#     return results['documents'][0] if results else []

# if __name__ == "__main__":
#     # devops_file = ""
#     product_manual_path = "C:/Users/lzfdd/Desktop/备份软件缺陷管理.pdf"
#     docs = load_pdf(product_manual_path)
#     splits = split_documents(docs)
#     save_to_chroma(splits, "运维助手")
#     print("数据已保存到 ChromaDB")
#     print(f"集合记录数: {rag_collections['运维助手'].count()}")