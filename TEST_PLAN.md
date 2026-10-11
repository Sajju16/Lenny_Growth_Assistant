# Quality Assurance & Verification Test Plan

**Document Version:** 1.1.0
**Application:** Lenny Growth Assistant — Executive Product Intelligence Workstation
**Test Suite Status:** 105 Passed, 0 Failed

---

## 1. Automated Test Suite

The automated test suite runs via `pytest` inside the Python virtual environment and covers unit, integration, and security layers across all backend modules.

### 1.1 Running the Backend Tests
```powershell
# Open terminal in repository root
$env:PYTHONPATH=".;.venv\Lib\site-packages"; python -m pytest backend/tests/ -v
```

### 1.2 Breakdown of Automated Tests (105 Tests Total)

The test suite expanded from the baseline 55 tests to **105 passing tests** to validate streaming SSE, latency profiling, bounded timeouts, model selection, citation grounding, and conversation-history truncation:

- **`test_streaming_and_latency.py` (19 passing tests / test cases):**
  - `test_query_embedding_cache`: Verifies in-memory caching of query embeddings in `OllamaEmbeddingClient` (0ms cache hits).
  - `test_stream_response_tokens_and_metadata`: Verifies that `OllamaProvider.stream_response` yields token deltas and ends with metadata payload.
  - `test_stream_response_tps_calculation_excludes_ttft`: Verifies TPS measures generation duration rather than conflating TTFT.
  - `test_stream_response_zero_generation_time_safe`: Handles edge cases where stream terminates immediately without divide-by-zero.
  - `test_stream_response_native_ollama_metrics_logging`: Validates parsing of native `load_duration`, `prompt_eval_duration`, `eval_duration`, and token counts from Ollama final chunk.
  - `test_api_chat_stream_success_endpoint`: Tests end-to-end SSE `/api/chat/stream` endpoint with token events and done metadata.
  - `test_api_chat_stream_insufficient_evidence_endpoint`: Verifies that ungrounded queries return rapid refusal via SSE without invoking LLM generation.
  - `test_api_chat_stream_retrieval_top_k_two`: Confirms retrieval context is bounded to top-2 chunks in streaming mode.
  - `test_api_chat_standard_retrieval_top_k_two`: Confirms retrieval context is bounded to top-2 chunks in standard `/api/chat`.
  - `test_stream_endpoint_truncates_long_history_to_four`: Validates that long conversation histories (e.g., 8+ messages) are strictly truncated to the latest 4 messages (2 full turns) before invoking the LLM provider in `/api/chat/stream`.
  - `test_stream_endpoint_short_history_unchanged`: Confirms short histories (<= 4 messages) pass through unmodified in `/api/chat/stream`.
  - `test_chat_endpoint_truncates_long_history_to_four`: Validates that `/api/chat` enforces the identical 4-message history truncation policy.
  - `test_chat_endpoint_short_history_unchanged`: Confirms short histories pass through unmodified in `/api/chat`.

- **`test_model_selection.py` (5 passing tests):**
  - `test_health_model_reporting`: Verifies `/health` accurately reflects loaded Ollama models and defaults.
  - `test_chat_explicit_model_selection_1_5b`: Validates explicit model override to `qwen2.5:1.5b` in standard chat.
  - `test_chat_explicit_model_selection_3b`: Validates explicit model override to `qwen2.5:3b`.
  - `test_chat_stream_explicit_model_selection_1_5b`: Validates model selection override in streaming SSE requests.
  - `test_chat_stream_unsupported_question_preserves_selected_model`: Ensures model metadata is preserved even on early insufficient-evidence refusal.

- **`test_timeouts.py` (6 passing tests):**
  - `test_ollama_timeout_configuration`: Confirms environment variables `OLLAMA_CHAT_TIMEOUT` (180s) and `OLLAMA_ESSAY_TIMEOUT` (420s) configure client timeouts.
  - `test_factory_passes_timeout`: Verifies `get_llm_provider` propagates timeout settings to provider instances.
  - `test_chat_timeout_handling_persists_actionable_error`: Validates HTTP 504 handling and DB message persistence with guidance.
  - `test_essay_skill_timeout_handling`: Validates 420s timeout budget in essay generation.
  - `test_chat_message_deduplication_on_retry`: Verifies retrying a timed-out prompt updates existing assistant error rather than creating orphaned duplicates.
  - `test_stream_timeout_handling`: Verifies SSE stream emits error events on connection/inference timeout.

