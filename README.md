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

- LLM：由 `LLM_*` 配置决定，当前示例使用 DeepSeek `deepseek-v4-flash`
- Embedding：由 `EMBEDDING_*` 配置决定，当前示例使用阿里百炼 `text-embedding-v4`

LLM 和 Embedding 使用独立的配置、凭证和模型参数。文档入库与查询检索必须使用同一套 Embedding 模型和向量维度；如果修改 `EMBEDDING_MODEL` 或 `EMBEDDING_DIMENSIONS`，需要评估并重建已有 Chroma 向量集合。

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

# LLM 配置
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_CONNECT=10
LLM_TIMEOUT_READ=120
LLM_TIMEOUT_WRITE=30
LLM_TIMEOUT_POOL=10
LLM_MAX_RETRIES=2

# Embedding 配置
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_API_KEY=your_embedding_api_key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_DIMENSIONS=1024
EMBEDDING_ENCODING_FORMAT=float

# Chroma 配置
CHROMA_DISTANCE_METRIC=l2

# Retriever 配置
RETRIEVER_TOP_K=5
RETRIEVER_CANDIDATE_K=10
RETRIEVER_ENABLE_DISTANCE_FILTER=false
RETRIEVER_DISTANCE_THRESHOLD=

# 存储路径
RAG_DB_PATH=./chroma_db/local_rag_db
UPLOAD_DIR=./uploads
TEMP_UPLOAD_DIR=./temp_uploads
```

说明：

- 开发环境下，如果未设置 `DATABASE_URL`，应用会回退到 MySQL 配置拼接连接串。
- 生产环境下必须显式配置 `SESSION_SECRET_KEY`。
- 生产环境下如果未设置 `DATABASE_URL`，则 `MYSQL_PASSWORD` 不能保留默认值 `password`。
- `LLM_MAX_TOKENS` 会传递给 LangChain ChatModel，限制 LLM 的最大输出 token 数；标题生成会单独使用 50 个 token。
- `LLM_TIMEOUT_*` 的单位是秒，分别控制连接、读取、写入和连接池超时；`LLM_MAX_RETRIES` 控制 LLM 请求重试次数。
- `EMBEDDING_DIMENSIONS` 必须与已写入 Chroma 集合的向量维度一致。
- `RETRIEVER_TOP_K` 是最终返回的文档数量，`RETRIEVER_CANDIDATE_K` 是初始召回数量。
- `RETRIEVER_ENABLE_DISTANCE_FILTER` 为 `true` 且设置了 `RETRIEVER_DISTANCE_THRESHOLD` 时，才会启用距离阈值过滤。
- 模型配置优先使用上述 `LLM_*` 和 `EMBEDDING_*` 变量；旧版 `DEEPSEEK_API_KEY`、`ALIYUN_API_KEY` 和 `ALIYUN_BASE_URL` 可作为 API 凭证和地址的兼容回退配置。

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
