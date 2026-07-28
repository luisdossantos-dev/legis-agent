# ⚖️ Legis Agent

**AI Agents for Legal Document Analysis & Drafting**

Desktop AI Agent system for legal/notarial document analysis and drafting. Combines a **Python (FastAPI + LangGraph + RAG)** backend with a **Rust + Tauri** desktop GUI and a **React + TypeScript** frontend.

🌙 **Dark & Light mode** — Toggle between dark and light themes via the header button. Preference is saved in your browser.

🌐 **Bilingual UI** — Switch between **English** and **French** at any time via the language selector. All user-facing strings are fully translated.

---

## ✨ Features

### 🎨 User Interface
| Feature | Description |
|---------|-------------|
| **🌙 Dark / ☀️ Light Mode** | Toggle themes from the header — persists in localStorage |
| **🌐 Bilingual (EN/FR)** | English and French translations for all user-facing strings |
| **Responsive Layout** | Adapts from full desktop to narrow windows gracefully |
| **Toast Notifications** | Non-intrusive feedback for operations, warnings, and errors |
| **Keyboard Navigation** | Full keyboard support for all interactive elements |
| **Skeleton Loading** | Shimmer placeholders during analysis and chat responses |

### 📄 Document Processing
| Feature | Description |
|---------|-------------|
| **Upload & Parse** | PDF, DOCX, TXT — automatic text extraction |
| **Semantic Chunking** | French notarial structure detection (titres, chapitres, alinéas) |
| **Background Indexing** | Async vector embedding for instant RAG retrieval |

### 🧠 RAG Pipeline
| Feature | Description |
|---------|-------------|
| **Hybrid Search** | BM25 keyword + semantic cosine similarity with RRF fusion |
| **Cross-encoder Reranking** | Re-ranks top-20 results with transformer model |
| **MMR Diversity** | Maximum Marginal Relevance to avoid redundant chunks |
| **Query Expansion** | LLM generates 2-3 query variations for broader retrieval |
| **Dynamic top_k + Compression** | Adjusts chunk count based on query complexity |
| **Multi-embedding Provider** | fastembed (local ONNX), OpenAI, or mock |
| **French Notarial Chunking** | 15+ section patterns for French legal documents |

### 🤖 LLM Routing
| Feature | Description |
|---------|-------------|
| **Multi-Provider** | OpenAI, Anthropic, Google, DeepSeek, Mistral, Groq, OpenRouter, custom endpoints |
| **Profile-Based** | `fast` for simple queries, `reasoning` for complex analysis, `cheap` for cost-sensitive |
| **SSE Streaming** | First token in ~1-3s via Server-Sent Events |
| **Semantic Caching** | Repeated queries return instantly (TTL-based) |
| **Circuit Breaker** | Auto-fallback on provider failures |
| **Cost Guards** | Per-call cost estimation with monthly projections |

### 🔗 Agent Workflows
| Feature | Description |
|---------|-------------|
| **Document Analysis** | Retrieve → analyze → structured report |
| **Multi-Step Pipeline** | Configurable: extract → analyze → review → draft → send |
| **Supervisor Routing** | Auto-selects steps based on document type |
| **Chat** | Multi-turn conversation with RAG context |
| **Streaming Chat** | Token-by-token real-time responses |
| **Document → Email** | Select a document and generate a context-aware email |

### 📧 Email Tools
| Feature | Description |
|---------|-------------|
| **Smart Drafting** | Template-based email generation with RAG context |
| **Document → Email** | Select a document and generate a context-aware email with one click |
| **Classification** | Hybrid embedding + LLM email categorization (6 categories) |
| **Action Detection** | Detect and execute actions from emails (reply, forward, schedule) |
| **Multi-Language** | Generate emails in ES, EN, FR, PT |