- **`test_retriever.py` (16 passing tests):**
  - `test_build_excerpt`: Tests verbatim transcript excerpt construction.
  - `test_extract_best_segment_prioritizes_guest`: Verifies excerpt extraction prioritizes guest utterances over interviewer intro/filler.
  - `test_format_context_prompt_empty` & `test_format_context_prompt_with_chunks`: Validates system prompt assembly with context windows.
  - `test_retriever_insufficient_evidence`: Validates cosine similarity thresholding (`>= 0.35`) triggers refusal when evidence is absent.
  - `test_retriever_sufficient_evidence`: Validates verified citation return when matching chunks exist.
  - `test_retriever_multiple_chunks_same_episode`: Confirms multiple chunks from one episode are merged into a single clean citation.
  - `test_retriever_different_episodes_distinct_citations`: Validates distinct citations for multiple guests/episodes.
  - `test_citation_excerpt_verbatim_transcript_words`: Confirms citations contain exact verbatim transcript quotes.
  - `test_grounding_system_prompt_rules`: Validates strict grounding instructions in prompt.
  - `test_retention_question_prunes_weakly_related_citation`: Tests semantic relevance pruning of tangentially matched chunks.
  - `test_align_citations_with_response_claims`: Verifies citation alignment with claims actually made in the synthesized response.
  - `test_unsupported_question_no_fabricated_citations`: Confirms unsupported queries never generate hallucinated citations.
  - `test_sourdough_croissants_unsupported_gate_with_moderate_raw_similarity`: Validates that out-of-domain food questions fail the grounding gate even if keyword similarity is moderate.
  - `test_duplicate_episode_citations_deduplicated`: Confirms duplicate episode citations are pruned.
  - `test_align_citations_insufficient_evidence_returns_empty`: Confirms that refusal responses return an empty citations list.

- **`test_api.py` (5 passing tests):**
  - `test_health_endpoint`: Tests `/health` status reporting across DB, Ollama, ChromaDB, and Anthropic.
  - `test_chat_endpoint_basic`: Tests basic synchronous `/api/chat` interaction.
  - `test_chat_endpoint_insufficient_evidence`: Tests insufficient evidence refusal response format.
  - `test_chat_real_dan_hockenmaier_retention_supported`: Tests live grounded Q&A on retention strategy attributed to Dan Hockenmaier.
  - `test_chat_real_sourdough_croissants_unsupported`: Verifies out-of-domain query ("sourdough croissants") returns strict refusal with zero fabricated baking ingredients.

- **`test_essay_skill.py` (12 passing tests):**
  - `test_extract_title_from_markdown`: Verifies H1 headline extraction from markdown.
  - `test_essay_skill_direct_generation_with_citations`: Verifies ~1,250-word essay structure, guest attribution, and Monday takeaways.
  - `test_essay_skill_insufficient_evidence`: Verifies refusal when evidence is lacking.
  - `test_api_skills_essay_endpoint`: Tests `POST /api/skills/essay` and database persistence.
  - `test_chat_endpoint_auto_routes_essay_intent_keywords`: Tests natural language intent routing ("Write an essay on...").
  - `test_chat_endpoint_auto_routes_slash_essay_command`: Tests slash command `/essay` routing to essay skill.
  - `test_essay_skill_timeout_explanation_persisted`: Verifies that a timed-out essay run persists detailed CPU diagnostic guidance.
  - `test_chat_endpoint_timeout_persists_actionable_guidance`: Verifies persistent timeout assistance in DB conversation view.
  - Plus 4 supporting unit tests covering headline fallback, section length validation, and prompt structure.

