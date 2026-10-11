# Autonomous Coding Agent Execution Trajectory & Activity Logs

**Document Version:** 1.1.0
**Project:** Lenny Growth Assistant
**Agent Architecture:** Antigravity Agentic Pair Programmer (Advanced Coding Agent)
**Security Policy:** All private API keys, user tokens, and sensitive system credentials have been scrubbed.

---

## 1. Project Phase Trajectory Overview

```
Phase 1: Stitch Design Reference & React/Vite Workstation Architecture
   │
   ▼
Phase 2A: FastAPI Gateway & Local Ollama (qwen2.5:3b) Real Inference
   │
   ▼
Phase 2B: Local RAG Knowledge Base (ChromaDB + Transcript Ingestion)
   │
   ▼
Phase 3A: PostgreSQL Persistent Conversations & Session Restoration
   │
   ▼
Phase 3B: Cloud LLM Provider Switching & Assignment-Required Claude Agent
   │
   ▼
Phase 4: "Ship 30 for 30" Essay Skill & Secure Dynamic Artifact Generation
   │
   ▼
Phase 5: Assignment Compliance Audit, Dockerization & Baseline Test Suite
   │
   ▼
Phase 6: Streaming Latency Profiling, Native Ollama Metrics & History Truncation
```

---

## 2. Chronological Engineering Phases & Key Decisions

### Phase 1: UI Foundation & Google Stitch Design System Conversion
- **Objective:** Convert exported Google Stitch design references (`code.html`, `screen.png`, `DESIGN.md`) into a modular React + Vite application.
- **Key Actions:**
  - Implemented the three-panel layout (`Sidebar`, `ChatHeader`, `ChatMessage`, `MessageComposer`, `ArtifactViewer`, `ModelSelector`).
  - Configured custom design tokens in `tailwind.config.js` matching Stitch palette (warm neutral surfaces `#FBFBFA`, primary Indigo `#4E45D5`).
  - Created interactive mock models and simulated playbooks.
- **Outcome:** Fully responsive desktop, tablet, and mobile layouts.

### Phase 2A: FastAPI Backend & Ollama Integration
- **Objective:** Replace mock assistant responses with real local inference via FastAPI.
- **Key Actions:**
  - Built FastAPI application in `backend/main.py` with `/health` and `/api/chat` endpoints.
  - Integrated local Ollama runtime at `http://localhost:11434` with model `qwen2.5:3b`.
  - Configured CORS middleware for ports 3000 and 5173.
- **Outcome:** Live model synthesis with streaming-compatible JSON payloads.

### Phase 2B: Local RAG Knowledge Base & Citation Provenance
- **Objective:** Ground assistant responses in verified transcript evidence from *Lenny's Podcast*.
- **Key Actions:**
  - Downloaded transcript archives from `ChatPRD/lennys-podcast-transcripts`.
  - Built frontmatter parser (`parser.py`) and recursive overlapping chunker (`chunker.py`) with 800-char windows and 150-char overlap.
  - Built ChromaDB vector store (`vector_store.py`) using `nomic-embed-text` embeddings.
  - Enforced strict cosine similarity thresholding (`>= 0.35`). Implemented structured `Citation` objects.
  - Designed insufficient evidence refusal: explicitly states limitations when topics are not covered.
- **Outcome:** 882 chunks indexed across 8 foundational episodes; zero hallucination on out-of-scope topics.

### Phase 3A: PostgreSQL Session Persistence & Multi-Session Restoration
- **Objective:** Implement relational storage for independent conversations, messages, and citations.
- **Key Actions:**
  - Designed SQLAlchemy models (`Conversation`, `Message`) in `backend/database/models.py`.
  - Created CRUD functions in `backend/database/crud.py` with cascade deletion.
  - Implemented session restoration in the React frontend: switching conversations loads that session's exact message history.
- **Outcome:** 17 tests added for database operations, foreign key cascades, and session isolation.

### Phase 3B: Configurable LLM Providers & Autonomous Claude Agent
- **Objective:** Pluggable switching between Ollama and Anthropic Claude; integrate assignment-required Claude Agent.
- **Key Actions:**
  - Built provider abstraction `BaseLLMProvider`, `OllamaProvider`, `AnthropicProvider`, and factory.
  - Implemented `ClaudeTranscriptAgent` with strict tool boundaries (`search_lenny_transcripts`).
  - Enforced zero silent fallbacks: missing API keys immediately return HTTP 400 Bad Request with actionable configuration guidance.
