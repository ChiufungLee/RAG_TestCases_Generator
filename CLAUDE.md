# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

AI 智能测试系统，基于 FastAPI + LangChain + RAG 构建。支持上传 PDF 知识库文档、通过 ChromaDB 进行向量检索，并借助大语言模型完成需求分析、测试用例生成和产品问题排查。

## 虚拟环境

项目使用根目录下的 `fastapi_venv/` 虚拟环境。请始终使用 venv 中的 Python 和 pip：
```bash
fastapi_venv/Scripts/python.exe   # Python 解释器
fastapi_venv/Scripts/pip.exe      # pip
```

## 常用命令

### 启动应用
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 安装依赖
```bash
fastapi_venv/Scripts/pip.exe install -r requirements.txt
```

### 运行测试
```bash
fastapi_venv/Scripts/pytest.exe tests/                                       # 全部测试
fastapi_venv/Scripts/pytest.exe tests/test_auth.py                          # 单个文件
fastapi_venv/Scripts/pytest.exe tests/test_auth.py::test_register_hashes_password  # 单个用例
fastapi_venv/Scripts/pytest.exe tests/test_chat_authorization.py -k "test_user_cannot_read"  # 按名称筛选
```

项目中暂无 linting 配置。

## 架构

### 应用工厂与生命周期
`main.py` 中的 `create_app()` 初始化 FastAPI，并通过 `lifespan` 在启动时调用 `init_db()`。会话中间件（Starlette `SessionMiddleware`，基于签名 Cookie）处理认证状态。

### 路由（main.py 中注册了 4 个路由）
- `auth.router`（`api/endpoints/auth.py`）— `/login`、`/register`、`/logout`、`/`（首页）
- `chat.app`（`api/endpoints/chat.py`）— `/chat`、`/api/chat`（SSE 流式响应）、`/api/history`、`/api/conversation/...`
- `kb.app`（`api/endpoints/knowledg_api.py`）— `/api/knowledge-bases/...`、`/api/files/...`
- `api_router`（`api/api_v1.py`）— 聚合 `func.router`，提供 `/knowledge` 页面

### 数据库
SQLAlchemy 2.0 + `declarative_base()`。`models/database.py` 根据环境变量构建数据库连接 URL（默认 MySQL，当 `DATABASE_URL` 包含 `sqlite` 时使用 SQLite）。`init_db()` 执行 `create_all()` 外加 `_ensure_schema_updates()` 中的轻量级 schema 迁移。`get_db()` 是 FastAPI 的数据库会话依赖注入。

### 数据模型（models/）
- **User** — `id`、`username`、`password`（bcrypt 哈希）、`created_at`、`last_login_at`
- **Conversation** — UUID 主键、`user_id` 外键、`title`、`scenario`、`knowledge_base_id` 外键（可空）
- **Message** — `conversation_id` 外键、`role`（user/assistant/system）、`content`、`timestamp`
- **KnowledgeBase** — UUID 主键、`owner_user_id` 外键、`collection_name`（ChromaDB 唯一集合名）、`file_count`、`visibility`（private/shared）
- **KnowledgeFile** — UUID 主键、`knowledge_base_id` 外键、`status`（pending/processing/completed/failed）

### 服务层（services/）
无状态的静态方法类。`AuthService` 处理注册、登录、bcrypt 哈希和会话读写。`ChatService` 管理对话和消息。`knowledge_service` 负责知识库 CRUD、文件上传及后台处理、ChromaDB 清理。

### Schema 层（schemas/）
用于请求/响应校验的 Pydantic 模型：`KnowledgeBaseCreate`、`KnowledgeBaseUpdate`、`KnowledgeBaseResponse`、`KnowledgeFileResponse`。

### RAG 流水线（utils/）
PDF 上传后作为后台任务进行解析，采用三级加载策略：