- **`test_artifacts.py` (8 passing tests):**
  - `test_html_sanitizer_safe_html`: Validates clean HTML document encapsulation.
  - `test_html_sanitizer_removes_script_tags`: Neutralizes malicious `<script>` tags.
  - `test_html_sanitizer_removes_inline_event_handlers`: Neutralizes `onclick`, `onerror`, `onload`.
  - `test_html_sanitizer_neutralizes_javascript_uri`: Neutralizes `javascript:` protocols.
  - `test_create_markdown_artifact_api`: Tests `POST /api/artifacts` for Markdown.
  - `test_create_html_artifact_with_sanitization`: Tests `POST /api/artifacts` for HTML with security warnings.
  - `test_ordinary_chat_does_not_create_artifact`: Confirms chats do NOT accidentally become artifacts.
  - `test_chat_with_explicit_create_artifact`: Verifies artifact generation when `create_artifact=True`.

- **`test_providers.py` (8 passing tests):**
  - Tests provider factory resolution, key validation, HTTP 400 errors on missing keys, health reporting, mocked Claude generation, and prevention of silent fallbacks.

- **`test_agent.py` (5 passing tests):**
  - Tests `search_lenny_transcripts` schema, execution boundaries, multi-turn reasoning loop, missing key handling, and `/api/chat` agent mode.

- **`test_database.py` (6 passing tests):**
  - Verifies conversation CRUD, foreign key cascading, citation serialization, session isolation.

- **`test_conversations_api.py` (5 passing tests):**
  - Tests `/api/conversations` endpoints (create, list, get, update, delete).

- **`test_parser.py` (5 passing tests):**
  - Tests frontmatter parsing, missing frontmatter handling, malformed yaml handling, ignoring README files, and clean body extraction.

- **`test_chunker.py` (3 passing tests):**
  - Tests 800-char windowing, 150-char overlap, and chunk metadata preservation.

- **`test_provider_persistence.py` (1 passing test):**
  - Verifies session isolation and structured JSON citation storage across providers.

- **`test_postgres_real.py` (1 passing test):**
  - Verifies connection and CRUD against active PostgreSQL instance.

### 1.3 Running the Frontend Production Build
```powershell
npm run build
```
Confirms clean compilation with zero linting, JSX, or bundling errors (`1,599 modules transformed`).

---

## 2. Distinction: Automated Tests vs. Manual Checks vs. Live Integrations

| Verification Level | Scope | Environment Status |
|---|---|---|
| **Automated Tests (105 Tests)** | Backend unit, integration, and security tests using `pytest` and `fastapi.testclient.TestClient`. | **100% Passing** in local virtual environment. |
| **Live Local Integrations** | Real PostgreSQL (`lenny_growth_db` on port 5432) and real local Ollama runtime (`qwen2.5:3b`, `nomic-embed-text` on port 11434). | **Verified Live**; verified via benchmark script and `/health` diagnostics. |
| **Mocked / Offline Integrations** | Anthropic Claude API (`claude-3-5-sonnet`) and Claude Agent SDK. | **Verified via Mock Tests**; live execution requires external user API key in `backend/.env`. |
| **Dockerized Integration** | Multi-container Docker Compose launch (`docker compose up --build`). | **Configured & Validated Syntactically**; host Windows machine lacks active Docker Desktop daemon. |
| **Manual UI Workflows** | 3-panel layout, citation card rendering, mode chips, and live SSE token streaming. | **Verified in Local Browser** on `http://localhost:3000`. |

---

## 3. Manual UI Verification Workflow

### Test 1: Workspace Load & Health Diagnostics
1. Navigate to `http://localhost:3000`.
2. **Expected:** Interface displays the 3-panel layout. Header shows `PostgreSQL · Online` and `Ollama Local (qwen2.5:3b)`.

### Test 2: Grounded Q&A with Live SSE Streaming & Citation Badges
1. Select the `Direct Q&A` mode chip.
2. Enter: *"How should an early-stage startup improve retention, and should we focus on early user experience or resurrection campaigns?"*
3. Click **Send**.
4. **Expected:**
   - Immediate TTFT (< 2–4s) with live word-by-word streaming token animation.
   - Response grounds in Dan Hockenmaier's interview, advising retention curves flatten early.
   - Citation cards display episode title, guest name, verbatim quote, and YouTube link.
   - Message footer displays verified citation count, model used, and streaming duration metrics.