### 🔐 Security & Compliance
| Feature | Description |
|---------|-------------|
| **RBAC** | Role-based access (admin, notaire, assistant, stagiaire) |
| **GDPR Audit Trail** | Every interaction logged with user, action, timestamp |
| **Right to Erasure** | GDPR Article 17 — user data anonymization |
| **Data Portability** | GDPR Article 20 — full user data export |
| **Prompt Injection Detection** | Security scanning of user inputs |
| **Rate Limiting** | Per-role API call limits (200/min admin, 20/min stagiaire) |
| **Sensitive Data Routing** | PII detection for GDPR-compliant provider selection |

### 📊 Observability & Cost Tracking
| Feature | Description |
|---------|-------------|
| **Interactive Dashboard** | Chart.js cost/day, model usage, latency distribution |
| **HTML Dashboard** | Self-contained offline dashboard at `/observability/dashboard` |
| **Langfuse Tracing** | Full trace trees for agent executions (optional) |
| **Prometheus Metrics** | `/metrics` endpoint for scraping |
| **Cost Estimation** | Per-call cost tracking with monthly projections |
| **Performance Profiling** | Automatic slow-request detection (>5s warning, >30s critical) 🐢

### 🧪 CI & Evaluation
| Feature | Description |
|---------|-------------|
| **Promptfoo Suite** | 21 tests across 8 categories (RAG, security, latency, etc.) |
| **Regression Testing** | Baseline comparison rejects PRs with quality drops |
| **GitHub Actions** | Backend tests, frontend build, and eval workflow |
| **Quality Gates** | Accuracy ≥85%, cost <$0.10 increase, latency <5s P95 increase |

---

## 🚀 Quick Start

```bash
# One command — installs everything and launches the app:
./start.sh

# Or manually:
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload &

cd frontend && npm install && npm run dev &

cd src-tauri && cargo tauri dev
```

### Options
```
1  →  Full Desktop GUI (Tauri + Frontend + Backend)
2  →  Backend only (API on localhost:8000)
3  →  Frontend only (React on localhost:1420)
4  →  Run backend tests
```

---

## 🏗️ Architecture