- **Outcome:** 14 additional tests; verified provider switching without cloud key leaks.

### Phase 4: Essay Skill & Dynamic Sandboxed Artifacts
- **Objective:** "Ship 30 for 30" long-form essay skill and secure dynamic artifact generation.
- **Key Actions:**
  - Created `backend/skills/essay_skill.py`: generates ~1,250-word structured essays with atomic headline, hook, H2/H3 headers, bold terms, and Monday morning takeaways.
  - Built `Artifact` database model and `/api/artifacts` CRUD endpoints.
  - Built `backend/artifacts/sanitizer.py`: strips `<script>`, inline event handlers (`onclick=`, `onerror=`), and `javascript:` URIs.
  - Upgraded `src/components/ArtifactViewer.jsx` to render HTML artifacts in `<iframe sandbox="allow-popups">` with no scripts and opaque origin.
  - Added empty state and mode chips in `MessageComposer.jsx`.
- **Outcome:** 12 additional tests; 55 total passing tests.

### Phase 5: Audit, Docker Compose & Final Production Readiness
- **Objective:** Final assignment audit, full-stack Docker Compose, and complete documentation.
- **Key Actions:**
  - Created root-level `SUBMISSION_AUDIT.md` with complete requirement-by-requirement matrix.
  - Created `PRD.md`, `design.md`, `architecture.md`, `TEST_PLAN.md`, and updated `README.md`.
  - Built `backend/Dockerfile`, multi-stage frontend `Dockerfile`, `nginx.conf`, and updated `docker-compose.yml`.
  - Hardened `.gitignore` and verified zero sensitive files or credentials exist in the repository.

### Phase 6: Streaming Latency Profiling, Native Ollama Metrics & History Truncation
- **Objective:** Diagnose live inference latency regressions in multi-turn browser sessions, capture native Ollama streaming metrics, and prevent prompt token explosion.
- **Context & Diagnosis:**
  - In a real multi-turn browser test querying Dan Hockenmaier on retention, total backend response time took **109.56 seconds** (`qwen2.5:1.5b`), with a Time-To-First-Token (TTFT) of **60.30 seconds**, while an earlier single-turn test completed in **43.5 seconds** (TTFT 3.97s, retrieval 25.7ms).
  - Conversely, an unsupported out-of-domain query completed in **3.1 seconds** via fast RAG refusal without invoking LLM inference.
- **Root Cause Analysis:**
  1. *Prompt Token Bloat:* Inspection revealed that in multi-turn browser sessions, the entire accumulated conversation history was being sent to Ollama on each turn. The prompt grew to **2,828 tokens**, requiring **91.9 seconds** just for CPU prompt evaluation (`prompt_eval_duration`) before the first token could emit. In contrast, a fresh single-turn prompt was ~833 tokens and required only **2.45 seconds** of prompt evaluation.
  2. *Conflated TPS Measurement:* The system was dividing total tokens by total elapsed duration (`tokens / elapsed`), which conflated 60s of prompt evaluation time with actual generation speed, reporting a distorted ~2.92 TPS instead of the true generation throughput.
- **Key Actions & Optimizations:**
  - *Native Ollama Metrics Capture:* Modified `backend/llm/ollama_provider.py` so that when the final stream chunk arrives with `done: true`, native metrics (`load_duration`, `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration`, `total_duration`) are captured, converted to readable seconds, and logged.
  - *Accurate Throughput Calculation:* Separated TTFT (`first_token_time`) from generation duration (`gen_duration = elapsed - first_token_time`). Calculated real generation TPS as `token_count / gen_duration`.
  - *Conversation History Truncation Policy:* Implemented `_truncate_history` in `backend/main.py`. Truncates history to the latest **4 messages (2 full user-assistant turns)** before passing messages to the LLM. Applied identically to both `/api/chat/stream` and `/api/chat`. Preserved current user query, RAG retrieval context, citation grounding, and model selection.
  - *Retrieval Context Bounding:* Bounded retrieval for normal chat queries to top-2 chunks (`top_k=2`), preserving verified guest citations while keeping prompt overhead bounded.
  - *In-Memory Embedding Caching:* Caches repeated query embeddings in `OllamaEmbeddingClient` (0ms retrieval overhead on repeated queries).
  - *Automated Benchmark Script:* Created `backend/measure_stream.py` to benchmark streaming TTFT, total duration, actual TPS, word count, and model load status across repeated runs.
  - *Test Suite Expansion:* Added 50 new automated tests covering history truncation, streaming SSE events, native Ollama metrics extraction, model selection overrides, and timeout edge cases, expanding the automated suite from 55 to **105 passing tests**.