### Test 3: Insufficient Evidence Handling
1. Enter an out-of-scope query: *"How do extreme ultraviolet lithography mirrors work in semiconductor manufacturing?"* or *"Can you share a French sourdough croissant recipe with butter and flour?"*
2. Click **Send**.
3. **Expected:** Assistant explicitly declines to invent advice and states: *"Based on the verified podcast transcripts currently indexed, there is insufficient evidence to answer this question."* No fabricated citations or ingredients appear.

### Test 4: Conversation History Truncation (Multi-Turn Latency Protection)
1. In an existing conversation, submit 3 successive questions.
2. Inspect the prompt token evaluation in logs.
3. **Expected:** Only the latest 4 messages (2 full user-assistant turns) plus the current prompt are passed to the LLM. Prompt tokens remain bounded (< 1,000 tokens) rather than ballooning to 2,800+ tokens.

### Test 5: "Ship 30 for 30" Essay Skill & Timeout Handling
1. Select the `✨ Ship 30 for 30 Essay` mode chip above the composer.
2. Enter: *"Founder-led sales and customer discovery playbooks"*
3. Click **Generate Essay**.
4. **Expected:**
   - Multi-phase progress indicator displays active phase ("Retrieving evidence", "Model prefill", "Generating sections").
   - Synthesizes an executive essay with atomic headline, hook, H2/H3 headers, and "Monday Morning Action Plan".
   - If CPU inference reaches the 420s safety timeout, the conversation view persists an informative explanation detailing measured tokens/s and guidance to switch to Cloud Claude for instant generation.

### Test 6: Real Dynamic Artifact & Security Sandbox
1. Select the `🌐 HTML Artifact` mode chip.
2. Enter: *"Build an interactive SaaS CAC-to-LTV payback calculator with sliders"*
3. Click **Build Artifact**.
4. **Expected:**
   - Artifact Viewer renders the interactive calculator in an isolated `<iframe>` with `sandbox="allow-popups"`.
   - Styles inside the calculator do not bleed into the outer React interface.
   - Switching between "Preview (Sandbox)" and "HTML Source" tabs works smoothly.

### Test 7: Malicious HTML Sandbox Defense
1. Submit an HTML artifact containing `<script>alert(1)</script><button onclick="stealCookies()">Test</button>`.
2. Open the artifact in the Artifact Viewer.
3. **Expected:**
   - Amber **Security Notice: Untrusted Markup Neutralized** banner appears at the top.
   - `<script>` and `onclick=` handler are stripped from the source code.
   - The viewer defaults to the source code inspection view.

### Test 8: Multi-Session Persistence & Restoration
1. Click **+ New Chat** (or press `⌘K`).
2. **Expected:** Chat resets to empty state; Artifact Viewer displays clean empty state.
3. Switch back to the previous session in the sidebar.
4. **Expected:** All previous messages, citation badges, and active dynamic artifacts are restored from PostgreSQL.

### Test 9: Fail-Safe Provider Switching
1. In the model selector, select **Anthropic Claude 3.5 Sonnet** (without configuring `ANTHROPIC_API_KEY`).
2. Submit any query.
3. **Expected:** UI displays an immediate HTTP 400 error requiring `ANTHROPIC_API_KEY`. No silent fallback occurs.

---

## 4. Manual API Verification Commands (cURL)

```bash
# 1. Health check
curl -X GET http://127.0.0.1:8001/health

# 2. Knowledge base status
curl -X GET http://127.0.0.1:8001/api/knowledge/status

# 3. Create conversation
curl -X POST http://127.0.0.1:8001/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "GTM Positioning Strategy", "category": "Product Strategy"}'

# 4. Stream chat with SSE
curl -N -X POST http://127.0.0.1:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "What is April Dunfords core framework for competitive alternatives?", "model": "qwen2.5:1.5b", "use_rag": true}'

# 5. Generate Ship 30 for 30 Essay
curl -X POST http://127.0.0.1:8001/api/skills/essay \
  -H "Content-Type: application/json" \
  -d '{"topic": "Product positioning frameworks for B2B SaaS"}'

# 6. Create Dynamic HTML Artifact
curl -X POST http://127.0.0.1:8001/api/artifacts \
  -H "Content-Type: application/json" \
  -d '{"title": "Funnel Calculator", "artifact_type": "html", "content": "<div><h1>Cohort Funnel</h1></div>"}'
```
