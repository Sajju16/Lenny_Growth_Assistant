# Quality Assurance & Verification Test Plan

**Document Version:** 1.0.0  
**Application:** Lenny Growth Assistant — Executive Product Intelligence Workstation  

---

## 1. Automated Test Suite

The test suite runs using `pytest` inside the Python virtual environment and covers unit, integration, and security layers.

### 1.1 Running the Backend Tests
```powershell
# Open terminal in repository root
$env:PYTHONPATH=".;.venv\Lib\site-packages"; python -m pytest backend/tests/ -v
```

### 1.2 Breakdown of Automated Tests (55 Tests Total)
- **`test_essay_skill.py` (4 tests):**
  - `test_extract_title_from_markdown`: Verifies H1 headline extraction.
  - `test_essay_skill_direct_generation_with_citations`: Verifies ~1,250-word essay structure, guest attribution, and Monday takeaways.
  - `test_essay_skill_insufficient_evidence`: Verifies refusal when evidence is lacking.
  - `test_api_skills_essay_endpoint`: Tests `POST /api/skills/essay` and database persistence.
- **`test_artifacts.py` (8 tests):**
  - `test_html_sanitizer_safe_html`: Validates clean HTML document encapsulation.
  - `test_html_sanitizer_removes_script_tags`: Neutralizes malicious `<script>` tags.
  - `test_html_sanitizer_removes_inline_event_handlers`: Neutralizes `onclick`, `onerror`, `onload`.
  - `test_html_sanitizer_neutralizes_javascript_uri`: Neutralizes `javascript:` protocols.
  - `test_create_markdown_artifact_api`: Tests `POST /api/artifacts` for Markdown.
  - `test_create_html_artifact_with_sanitization`: Tests `POST /api/artifacts` for HTML with security warnings.
  - `test_ordinary_chat_does_not_create_artifact`: Confirms chats do NOT accidentally become artifacts.
  - `test_chat_with_explicit_create_artifact`: Verifies artifact generation when `create_artifact=True`.
- **`test_providers.py` (8 tests):**
  - Tests provider factory resolution, key validation, HTTP 400 errors on missing keys, health reporting, mocked Claude generation, and prevention of silent fallbacks.
- **`test_agent.py` (5 tests):**
  - Tests `search_lenny_transcripts` schema, execution boundaries, multi-turn reasoning loop, missing key handling, and `/api/chat` agent mode.
- **`test_provider_persistence.py` (1 test):**
  - Verifies session isolation and structured JSON citation storage.
- **`test_database.py` (6 tests):**
  - Verifies conversation CRUD, foreign key cascading, citation serialization, session isolation.
- **`test_conversations_api.py` (6 tests):**
  - Tests `/api/conversations` endpoints (create, list, get, update, delete).
- **`test_postgres_real.py` (1 test):**
  - Verifies connection and CRUD against live PostgreSQL instance.
- **`test_parser.py`, `test_chunker.py`, `test_retriever.py`, `test_api.py` (16 tests):**
  - Tests frontmatter parsing, chunking with overlap, semantic retrieval, citations, and health checks.

### 1.3 Running the Frontend Production Build
```powershell
npm run build
```
Confirms clean compilation with zero linting, JSX, or bundling errors.

---

## 2. Manual UI Verification Workflow

### Test 1: Workspace Load & Health Diagnostics
1. Navigate to `http://localhost:3000`.
2. **Expected:** Interface displays the 3-panel layout. Header shows `PostgreSQL · Online` and `Ollama Local (qwen2.5:3b)`.

### Test 2: Grounded Q&A with Verified Citations
1. Select the `Direct Q&A` mode chip.
2. Enter: *"According to April Dunford, what are the key steps for crafting a winning sales pitch?"*
3. Click **Send**.
4. **Expected:** Model synthesizes grounded advice citing April Dunford. Citation cards display episode title, episode number, direct quote, and YouTube link.

### Test 3: Insufficient Evidence Handling
1. Enter an out-of-scope query: *"How do extreme ultraviolet lithography mirrors work in semiconductor manufacturing?"*
2. Click **Send**.
3. **Expected:** Assistant explicitly declines to invent advice and states: *"Based on the verified podcast transcripts currently indexed, there is insufficient evidence to answer this question."*

### Test 4: "Ship 30 for 30" Essay Skill
1. Select the `✨ Ship 30 for 30 Essay` mode chip above the composer.
2. Enter: *"Founder-led sales and customer discovery playbooks"*
3. Click **Generate Essay**.
4. **Expected:**
   - Model synthesizes an essay of ~1,250 words with atomic headline, opening hook, H2/H3 headers, and a "Monday Morning Action Plan".
   - Citations are preserved.
   - The Artifact Viewer opens automatically displaying the new Markdown essay.

### Test 5: Real Dynamic Artifact & Security Sandbox
1. Select the `🌐 HTML Artifact` mode chip.
2. Enter: *"Build an interactive SaaS CAC-to-LTV payback calculator with sliders"*
3. Click **Build Artifact**.
4. **Expected:**
   - Artifact Viewer renders the interactive calculator in an isolated `<iframe>` with `sandbox="allow-popups"`.
   - Styles inside the calculator do not bleed into the outer React interface.
   - Switching between "Preview (Sandbox)" and "HTML Source" tabs works smoothly.
   - Copy Code and Download (`.html`) work as expected.

### Test 6: Malicious HTML Sandbox Defense
1. In the console or via API, submit an HTML artifact containing `<script>alert(1)</script><button onclick="stealCookies()">Test</button>`.
2. Open the artifact in the Artifact Viewer.
3. **Expected:**
   - An amber **Security Notice: Untrusted Markup Neutralized** banner appears at the top.
   - The `<script>` and `onclick=` handler are stripped from the source code.
   - The viewer defaults to the source code inspection view.

### Test 7: Multi-Session Persistence & Restoration
1. Click **+ New Chat** (or press `⌘K`).
2. **Expected:** Chat resets to empty state; Artifact Viewer displays the clean empty state with the "Generate Ship 30 for 30 Essay" button.
3. Switch back to the previous session in the sidebar.
4. **Expected:** All previous messages, citation badges, and active dynamic artifacts are restored from PostgreSQL.

### Test 8: Fail-Safe Provider Switching
1. In the model selector, select **Anthropic Claude 3.5 Sonnet** (without configuring `ANTHROPIC_API_KEY`).
2. Submit any query.
3. **Expected:** The UI displays an immediate, actionable HTTP 400 error requiring `ANTHROPIC_API_KEY`. No silent fallback to mock or Ollama occurs.

---

## 3. Manual API Verification Commands (cURL)

```bash
# 1. Health check
curl -X GET http://127.0.0.1:8000/health

# 2. Knowledge base status
curl -X GET http://127.0.0.1:8000/api/knowledge/status

# 3. Create conversation
curl -X POST http://127.0.0.1:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "GTM Positioning Strategy", "category": "Product Strategy"}'

# 4. Generate Ship 30 for 30 Essay
curl -X POST http://127.0.0.1:8000/api/skills/essay \
  -H "Content-Type: application/json" \
  -d '{"topic": "Product positioning frameworks for B2B SaaS"}'

# 5. Create Dynamic HTML Artifact
curl -X POST http://127.0.0.1:8000/api/artifacts \
  -H "Content-Type: application/json" \
  -d '{"title": "Funnel Calculator", "artifact_type": "html", "content": "<div><h1>Cohort Funnel</h1></div>"}'
```
