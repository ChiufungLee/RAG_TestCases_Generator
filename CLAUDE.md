# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered testing assistant platform (AI 智能测试系统) built with FastAPI + LangChain + RAG. Supports uploading PDF knowledge bases, vector retrieval via ChromaDB, and LLM-driven requirement analysis, test case generation, and product troubleshooting.

## Commands

### Run the app
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run tests
```bash
pytest                                          # all tests
pytest tests/test_auth.py                       # single file
pytest tests/test_auth.py::test_register_hashes_password  # single test
pytest tests/test_chat_authorization.py -k "test_user_cannot_read"  # by name
```

No linting configuration exists in this project.

## Architecture

### App Factory & Lifecycle
`main.py` contains `create_app()` which initializes FastAPI with a `lifespan` that calls `init_db()` on startup. Session middleware (signed cookies via Starlette `SessionMiddleware`) handles auth state.

### Routing (4 routers registered in main.py)
- `auth.router` (`api/endpoints/auth.py`) — `/login`, `/register`, `/logout`, `/` (home page)
- `chat.app` (`api/endpoints/chat.py`) — `/chat`, `/api/chat` (SSE streaming), `/api/history`, `/api/conversation/...`
- `kb.app` (`api/endpoints/knowledg_api.py`) — `/api/knowledge-bases/...`, `/api/files/...`
- `api_router` (`api/api_v1.py`) — aggregates `func.router` for `/knowledge` page

### Database
SQLAlchemy 2.0 with `declarative_base()`. `models/database.py` builds the connection URL from env vars (MySQL by default, SQLite when `DATABASE_URL` contains `sqlite`). `init_db()` runs `create_all()` plus lightweight schema migrations via `_ensure_schema_updates()`. `get_db()` is the FastAPI dependency for DB sessions.

### Models (models/)
- **User** — `id`, `username`, `password` (bcrypt hash)
- **Conversation** — UUID PK, `user_id` FK, `title`, `scenario`, `knowledge_base_id` FK (nullable)
- **Message** — `conversation_id` FK, `role` (user/assistant/system), `content`, `timestamp`
- **KnowledgeBase** — UUID PK, `owner_user_id` FK, `collection_name` (unique ChromaDB collection), `file_count`
- **KnowledgeFile** — UUID PK, `knowledge_base_id` FK, `status` (pending/processing/completed/failed)

### Services (services/)
Stateless classes with static methods. `AuthService` handles registration, login, bcrypt hashing, and session read/write. `ChatService` manages conversations and messages. `knowlege_service` (note: typo in filename) handles KB CRUD, file upload with background processing, and ChromaDB cleanup.

### RAG Pipeline
1. PDF upload → background task: `PyPDFLoader` → `RecursiveCharacterTextSplitter` (1000 chars, 200 overlap) → Aliyun `text-embedding-v4` (1024 dims) → ChromaDB collection
2. Chat with KB selected: embed query → ChromaDB vector search → inject context into prompt → DeepSeek `deepseek-chat` → SSE stream response

### Prompts (prompts/prompts.py)
Each chat scenario has two prompt variants: one with RAG context, a `_plain` variant without. Scenarios: `requeirement_analysis`, `testcase_generation`, `devops_tool`, `product_manual`.

### Authentication
Session-based. `user_id`/`username` stored in `request.session`. API endpoints use `AuthService.get_optional_request_user_id(request)` returning 401 JSON if unauthenticated. Page routes redirect to `/login`.

### Frontend
Jinja2 templates in `templates/`. JS/CSS in `static/`. No frontend build step — plain vanilla JS.

## Configuration

All config via `.env` file loaded by `python-dotenv` in `config.py`. Key variables: `DATABASE_URL`, `SESSION_SECRET_KEY`, `DEEPSEEK_API_KEY`, `ALIYUN_API_KEY`, `ALIYUN_BASE_URL`, `RAG_DB_PATH`, `UPLOAD_DIR`.

In production: `SESSION_SECRET_KEY` is required, `MYSQL_PASSWORD` must not be the default.

## Testing

Tests use `pytest` + `pytest-asyncio`. The `test_env` fixture creates an isolated SQLite DB in `tmp_path` and resets all module-level cached state (`reset_database`, `reset_document_processor_state`, `reset_retriever_state`, `reset_llm_state`). The `stub_external_dependencies` fixture replaces ChromaDB, OpenAI client, embeddings, and PDF loading with dummies so tests run without external services.

Key fixtures: `client` (TestClient), `logged_in_client` (pre-authenticated as "alice"), `db_session`, `make_user`, `make_conversation`, `make_knowledge_base`, `make_knowledge_file`.

Async tests (retriever, LLM streaming) use `@pytest.mark.asyncio`.

## Important Notes

- No `__init__.py` files exist in `api/`, `models/`, `schemas/`, `services/`, or `tests/`. Imports work because `pytest.ini` sets `pythonpath = .`.
- `requirements.txt` is UTF-16 encoded (legacy issue).
- The file `services/knowlege_service.py` has a typo in its name ("knowlege" instead of "knowledge").