```
legis-agent/
├── backend/                  # Python FastAPI
│   ├── app/
│   │   ├── api/              # REST endpoints
│   │   │   ├── agents.py     # Analyze, chat, pipeline
│   │   │   ├── documents.py  # Upload, list, get
│   │   │   ├── email.py      # Draft emails
│   │   │   ├── email_classifier.py
│   │   │   ├── email_action.py
│   │   │   ├── clause_review.py
│   │   │   ├── deeds.py      # Clause drafting
│   │   │   ├── act_generation.py
│   │   │   ├── rbac.py       # Users, auth, GDPR
│   │   │   ├── system.py     # Config, logs
│   │   │   └── observability.py
│   │   ├── agents/           # LangGraph state machines
│   │   │   ├── graph.py      # Main pipeline orchestrator
│   │   │   ├── analyzer.py   # Document analysis
│   │   │   ├── drafter.py    # Response drafting
│   │   │   ├── email_drafter.py
│   │   │   ├── act_generator.py
│   │   │   ├── clause_reviewer.py
│   │   │   ├── deed_drafter.py
│   │   │   ├── action_graph.py
│   │   │   └── conversation_graph.py
│   │   ├── rag/              # Retrieval-Augmented Generation
│   │   │   ├── retriever.py  # Hybrid search + MMR
│   │   │   ├── chunker.py    # French notarial chunking
│   │   │   ├── reranker.py   # Cross-encoder reranking
│   │   │   ├── embeddings.py # Multi-provider embeddings
│   │   │   ├── query_expansion.py
│   │   │   ├── context_optimizer.py
│   │   │   └── email_templates.py
│   │   ├── core/             # Shared infrastructure
│   │   │   ├── llm.py        # LLM calls + streaming
│   │   │   ├── router_factory.py  # LiteLLM multi-model router
│   │   │   ├── runtime_config.py  # API key persistence
│   │   │   ├── auth.py       # RBAC authentication
│   │   │   ├── gdpr.py       # Audit trail
│   │   │   ├── rate_limit.py # Per-role rate limiting
│   │   │   ├── security.py   # Prompt injection detection
│   │   │   ├── observability.py   # Metrics, cost tracking
│   │   │   ├── langfuse.py   # Langfuse tracing
│   │   │   ├── profiler.py   # Slow request detection
│   │   │   └── cache.py      # TTL caching
│   │   ├── services/         # Business logic
│   │   │   └── document_service.py
│   │   ├── models/           # Pydantic schemas
│   │   └── ingestion/        # Document parsing
│   ├── tests/                # Test suite (10 dimensions)
│   │   ├── unit/             # Unit tests
│   │   ├── integration/      # Integration tests
│   │   ├── contract/         # API contract tests
│   │   ├── property/         # Property-based (Hypothesis)
│   │   ├── fault/            # Fault injection tests
│   │   └── ...               # Smoke, edge, regression, mutation, benchmark
│   ├── config/               # Runtime config (persisted)
│   └── prompts/              # Custom prompts
├── frontend/                 # React 18 + TypeScript + Vite 6
│   └── src/
│       ├── components/       # UI components
│       │   ├── Header.tsx           # Navigation + language switcher
│       │   ├── DocumentList.tsx     # Document management
│       │   ├── DocumentUpload.tsx   # Drag-drop upload
│       │   ├── AgentChat.tsx        # Multi-turn chat
│       │   ├── AnalysisResult.tsx   # Analysis display
│       │   ├── EmailDraft.tsx       # Email composer
│       │   ├── EmailClassifier.tsx  # Email classification
│       │   ├── ActionDetector.tsx   # Action detection
│       │   ├── ClauseReview.tsx     # Clause review
│       │   ├── CostDashboard.tsx    # Chart.js dashboard
│       │   ├── SettingsModal.tsx    # Provider config
│       │   ├── UserManager.tsx      # RBAC management
│       │   ├── UserAuditViewer.tsx  # Audit trail with filters
│       │   └── Toast.tsx            # Notifications
│       ├── api/              # HTTP client
│       ├── i18n.ts           # English/French translations
│       └── App.tsx           # Main app shell
├── promptfoo/                # Eval suite
│   ├── promptfoo.yaml        # 21 tests, 8 categories
│   ├── tests/                # Test prompt files
│   └── run.sh                # Local eval runner
├── src-tauri/                # Rust/Tauri desktop wrapper
├── .github/workflows/        # CI/CD pipelines
│   └── eval.yml              # Tests + regression + frontend build
└── start.sh                  # Quick start launcher
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12+ · FastAPI 0.115+ · Uvicorn |
| **Agents** | LangGraph 0.2+ (state machines, supervisor routing) |
| **RAG** | rank_bm25 · sentence-transformers · numpy |
| **Multi-LLM** | LiteLLM 1.50+ (OpenAI, Anthropic, Google, DeepSeek, Groq, custom) |
| **Vector Store** | pgvector (optional) / in-memory (dev) |
| **Embeddings** | fastembed (local ONNX) / OpenAI / mock |
| **Observability** | Langfuse 2.50+ · Prometheus · custom metrics |
| **Eval** | Promptfoo · Hypothesis · pytest-benchmark |
| **Frontend** | React 18+ · TypeScript · Vite 6 · Chart.js |
| **Desktop** | Tauri 2.x (Rust) |
| **CI** | GitHub Actions · pip-audit · npm audit |

---

## 📋 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/documents/upload` | Upload PDF/DOCX/TXT |
| `GET` | `/api/v1/documents/` | List documents |
| `GET` | `/api/v1/documents/{id}` | Get document metadata |
| `POST` | `/api/v1/agents/analyze` | Analyze a document |
| `POST` | `/api/v1/agents/chat` | Chat with agent |
| `POST` | `/api/v1/agents/chat/stream` | Streaming chat (SSE) |
| `POST` | `/api/v1/agents/pipeline` | Multi-step pipeline |
| `POST` | `/api/v1/email/draft` | Draft an email |
| `GET` | `/api/v1/email/templates` | List email templates |
| `POST` | `/api/v1/email/classify` | Classify an email |
| `POST` | `/api/v1/email/action` | Detect email actions |
| `POST` | `/api/v1/clauses/review` | Review a clause |
| `GET` | `/api/v1/clauses/types` | List clause types |
| `POST` | `/api/v1/deeds/draft-clause` | Draft a clause |
| `POST` | `/api/v1/deeds/index` | Index a deed |
| `POST` | `/api/v1/acts/generate` | Generate a notarial act |
| `GET` | `/api/v1/system/config` | View runtime configuration |
| `POST` | `/api/v1/system/config/provider` | Configure LLM provider |
| `GET` | `/api/v1/system/logs` | Recent error logs |
| `GET` | `/api/v1/observability/stats` | Raw metrics (JSON) |
| `GET` | `/api/v1/observability/dashboard` | HTML dashboard |
| `GET` | `/api/v1/observability/metrics` | Prometheus metrics |
| `GET` | `/api/v1/rbac/users` | List users (admin) |
| `POST` | `/api/v1/rbac/users` | Create user (admin) |
| `GET` | `/api/v1/rbac/audit` | Audit trail (admin) |
| `POST` | `/api/v1/rbac/export/{id}` | GDPR data export |
| `POST` | `/api/v1/rbac/auth/login` | Authenticate |
| `GET` | `/api/v1/security/scan` | Injection detection |

