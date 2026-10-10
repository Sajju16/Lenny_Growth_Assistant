# System Architecture & Technical Specifications

**Document Version:** 1.0.0  
**Application:** Lenny Growth Assistant — Executive Product Intelligence Workstation  

---

## 1. System Topology Overview

```
                      ┌───────────────────────────────────────────────┐
                      │          React + Vite Frontend (Port 3000)    │
                      │  • TailwindCSS Design System                  │
                      │  • Sandboxed HTML Preview Iframe              │
                      │  • Session State & Artifact Management        │
                      └───────────────────────┬───────────────────────┘
                                              │ HTTP JSON / REST
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │             FastAPI Backend (Port 8000)       │
                      │  • Dependency Injection (SQLAlchemy DB)       │
                      │  • Health Diagnostics (/health)               │
                      │  • Conversation CRUD & Auto-Migration         │
                      │  • Artifact CRUD & HTML Sanitization Engine   │
                      │  • Ship 30 for 30 Essay Skill Endpoint        │
                      └───────┬───────────────┬───────────────┬───────┘
                              │               │               │
        Conversations/Messages│               │Semantic Search│
                              ▼               ▼               ▼
           ┌─────────────────────┐ ┌────────────────────┐ ┌───────────────────────────┐
           │     PostgreSQL      │ │  ChromaDB Store    │ │   LLM Provider Layer      │
           │  (lenny_growth_db)  │ │ (backend/data/     │ │ • OllamaProvider (Local)  │
           │  • conversations    │ │  chroma_db)        │ │ • AnthropicProvider (Cloud│
           │  • messages (JSON)  │ │ • Cosine Sim>=0.35 │ │ • ClaudeTranscriptAgent   │
           │  • artifacts (table)│ └────────────────────┘ └───────────────────────────┘
           └─────────────────────┘
```

---

## 2. Pluggable LLM Provider Layer

The LLM generation pipeline is decoupled from API routing via the abstract base class `BaseLLMProvider` in `backend/llm/base.py`:

```python
class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        history: List[Dict[str, str]],
        context_text: Optional[str] = None,
        citations: Optional[List[Citation]] = None,
        has_sufficient_context: bool = True,
    ) -> ProviderResponse: ...
```

### 2.1 Provider Implementations
- **`OllamaProvider` (`backend/llm/ollama_provider.py`):** Connects to the local Ollama daemon via HTTP (`http://localhost:11434/api/chat`). Uses model `qwen2.5:3b` with zero cloud network egress.
- **`AnthropicProvider` (`backend/llm/anthropic_provider.py`):** Uses the official Anthropic Python SDK with `claude-3-5-sonnet-20241022`. Requires `ANTHROPIC_API_KEY`.
- **Provider Factory (`backend/llm/factory.py`):** Resolves provider instances based on `LLM_PROVIDER=ollama|anthropic`. Enforces zero-fallback validation: missing cloud keys return explicit HTTP 400 Bad Request errors.

---

## 3. Assignment-Required Agent Layer

Located in `backend/agent/transcript_agent.py` and `backend/agent/tools.py`:

```
User Query
    │
    ▼
ClaudeTranscriptAgent.run()
    │
    ▼
Prompt Claude with Tools: [search_lenny_transcripts]
    │
    ├── Claude decides to invoke tool ──► execute_search_transcripts()
    │                                          │
    │                                          ▼
    │                                     KnowledgeRetriever.retrieve()
    │                                          │
    │                                          ▼
    │                                     ChromaDB Vector Store
    │                                          │
    │                                          ▼
    │                                     Return formatted JSON citations
    │                                          │
    │◄── Feed tool_result back to Claude ──────┘
    │
    ▼
Claude produces final grounded executive synthesis
```

