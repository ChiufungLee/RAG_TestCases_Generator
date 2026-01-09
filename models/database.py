# app/models/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

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
    # MySQL 特定配置
    connect_args={
        "charset": "utf8mb4",  # 支持表情符号
        "connect_timeout": 10  # 连接超时时间
    },
    echo=False  # 设置为 True 可以看到 SQL 语句（调试用）
)

with engine.connect() as conn:
    print("Database connection successful!")

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 声明 ORM 基础类
Base = declarative_base()

# 数据库初始化
def init_db():
    """初始化数据库（创建表结构）"""
    Base.metadata.create_all(bind=engine)

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
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return False