import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# MySQL 数据库配置
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "aitest_rag")

# 构建 MySQL 连接 URL
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 创建引擎，配置连接池
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "charset": "utf8mb4",
        "connect_timeout": 10,
    },
    echo=False,
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# 声明 ORM 基础类
Base = declarative_base()


def _ensure_schema_updates():
    """补齐当前版本需要的轻量 schema 变更。"""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "knowledge_bases" not in table_names:
        return

    column_names = {column["name"] for column in inspector.get_columns("knowledge_bases")}
    index_names = {index["name"] for index in inspector.get_indexes("knowledge_bases")}

    with engine.begin() as conn:
        if "owner_user_id" not in column_names:
            conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN owner_user_id INTEGER NULL"))

        if "ix_knowledge_bases_owner_user_id" not in index_names:
            conn.execute(text("CREATE INDEX ix_knowledge_bases_owner_user_id ON knowledge_bases (owner_user_id)"))


# 数据库初始化

def init_db():
    """初始化数据库（创建表结构并补齐必要字段）"""
    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()


# 数据库依赖注入

def get_db():
    """
    获取数据库会话的依赖函数
    在 FastAPI 路由中使用 Depends(get_db) 来注入数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 数据库连接健康检查

def check_database_connection():
    """检查数据库连接是否正常"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("数据库连接失败: %s", e, exc_info=True)
        return False