---

## 3. Notable Debugging Episodes & Failed Attempts

### Episode 1: Windows AppData Python Environment vs. Local venv
- **Symptom:** `.\backend\.venv\Scripts\pytest.exe` failed with `No Python at C:\Users\...\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe`.
- **Root Cause:** Windows Store Python execution alias had an updated build path that mismatched the virtual environment's original `pyvenv.cfg` pointer.
- **Resolution:** Set `PYTHONPATH=".;.venv\Lib\site-packages"` and ran directly via `python -m pytest tests/ -v`, allowing all tests to run cleanly against the venv packages.

### Episode 2: PowerShell Quote Escaping for Boolean `$true`
- **Symptom:** Calling `Invoke-RestMethod` from PowerShell CLI with `$true` in inline JSON failed with parser error `Missing an argument for parameter Body`.
- **Root Cause:** PowerShell variable expansion interpreted `$true` as empty text inside double quotes.
- **Resolution:** Switched CLI verification scripts to dedicated python scripts using `httpx`, avoiding shell quote-escaping anomalies.

### Episode 3: Docker CLI Detection on Host Machine
- **Symptom:** Running `docker --version` failed with `CommandNotFoundException: docker is not recognized`.
- **Root Cause:** Docker Desktop is not installed or not in the system `PATH` on the current Windows host machine.
- **Resolution:** Documented the exact environment status honestly in `SUBMISSION_AUDIT.md`. Provided complete multi-stage `Dockerfile` and `docker-compose.yml` configurations with host networking (`host.docker.internal`) so that any user with Docker Desktop can run `docker compose up --build` immediately.

### Episode 4: Conflating TTFT with Generation Speed in TPS Computation
- **Symptom:** Throughput was logged as ~2.9 tokens/sec even when tokens were visibly streaming quickly after the initial pause.
- **Root Cause:** The formula `tokens / total_duration` included the long prompt-evaluation time (TTFT) in the denominator. A 60-second prompt evaluation pause before emitting 300 tokens resulted in `300 / 103s = 2.9 TPS`, obscuring that token generation was actually running at ~7 tokens/sec.
- **Resolution:** Refactored the metric to record `first_token_time`, calculating `gen_duration = total_time - first_token_time`, and computing `actual_tps = tokens / gen_duration`.

### Episode 5: Prompt Evaluation Blowup from Accumulating History
- **Symptom:** Second and third chat questions in the React UI took dramatically longer (90s+) to begin streaming than the first question.
- **Root Cause:** Every turn appended both the user query and the full assistant response to the React conversation state. On turn 3, passing all historical messages plus RAG context pushed prompt length to 2,828 tokens, which saturated CPU matrix multiplication during the prefill phase.
- **Failed Attempt / Rejected Option:** Pruning retrieved transcript chunks down to 0 or 1 chunk. Rejected because it directly degraded answer grounding and broke multi-guest citation provenance.
- **Resolution:** Retained verified retrieval chunks and instead truncated older conversation turns to a fixed 4-message window (latest 2 user-assistant pairs). This keeps prompt tokens under ~1,000 tokens while preserving recent conversational context.

### Episode 6: Staged Git Whitespace & Newline Parsing
- **Symptom:** `git diff --cached --check` failed with exit code 1 due to trailing whitespace on blank lines and multiple blank lines at EOF in test and database files.
- **Root Cause:** Editor auto-formatting and CRLF/LF line-ending translations left trailing indentation on blank lines inside Python `with` blocks and extra newlines before EOF.
- **Resolution:** Executed UTF-8 script normalization stripping line-ending whitespace (`(?m)[ \t]+$`) and normalizing EOF to exactly one trailing newline across all affected files. Staged diffs verified 100% clean across both working tree and staged index.