### 3.1 Strict Security Boundaries
- **No Arbitrary Shell:** The agent only has access to `search_lenny_transcripts`. Any unauthorized tool name requested by the model is immediately rejected.
- **No Unrestricted Filesystem Access:** Read-only access to pre-indexed ChromaDB embeddings.
- **Multi-Turn Reasoning Loop:** Supports up to 3 iterative tool-calling turns before returning final synthesis.

---

## 4. Local RAG Retrieval Architecture

Located in `backend/rag/`:

1. **Ingestion & Frontmatter Parser (`parser.py`):** Parses markdown transcripts from `ChatPRD/lennys-podcast-transcripts`, extracting YAML frontmatter (`guest`, `title`, `number`, `youtube_url`).
2. **Overlapping Recursive Chunker (`chunker.py`):** Breaks transcripts into semantic chunks (~800 characters) with 150-character overlapping windows, preserving metadata on every chunk.
3. **ChromaDB Vector Store (`vector_store.py`):** Indexes embeddings using local Ollama `nomic-embed-text` into persistent storage (`backend/data/chroma_db`).
4. **Knowledge Retriever (`retriever.py`):** Performs cosine similarity search. Filters out irrelevant chunks with threshold `score >= 0.35`. Formats verified `Citation` objects.

---

## 5. PostgreSQL Relational Persistence

Located in `backend/database/`:

```
┌─────────────────────────────────┐
│          conversations          │
├─────────────────────────────────┤
│ id: VARCHAR(64) PRIMARY KEY     │
│ title: VARCHAR(255)             │
│ category: VARCHAR(100)          │
│ artifact_id: VARCHAR(64) NULL   │
│ created_at: TIMESTAMP           │
│ updated_at: TIMESTAMP           │
└────────────────┬────────────────┘
                 │
                 ├── 1:N (Cascade Delete)
                 │
                 ▼
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│            messages             │       │            artifacts            │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ id: VARCHAR(64) PRIMARY KEY     │       │ id: VARCHAR(64) PRIMARY KEY     │
│ conversation_id: VARCHAR(64) FK │       │ conversation_id: VARCHAR(64) FK │
│ role: VARCHAR(20)               │       │ title: VARCHAR(255)             │
│ content: TEXT                   │       │ artifact_type: VARCHAR(20)      │
│ model: VARCHAR(100)             │       │ content: TEXT                   │
│ citations: JSON NULL            │       │ is_safe: BOOLEAN                │
│ has_sufficient_context: BOOLEAN │       │ security_warnings: JSON         │
│ created_at: TIMESTAMP           │       │ citations: JSON                 │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

---

## 6. Dynamic Artifact & HTML Security Sandbox

Located in `backend/artifacts/sanitizer.py` and `src/components/ArtifactViewer.jsx`:

1. **Backend Sanitization (`validate_and_sanitize_html`):**
   - Strips `<script>`, `<object>`, `<embed>`, `<iframe>`.
   - Strips inline event handlers (`onclick`, `onerror`, `onload`, `onmouseover`).
   - Replaces `javascript:` URIs with `#`.
   - Wraps raw snippets in complete HTML5 documents with isolated stylesheets.
   - Flags unsafe inputs with `is_safe=False` and attaches warning messages.
2. **Frontend Sandboxed Iframe:**
   - Rendered via `<iframe srcDoc={content} sandbox="allow-popups" />`.
   - Omission of `allow-scripts` disables JS execution.
   - Omission of `allow-same-origin` ensures the iframe cannot read or write parent cookies, local storage, session storage, or DOM elements.
   - Displays an amber security banner when `is_safe: false`.

---

## 7. Containerization & Deployment

`docker-compose.yml` provides a unified multi-container setup:
- **`postgres`:** Database server on port 5432 with healthchecks and `postgres_data` persistent volume.
- **`backend`:** FastAPI container with multi-stage Python build, connected to PostgreSQL and host Ollama via `host.docker.internal:11434`.
- **`frontend`:** Multi-stage Node build compiled to static bundle served via Nginx on port 3000, proxying API and health traffic to `backend`.
