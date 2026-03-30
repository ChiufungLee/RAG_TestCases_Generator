# AI 智能测试系统

这是一个基于 FastAPI + LangChain + RAG 的 AI 测试辅助平台。系统支持上传 PDF 知识库文档、进行向量检索，并结合大语言模型完成需求分析、测试点梳理、测试用例生成和产品问题排查等场景。

## 主要功能

- 基于知识库的测试用例生成
- 需求分析与测试策略设计
- 产品问题排查与用户手册阅读
- PDF 文档上传、预览、删除
- 多用户会话与知识库隔离

## 技术栈

- Python / FastAPI
- SQLAlchemy
- LangChain
- ChromaDB
- MySQL（默认） / SQLite（测试）
- JavaScript

## 使用的模型

- Embedding：阿里百炼 `text-embedding-v4`
- LLM：DeepSeek `deepseek-chat`

## 本地开发

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件，至少配置以下内容：

```env
# 应用环境
APP_ENV=development
SESSION_SECRET_KEY=dev-session-secret-change-me

# 数据库（二选一）
DATABASE_URL=
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=aitest_rag

# 模型配置
DEEPSEEK_API_KEY=your_deepseek_api_key
ALIYUN_API_KEY=your_aliyun_api_key
ALIYUN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 存储路径
RAG_DB_PATH=./chroma_db/local_rag_db
UPLOAD_DIR=./uploads
TEMP_UPLOAD_DIR=./temp_uploads
```

说明：

- 开发环境下，如果未设置 `DATABASE_URL`，应用会回退到 MySQL 配置拼接连接串。
- 生产环境下必须显式配置 `SESSION_SECRET_KEY`。
- 生产环境下如果未设置 `DATABASE_URL`，则 `MYSQL_PASSWORD` 不能保留默认值 `password`。

### 3. 启动应用

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问页面

- 首页：`http://localhost:8000/`
- 聊天页：`http://localhost:8000/chat`
- 知识库管理：`http://localhost:8000/knowledge`
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

## 测试

项目已补充 pytest 自动化测试，覆盖认证、权限、知识库文件链路、流式响应和后台处理竞态等关键路径。

运行全部测试：

```bash
pytest
```

运行单个测试文件：

```bash
pytest tests/test_auth.py
pytest tests/test_chat_authorization.py
pytest tests/test_knowledge_api.py
pytest tests/test_knowledge_background.py
pytest tests/test_retriever_authorization.py
pytest tests/test_llm_streaming.py
```

## 当前路由说明

- 页面路由：
  - `/login`
  - `/register`
  - `/chat`
  - `/knowledge`
  - `/knowledge-detail?kb_id=...`
- 主要 API 路由：
  - `/api/chat`
  - `/api/history`
  - `/api/conversation/...`
  - `/api/knowledge-bases/...`
  - `/api/files/{file_id}/preview`
  - `/logout`（POST）

## 项目结构

```text
api/
  api_v1.py
  endpoints/
main.py
models/
services/
static/
templates/
tests/
utils/
README.md
requirements.txt
```

## 后续可继续优化的方向

- 增加更多文档源支持（如 Word、Markdown、接口文档）
- 优化向量检索效果与召回速度
- 保存与版本化测试用例结果
- 对接外部测试管理工具
- 继续完善前端交互与错误提示