---

## 🔧 Configuration

### Environment Variables
Copy `backend/.env.example` to `backend/.env`:

```env
# LLM Provider (primary)
LITELLM_API_KEY=sk-...
LITELLM_MODEL=openai/deepseek-v4-flash

# Vector Store
VECTOR_STORE_PROVIDER=pgvector  # or pinecone, qdrant

# Observability (optional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

### Runtime Configuration
API keys and provider selection persist in `backend/config/runtime.json` and can be updated via the **Settings** panel in the UI without restarting the server.

---

## 🌐 Internationalization

The application supports **English** and **French** for the user interface.

- Language switcher in the header bar — selection persists in localStorage
- All user-facing strings translated (100+ translation keys)
- Translates: navigation, document management, chat, email tools, settings, audit viewer, dashboard
- Language preference auto-detects from browser locale

## 🎨 Theme Support

The application supports **Dark** (default) and **Light** themes.

- Theme toggle button in the header (🌙/☀️)
- Preference persisted in localStorage
- Smooth CSS transitions between themes
- Light theme optimized for daytime use with adjusted contrast and shadows

### CSS Custom Properties
Theming is implemented entirely via CSS custom properties on `[data-theme="dark"]` and `[data-theme="light"]` selectors. Adding a new theme is as simple as adding a new `[data-theme="..."]` block in `App.css`.

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest -v                                    # All tests
pytest tests/unit/ -v                        # Unit tests
pytest tests/integration/ -v                 # Integration tests
pytest tests/contract/ -v                    # API contract tests
pytest tests/property/ -v                    # Property-based tests
pytest tests/fault/ -v                       # Fault injection tests
```

### Evaluation Suite
```bash
# Requires running backend with configured API key
cd promptfoo
./run.sh                                     # Full eval suite
./run.sh rag-accuracy                        # RAG tests only
./run.sh --view                              # Open web UI
```

### CI Pipeline
The `.github/workflows/eval.yml` workflow runs on every PR:
1. **Backend Tests** — pytest with ≥80% coverage
2. **Promptfoo Evaluation** — 21 tests across 8 categories
3. **Regression Check** — Compares scores against baseline
4. **Frontend Build** — TypeScript check + Vite build

Quality gates:
- Accuracy ≥ 85%
- Cost increase < $0.10 from baseline
- P95 latency increase < 5s from baseline

---

## 📦 Deployment

### Production
```bash
docker build -t legis-agent-backend -f backend/Dockerfile .
docker run -p 8000:8000 legis-agent-backend
```

### Desktop Bundle
```bash
cd src-tauri
cargo tauri build
# Bundle in: src-tauri/target/release/bundle/
```

---

## 📄 License

MIT

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

All PRs must pass the CI evaluation pipeline (quality gates).
