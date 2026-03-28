import logging
import os
import uuid
from typing import List, Optional

import chromadb
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

# 配置日志
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
    base_url=ALIYUN_BASE_URL,
)

# 初始化 ChromaDB 客户端
chromadb_client = chromadb.PersistentClient(path=RAG_DB_PATH)


class DocumentProcessor:
    def __init__(self):
        self.client = client
        self.chromadb_client = chromadb_client

    def embed(self, text: str) -> List[float]:
        """生成文本的嵌入向量"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-v4",
                input=text,
                dimensions=1024,
                encoding_format="float",
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Embedding生成失败: %s", e, exc_info=True)
            return []

    def load_pdf(self, file_path: str) -> List[Document]:
        """加载PDF文件并返回文档列表"""
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.page_content = doc.page_content.replace("\n", " ").strip()
            return docs
        except Exception as e:
            logger.error("PDF加载失败: %s", e, exc_info=True)
            raise

    def split_documents(
        self,
        docs: list[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[Document]:
        """文档分块"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )
        return text_splitter.split_documents(docs)

    def save_to_chroma(
        self,
        splits: List[Document],
        collection_name: str,
        file_metadata: Optional[dict] = None,
    ) -> int:
        """保存文档分片到ChromaDB"""
        try:
            collection = self.chromadb_client.get_or_create_collection(name=collection_name)

            chunk_count = 0
            for split in splits:
                doc_id = f"{collection_name}_{uuid.uuid4().hex}"

                metadata = split.metadata.copy() if split.metadata else {}
                if file_metadata:
                    metadata.update(file_metadata)

                vector = self.embed(split.page_content)
                if not vector:
                    continue

                collection.add(
                    ids=[doc_id],
                    documents=[split.page_content],
                    embeddings=[vector],
                    metadatas=[metadata],
                )
                chunk_count += 1

            logger.info("成功保存 %s 个分片到集合 %s", chunk_count, collection_name)
            return chunk_count

        except Exception as e:
            logger.error("保存到ChromaDB失败: %s", e, exc_info=True)
            raise

    def delete_collection(self, collection_name: str) -> bool:
        """删除ChromaDB集合"""
        try:
            self.chromadb_client.delete_collection(name=collection_name)
            logger.info("成功删除集合: %s", collection_name)
            return True
        except Exception as e:
            logger.error("删除集合失败: %s", e, exc_info=True)
            return False

    def get_collection_info(self, collection_name: str) -> Optional[dict]:
        """获取集合信息"""
        try:
            collection = self.chromadb_client.get_collection(name=collection_name)
            return {
                "name": collection_name,
                "count": collection.count(),
                "metadata": collection.metadata,
            }
        except Exception as e:
            logger.error("获取集合信息失败: %s", e, exc_info=True)
            return None


# 全局处理器实例
document_processor = DocumentProcessor()
