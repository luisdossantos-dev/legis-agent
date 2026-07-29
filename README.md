# ⚖️ Legis Agent

**AI Agents for Legal Document Analysis & Drafting**

Desktop AI Agent system for legal/notarial document analysis and drafting. Combines a **Python (FastAPI + LangGraph + RAG)** backend with a **Rust + Tauri** desktop GUI and a **React + TypeScript** frontend.

🌐 **Bilingual UI** — Switch between **English** and **French** at any time via the language selector. The interface updates instantly without reload.

☀️ **Light theme by default** — Toggle between light and dark themes via the header button. Preference persists in localStorage.

📖 **[Full Documentation](/#)** — Built-in Docs view explains every feature with step-by-step guides.

---

## Features

### User Interface
| Feature | Description |
|---------|-------------|
| **Sidebar Navigation** | Quick access to all views (Email, Classify, Actions, Review, Pipeline, Dashboard, Users, Docs) |
| **Command Palette** | `Ctrl+K` — search and execute commands without leaving the keyboard |
| **Keyboard Shortcuts** | `Ctrl+U` upload, `Ctrl+1-7` navigate, `Ctrl+,` settings, `Esc` close |
| **Light/Dark Mode** | Toggle themes from the header — light is the default |
| **Bilingual (EN/FR)** | Full English and French translations, reactive instant switch |
| **Responsive Layout** | Adapts from full desktop to narrow windows |
| **Toast Notifications** | Feedback for operations, indexing completion, warnings, and errors |
| **Skeleton Loading** | Shimmer placeholders during analysis, chat, and pipeline execution |
| **Confirmation Dialogs** | Before long-running pipeline operations |

### Document Processing
| Feature | Description |
|---------|-------------|
| **Upload & Parse** | PDF, DOCX, TXT — automatic text extraction with magic-byte validation |
| **Semantic Chunking** | French notarial structure detection (articles, titres, chapitres) |
| **Background Indexing** | Async vector embedding for instant RAG retrieval |
| **Indexing Notifications** | Toast on completion: green for success, red for errors |

### RAG Pipeline
| Feature | Description |
|---------|-------------|
| **Hybrid Search** | BM25 keyword + semantic cosine similarity with RRF fusion |
| **Cross-encoder Reranking** | Re-ranks top-20 results with transformer model |
| **MMR Diversity** | Maximum Marginal Relevance to avoid redundant chunks |
| **Query Expansion** | LLM generates 2-3 query variations for broader retrieval |
| **Dynamic top_k + Compression** | Adjusts chunk count based on query complexity |
| **Multi-embedding Provider** | fastembed (local ONNX), OpenAI, or mock |
| **French Notarial Chunking** | 15+ section patterns for French legal documents |

### LLM Routing
| Feature | Description |
|---------|-------------|
| **Multi-Provider** | OpenAI, Anthropic, Google, DeepSeek, Mistral, Groq, OpenRouter, custom endpoints |
| **Profile-Based** | `fast` for simple queries, `reasoning` for complex analysis, `cheap` for cost-sensitive |
| **SSE Streaming** | First token in ~1-3s via Server-Sent Events |
| **Semantic Caching** | Repeated queries return instantly (TTL-based) |
| **Circuit Breaker** | Auto-fallback on provider failures |
| **Cost Guards** | Per-call cost estimation with monthly projections |

### Agent Workflows
| Feature | Description |
|---------|-------------|
| **Document Analysis** | Retrieve → analyze → structured report |
| **Multi-Step Pipeline** | Configurable: extract → analyze → review → draft → send |
| **Pipeline Presets** | Quick templates: Full Analysis, Quick Extract, Analyze + Draft, Review + Send |
| **Step Reordering** | Reorder pipeline steps with ◀ ▶ buttons, visual flow diagram |
| **Execution Indicator** | Current step highlighted in green with elapsed timer |
| **Chat** | Multi-turn conversation with RAG context |
| **Streaming Chat** | Token-by-token real-time responses |

### Email Tools
| Feature | Description |
|---------|-------------|
| **Smart Drafting** | Template-based email generation with RAG context |
| **Document → Email** | Select a document and generate a context-aware email |
| **Classification** | Hybrid embedding + LLM email categorization (6 categories) |
| **Action Detection** | Detect and execute actions from emails (reply, forward, schedule) |
| **Multi-Language** | Generate emails in ES, EN, FR, PT |

### Security & Compliance
| Feature | Description |
|---------|-------------|
| **RBAC** | Role-based access (admin, notaire, assistant, stagiaire) |
| **GDPR Audit Trail** | Every interaction logged with user, action, timestamp |
| **Right to Erasure** | GDPR Article 17 — user data anonymization |
| **Data Portability** | GDPR Article 20 — full user data export |
| **Prompt Injection Detection** | Security scanning of user inputs |
| **Rate Limiting** | Per-role API call limits (200/min admin, 20/min stagiaire) |
| **Sensitive Data Routing** | PII detection for GDPR-compliant provider selection |

### Observability & Cost Tracking
| Feature | Description |
|---------|-------------|
| **Usage Dashboard** | Token usage, cost (user-configurable price/M tokens), latency, errors |
| **Configurable Pricing** | Set your own price per million tokens — costs calculate locally |
| **Token Breakdown** | Input/output tokens per provider |
| **Daily Charts** | 30-day cost and call history with Chart.js |
| **Langfuse Tracing** | Full trace trees for agent executions (optional) |
| **Prometheus Metrics** | `/metrics` endpoint for scraping |

---

## Quick Start

```bash
# One command — installs everything and launches the app:
./start.sh

# Or manually:
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload &

cd frontend && npm install && npm run dev &
```

---

## Architecture

```
legis-agent/
├── backend/                  # Python FastAPI server (port 8000)
│   ├── app/
│   │   ├── api/              # 20 route modules (documents, agents, email, etc.)
│   │   ├── agents/           # LangGraph agent pipelines
│   │   ├── core/             # Auth, config, security, caching, observability
│   │   ├── rag/              # Chunking, embeddings, retrieval, reranking
│   │   ├── models/           # Pydantic schemas
│   │   ├── services/         # Business logic layer
│   │   └── ingestion/        # Parser (PDF, DOCX, TXT)
│   └── tests/                # 18 test files, 196 tests
├── frontend/                 # React + TypeScript + Vite (port 1420)
│   └── src/
│       ├── components/       # 18 React components
│       ├── api/              # API client
│       └── i18n.ts           # EN/FR translations
├── src-tauri/                # Tauri 2 (Rust desktop wrapper)
├── docs/                     # Rollback plan & documentation
└── LICENSE                   # MIT License
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12+, FastAPI, Pydantic, LiteLLM, LangGraph |
| **Vector Store** | pgvector (PostgreSQL), optional Pinecone/Qdrant |
| **RAG** | BM25, cross-encoder reranking, MMR, query expansion |
| **Frontend** | React 18, TypeScript, Vite, Chart.js |
| **Desktop** | Tauri 2 (Rust) |
| **Testing** | pytest (196 tests, 10s suite), ruff, mypy |

## API Reference

All routes are under `http://localhost:8000/api/v1/`:

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/documents/upload` | Upload PDF/DOCX/TXT (multipart) |
| `GET` | `/documents/` | List documents (paginated) |
| `GET` | `/documents/{id}` | Get document metadata |
| `POST` | `/agents/analyze` | Run full analysis pipeline |
| `POST` | `/agents/chat` | Multi-turn chat |
| `POST` | `/agents/chat/stream` | SSE streaming chat |
| `POST` | `/agents/pipeline` | Run configurable multi-step pipeline |
| `GET` | `/system/config` | LLM provider configuration |
| `POST` | `/system/config` | Update configuration |
| `POST` | `/email/draft` | Generate email draft |
| `POST` | `/email/classify` | Classify email |
| `POST` | `/email/action` | Detect email action |
| `POST` | `/clauses/review` | Review notarial clause |
| `POST` | `/acts/generate` | Generate notarial act |
| `POST` | `/deeds/draft-clause` | Draft deed clause |
| `POST` | `/cases/process` | Process document into case |
| `GET` | `/cases/stats` | Case statistics |
| `GET` | `/observability/stats` | Dashboard usage data |
| `GET` | `/observability/dashboard` | HTML dashboard |

---

## Testing

```bash
cd backend
pytest -v                                    # Full suite (196 tests, ~10s)
pytest tests/unit/ -v                        # Unit tests (cache, chunker, routing, etc.)
pytest tests/test_api.py -v                  # API endpoint tests
pytest tests/test_rbac.py -v                 # RBAC & auth tests
```

**Test status:** 196 tests — all passing, 0 warnings, ~10s runtime.

| Category | Tests | Status |
|----------|-------|--------|
| Smoke (health, imports) | 4 | ✅ |
| API (upload, analyze, config) | 9 | ✅ |
| RAG (chunker) | 4 | ✅ |
| RBAC (auth, users, audit) | 23 | ✅ |
| Unit — Cache | 10 | ✅ |
| Unit — Chunker | 18 | ✅ |
| Unit — Context Optimizer | 40 | ✅ |
| Unit — Security | 20 | ✅ |
| Unit — Routing | 8 | ✅ |
| Unit — Infrastructure | 8 | ✅ |
| Unit — Router Factory | 27 | ✅ |
| Unit — Retriever (pure) | 13 | ✅ |
| Unit — Query Expansion | 8 | ✅ |

---

## Configuration

Key environment variables (see `backend/.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_API_KEY` | — | API key for LLM provider |
| `LITELLM_MODEL` | `openai/gpt-4o` | Primary model |
| `ADMIN_PASSWORD` | auto-generated | Default admin password |
| `ENABLE_HEADER_AUTH` | `false` | Dev header auth |
| `VECTOR_STORE_PROVIDER` | `pgvector` | Vector DB provider |

---

## License

MIT — see [LICENSE](./LICENSE) for the full text.

Copyright (c) 2025 Luis Daniel Dos Santos

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
