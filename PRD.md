# Product Requirements Document (PRD)
## Lenny Growth Assistant — Executive Product Intelligence Workstation

**Document Version:** 1.0.0  
**Status:** Implemented & Production-Ready  
**Role:** Forward Deployed Engineer (FDE) Take-Home Assignment  
**Author:** Lenny Growth Assistant Engineering Team  

---

## 1. Executive Summary & Discovery Brief

### 1.1 The Context
*Lenny's Podcast* is the definitive archive of modern software growth wisdom, featuring hundreds of deep-dive interviews with world-class operators (e.g., April Dunford on positioning, Peter Kazanjy on founder-led sales, Elena Verna on B2B PLG, Sean Ellis on PMF).

However, operators, founders, and growth leaders face significant friction when attempting to leverage this knowledge in their daily strategic work:
1. **Generic LLM Hallucinations:** Commercial AI assistants (e.g., vanilla ChatGPT) synthesize generic, homogenized advice and frequently invent fake case studies or attribute frameworks to the wrong people.
2. **Loss of Verifiable Attribution:** Strategic decisions require executive credibility. Advice without verifiable source episodes, guest credentials, and direct timestamps is rejected by leadership teams.
3. **The "Blank Page" Delivery Gap:** Operators don't just want conversation answers—they need structured, board-ready strategic deliverables: "Ship 30 for 30" long-form essays, executive playbooks, and interactive cohort calculators.
4. **Security Vulnerabilities in Dynamic Deliverables:** Generating rich interactive artifacts (HTML/CSS models) introduces severe XSS risks if rendered un-sandboxed in enterprise applications.

### 1.2 The Discovery Brief
Through operator interviews and workflow observation, four primary requirements emerged:
- **Local-First, Zero-Cloud Lock-In:** Operators want local offline inference (Ollama `qwen2.5:3b`) for privacy and cost control, with the ability to switch to cloud models (Claude 3.5 Sonnet) when maximum reasoning depth is needed.
- **Strict Grounding with Transparent Limitations:** If Lenny's archives do not cover a topic (e.g., semiconductor lithography), the system must disclose the limitation immediately rather than hallucinating plausible-sounding startup advice.
- **Persistent Multi-Session History:** Strategy discussions evolve over weeks. Conversations and generated artifacts must persist reliably in PostgreSQL.
- **Safe Sandboxed Execution:** Dynamic HTML models must be completely isolated from application cookies, local storage, and the parent DOM.

---

## 2. Target Personas

| Persona | Role | Core Need | Key Friction Solved |
|---|---|---|---|
| **Alex Kim** | Head of Growth (Series A B2B SaaS) | Needs battle-tested positioning and activation playbooks grounded in verified operator experience. | Eliminates vague generic advice; provides direct guest attribution (April Dunford, Elena Verna). |
| **Maya Patel** | Early-Stage Founder | Needs structured "Ship 30 for 30" essays to communicate GTM strategy to investors and early hires. | Turns transcript insights into ~1,250-word publishable strategic essays with Monday morning takeaways. |
| **David Vance** | Product Operations Lead | Needs interactive retention models and visual calculators generated on the fly. | Generates interactive HTML artifacts rendered securely in isolated sandboxes. |

---

## 3. Goals & Success Metrics

| Goal | Success Metric | Target | Actual Result |
|---|---|---|---|
| **Transcript Grounding** | Proportion of advice attributed to real podcast guests | 100% | 100% verified via ChromaDB cosine similarity thresholding (>= 0.35). |
| **Zero Hallucination on Out-of-Scope Topics** | Refusal and disclosure rate when evidence is absent | 100% | Passes automated tests (`test_chat_insufficient_evidence`, `test_essay_skill_insufficient_evidence`). |
| **Essay Quality & Structure** | Word count, atomic headline, hook, H2/H3 headers, Monday takeaways | ~1,250 words | Validated via `backend/skills/essay_skill.py` and automated test suite. |
| **HTML Artifact Security** | Zero script execution, zero same-origin access, zero DOM leakage | 100% containment | Validated via `<iframe sandbox="allow-popups">` and automated sanitizer tests. |
| **Session Persistence** | Complete conversation, message, and artifact restoration | 100% consistency | PostgreSQL persistence across reloads and multi-session switches. |
| **Fail-Safe Provider Switching** | Zero silent fallbacks when cloud credentials are missing | 100% adherence | Immediate HTTP 400 with actionable configuration instructions. |

---

## 4. Scope & Feature Specifications

### 4.1 In Scope (Implemented)
1. **FastAPI Backend Gateway:** RESTful API with validation, health checks, structured errors, and CORS.
2. **Three-Panel React UI:** Left conversation sidebar, central chat with citation cards, right dynamic Artifact Viewer.
3. **Local RAG Pipeline:** Semantic transcript ingestion, chunking, and ChromaDB vector retrieval with citation traceability.
4. **Pluggable LLM Provider Abstraction:** Seamless switching between Ollama (`qwen2.5:3b`) and Anthropic (`claude-3-5-sonnet-20241022`).
5. **Assignment-Required Agent Layer:** `ClaudeTranscriptAgent` with strict tool boundaries (`search_lenny_transcripts`).
6. **PostgreSQL Session Persistence:** Relational storage of conversations, messages, citations, and dynamic artifacts.
7. **"Ship 30 for 30" Essay Skill:** Dedicated ~1,250-word essay generation module grounded in transcripts.
8. **Dynamic Artifact Generation & Viewer:** Markdown playbooks and sandboxed HTML models with empty-state handling.
9. **Full-Stack Docker Compose:** One-command startup for PostgreSQL, FastAPI, and React/Nginx.

### 4.2 Out of Scope (Deferred to Future Roadmap)
- Real-time multi-user team collaboration and commenting on artifacts.
- Native mobile applications (iOS/Android) — responsive web layout is prioritized.
- Direct push integration into third-party Notion API (simulated with feedback in current version).

---

## 5. Security & Risk Analysis

| Threat / Risk | Impact | Mitigation Strategy |
|---|---|---|
| **Cross-Site Scripting (XSS) via Model HTML** | High (Cookie/token theft, DOM defacement) | Model HTML is never injected via `dangerouslySetInnerHTML`. Previews run in `<iframe sandbox="allow-popups">` with no `allow-scripts` or `allow-same-origin`. Backend sanitizer strips `<script>` tags, inline handlers (`onclick`), and `javascript:` URIs. |
| **Silent Provider Degradation** | Medium (Unexpected cloud costs or fallback confusion) | Explicit validation rejects missing/placeholder API keys with HTTP 400 Bad Request; never silently falls back to another provider. |
| **Transcript Licensing & Attribution** | Low (Legal / ethical compliance) | Strict attribution to guests, episode titles, episode numbers, and original YouTube URLs. Raw transcript repository excluded from Git. |
| **Database Orphan Messages** | Medium (Data integrity drift) | PostgreSQL foreign key cascades automatically delete child messages and artifacts upon conversation deletion. |