1. **首选方案**：`unstructured.partition_pdf`（fast 策略）+ `chunk_by_title`（最大 1500 字符，500 字符合并阈值，100 重叠）→ 超过 2000 字符的块再用 `RecursiveCharacterTextSplitter` 二次分割
2. **回退方案**：`PyPDFLoader` + `RecursiveCharacterTextSplitter`（1000 字符，200 重叠）— 当 unstructured 未能提取到内容时使用
3. **OCR 方案**：`unstructured.partition_pdf`（hi_res 策略）— 针对图片型 PDF

向量化使用阿里云百炼 `text-embedding-v4`（1024 维），存储于 ChromaDB `PersistentClient`。

关键文件：
- `utils/file_handle.py` — `DocumentProcessor`：PDF 加载、向量嵌入、ChromaDB 存储/删除
- `utils/retriever.py` — `ChromaRetriever`：查询向量化、基于 L2 距离阈值（1.2）的向量检索，以及带线程锁的 `_retriever_cache` 字典，用于按知识库 ID 缓存检索器
- `utils/llm_handle.py` — 通过 LangChain `init_chat_model` 调用 DeepSeek `deepseek-chat`，SSE 流式响应，新对话自动生成标题
- `utils/data_handle.py` — Markdown 表格提取与测试用例 CSV 导出

### 提示词（prompts/prompts.py）
每个对话场景对应一个 `PromptTemplate`，包含 `system_template`、`user_template` 和 `temperature`。共四个场景，每个场景都有一个 `_plain` 变体用于未选择知识库时：
- `requirement_analysis` / `requirement_analysis_plain`（温度 0.4）
- `testcase_generation` / `testcase_generation_plain`（温度 0.3）
- `devops_tool` / `devops_tool_plain`
- `product_manual` / `product_manual_plain`

工具类提示词：`title_generation`（0.3）、`history_summary`（0.3）。

`get_prompt_messages()` 构建结构化消息列表：`[SystemMessage, ...历史消息, HumanMessage(上下文 + 问题)]`。

### 认证
基于 Session。`user_id`/`username` 存储在 `request.session` 中。API 端点使用 `AuthService.get_optional_request_user_id(request)`，未认证时返回 401 JSON。页面路由重定向到 `/login`。

### 前端
Jinja2 模板位于 `templates/`。JS/CSS 位于 `static/`。无前端构建步骤 — 纯原生 JavaScript。

## 配置

所有配置通过 `.env` 文件加载，由 `config.py` 中的 `python-dotenv` 读取。关键变量：`DATABASE_URL`、`SESSION_SECRET_KEY`、`DEEPSEEK_API_KEY`、`ALIYUN_API_KEY`、`ALIYUN_BASE_URL`、`RAG_DB_PATH`、`UPLOAD_DIR`。

生产环境：`SESSION_SECRET_KEY` 必须设置，`MYSQL_PASSWORD` 不得使用默认值。

## 测试

测试使用 `pytest` + `pytest-asyncio`。`test_env` 夹具在 `tmp_path` 中创建隔离的 SQLite 数据库，并重置所有模块级缓存状态（`reset_database`、`reset_document_processor_state`、`reset_retriever_state`、`reset_llm_state`）。`stub_external_dependencies` 夹具将 ChromaDB、OpenAI 客户端、embedding 和 PDF 加载替换为桩实现，确保测试不依赖外部服务。

关键夹具：`client`（TestClient）、`logged_in_client`（以 "alice" 身份预认证）、`db_session`、`make_user`、`make_conversation`、`make_knowledge_base`、`make_knowledge_file`。

异步测试（检索器、LLM 流式）使用 `@pytest.mark.asyncio`。

## 重要注意事项

- `api/`、`models/`、`schemas/`、`services/`、`tests/` 目录下均无 `__init__.py` 文件。导入之所以能正常工作，是因为 `pytest.ini` 中设置了 `pythonpath = .`。
- `requirements.txt` 为 UTF-16 编码（历史遗留问题）。
- KnowledgeBase 具有 `visibility` 字段（"private"/"shared"）— 共享知识库对所有已认证用户可见。服务方法中的 `allow_shared_read=True` 参数用于启用此行为。
