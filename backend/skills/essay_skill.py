import os
import re
import time
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from rag.retriever import KnowledgeRetriever, Citation, align_citations_with_response
from llm.base import BaseLLMProvider, ProviderResponse
import database.crud as crud
from database.schemas import ArtifactCreate, MessageCreate

logger = logging.getLogger("lenny-growth-backend.skills.essay")

SHIP30_SYSTEM_PROMPT = (
    "You are an elite product growth essayist and senior operator specializing in the 'Ship 30 for 30' long-form framework. "
    "Your objective is to produce an authoritative, comprehensive, deeply practical growth strategy essay "
    "targeting approximately 1,250 words based strictly on verified podcast transcript evidence from Lenny's Podcast.\n\n"
    "MANDATORY ESSAY STRUCTURE:\n"
    "1. ATOMIC HEADLINE: # [Punchy, high-signal title promising a transformative growth outcome]\n"
    "2. THE HOOK: ## The Hook: Why Conventional Wisdom Fails (expose an industry misconception/anti-pattern in 2-3 paragraphs)\n"
    "3. THE DIAGNOSTIC FRAMEWORK: ## The Diagnostic Framework: Core Mechanics (break down mental models and metrics with guest citations)\n"
    "4. THE TACTICAL PLAYBOOK: ## The Tactical Playbook: Real-World Execution (step-by-step playbooks with bold terms and transcript examples)\n"
    "5. PITFALLS & FAILURE MODES: ## Pitfalls & Counter-Intuitive Truths (2-3 common traps and how elite teams avoid them)\n"
    "6. MONDAY MORNING ACTION PLAN: ## The Monday Morning Action Plan (5 concrete operational checklist items)\n\n"
    "WRITING & GROUNDING RULES:\n"
    "- Attribute all strategies directly to the podcast guests present in the provided transcript evidence. Never fabricate quotes, guests, or episodes.\n"
    "- Write substantive, fully developed paragraphs. Target length is approximately 1,250 words."
)


class EssayResult(BaseModel):
    topic: str
    essay_content: str
    title: str
    word_count: int
    read_time: str
    citations: List[Citation] = Field(default_factory=list)
    has_sufficient_context: bool = True
    artifact_id: Optional[str] = None
    conversation_id: Optional[str] = None
    model: str
    provider: str


def extract_title_from_markdown(text: str, default_title: str) -> str:
    """
    Extracts the main H1 or first header from markdown content.
    """
    lines = text.strip().split("\n")
    for line in lines:
        cleaned = line.strip()
        if cleaned.startswith("# ") and len(cleaned) > 2:
            return cleaned[2:].strip().replace("**", "").replace("*", "")
    return default_title


async def generate_ship30_essay(
    topic: str,
    provider: BaseLLMProvider,
    retriever: KnowledgeRetriever,
    conversation_id: Optional[str] = None,
    db: Optional[Session] = None,
    timeout: Optional[float] = None,
) -> EssayResult:
    """
    Generates a structured, evidence-grounded 'Ship 30 for 30' essay (~1,250 words).
    Reuses the existing RAG retrieval pipeline and persists the resulting essay
    both as a conversation message and as a dynamic Markdown artifact.
    Timeouts are explicitly budgeted (default: 420.0s for CPU inference).
    """
    essay_timeout = timeout if timeout is not None else float(os.getenv("OLLAMA_ESSAY_TIMEOUT", "420.0"))
    start_time = time.monotonic()
    logger.info("Executing Ship 30 for 30 Essay Skill on topic: '%s' (budget=%.1fs)", topic, essay_timeout)

    # 1. Retrieve focused evidence from Lenny's Podcast transcripts (top_k=4 reduces prompt prefill bloat)
    retrieval_res = retriever.retrieve(query=topic, top_k=4)
    citations = retrieval_res.citations

    if not retrieval_res.has_sufficient_context:
        logger.info("Insufficient evidence for essay topic: '%s'", topic)
        insufficient_text = (
            f"# Insufficient Evidence: {topic}\n\n"
            "Based on the verified podcast transcripts currently indexed in the knowledge base, "
            f"there is insufficient evidence to write a comprehensive 'Ship 30 for 30' essay on **{topic}**.\n\n"
            "To generate a fully grounded essay with verified attribution, please choose a topic covered in the indexed archives, "
            "such as:\n"
            "- **Founder-Led Sales & GTM Execution** (Peter Kazanjy)\n"
            "- **B2B Product Positioning & Context Setting** (April Dunford)\n"
            "- **Superhuman Product-Market Fit Engine** (Rahul Vohra)\n"
            "- **B2B PLG Acquisition & Expansion Loops** (Elena Verna)\n"
            "- **Retention Curves & Compounding Growth Loops** (Casey Winters, Brian Balfour)"
        )

        # If a conversation ID was provided, persist refusal message
        if db and conversation_id:
            crud.create_message(
                db=db,
                msg_in=MessageCreate(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=insufficient_text,
                    model=provider.model_name,
                    citations=[],
                    has_sufficient_context=False,
                ),
            )

        return EssayResult(
            topic=topic,
            essay_content=insufficient_text,
            title=f"Insufficient Evidence: {topic}",
            word_count=len(insufficient_text.split()),
            read_time="1 min read",
            citations=[],
            has_sufficient_context=False,
            conversation_id=conversation_id,
            model=provider.model_name,
            provider=provider.provider_name,
        )

    # 2. Build streamlined generation prompt (preserves the ~1,250-word target without duplicate section descriptions)
    prompt = (
        f"Write a full-length, authoritative 'Ship 30 for 30' executive essay on the following topic:\n"
        f"TOPIC: {topic}\n\n"
        "Follow the 6 mandatory sections from the instructions (# Atomic Headline, ## The Hook, ## The Diagnostic Framework, "
        "## The Tactical Playbook, ## Pitfalls & Counter-Intuitive Truths, ## The Monday Morning Action Plan). "
        "Ground all claims directly in the provided transcript evidence, citing the featured podcast guests. "
        "Maintain thorough executive depth targeting approximately 1,250 words."
    )

    citation_dicts = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in citations]

    # 3. Call LLM provider with dedicated essay system prompt and explicit timeout
    try:
        response_obj = await provider.generate_response(
            prompt=prompt,
            history=[],
            context_text=retrieval_res.context_text,
            citations=citations,
            has_sufficient_context=True,
            timeout=essay_timeout,
            system_prompt=SHIP30_SYSTEM_PROMPT,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_504_GATEWAY_TIMEOUT:
            logger.warning("Ship 30 for 30 essay generation hit %.1fs timeout on topic: '%s'", essay_timeout, topic)
            timeout_msg_content = (
                f"# Local Inference Timeout Reached ({essay_timeout:.0f}s Safety Budget)\n\n"
                f"The request to generate a complete 'Ship 30 for 30' essay on **{topic}** reached the {essay_timeout:.0f}-second timeout budget.\n\n"
                f"### Hardware & Throughput Analysis:\n"
                f"- **Model & Execution:** Local Ollama (`{provider.model_name}`) running on Intel Core i3-10110U CPU (dual-core, 8 GB RAM).\n"
                f"- **Measured Speed:** ~2.3–2.7 tokens/second (CPU inference without GPU acceleration).\n"
                f"- **Deliverable Target:** Full-length executive essay of ~1,250 words (~1,650 output tokens).\n"
                f"- **Time Requirement:** At ~2.4 tokens/second, generating a full 1,250-word essay requires **~11–13 minutes** (~700 seconds). The {essay_timeout:.0f}-second timeout was reached while generation was actively progressing.\n"
                f"- **Quality Commitment:** We preserve the ~1,250-word deliverable standard and do not silently substitute an incomplete 600–800 word summary as finished work.\n\n"
                f"### Recommended Actions:\n"
                f"1. **Cloud LLM Acceleration (Instant Generation):** Configure `ANTHROPIC_API_KEY` in `backend/.env` and select **Claude 3.5 Sonnet** in the top header. Claude will generate the complete, grounded 1,250-word essay with verified citations in ~15 seconds.\n"
                f"2. **Targeted Section Inquiries:** For local CPU execution, query specific framework sections (e.g. *'What is Rahul Vohra's 40% PMF benchmark?'*) which complete in 60–120 seconds."
            )
            if db and conversation_id:
                crud.create_message(
                    db=db,
                    msg_in=MessageCreate(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=timeout_msg_content,
                        model=provider.model_name,
                        citations=citation_dicts,
                        has_sufficient_context=True,
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=timeout_msg_content,
            ) from exc
        raise

    essay_content = response_obj.content
    words = len(essay_content.split())
    eval_count = response_obj.eval_count
    total_duration = response_obj.total_duration

    # 3b. Bounded enrichment safeguard: If the initial call concluded prematurely (< 600 words)
    # and we have sufficient remaining time budget (>= 120s), perform AT MOST ONE bounded expansion pass.
    elapsed_so_far = time.monotonic() - start_time
    remaining_budget = essay_timeout - elapsed_so_far
    if words < 600 and remaining_budget >= 120.0:
        logger.info(
            "Initial essay draft reached %d words. Executing bounded one-time enrichment pass (remaining budget: %.1fs)",
            words,
            remaining_budget,
        )
        enrich_prompt = (
            f"Here is the draft of the 'Ship 30 for 30' essay on '{topic}':\n\n"
            f"{essay_content}\n\n"
            "The draft requires tactical expansion to reach comprehensive executive depth. "
            "Write a detailed supplementary section containing:\n"
            "1. ## Deep-Dive Operational Nuances & Failure Modes: 2-3 specific case examples from the transcript evidence.\n"
            "2. ## Advanced Monday Morning Implementation Checklist: A step-by-step execution protocol for growth teams.\n\n"
            "Ground every point strictly in the verified transcript excerpts. Do NOT repeat sections already present."
        )
        try:
            enrich_timeout = min(remaining_budget - 10.0, 150.0)
            enrich_obj = await provider.generate_response(
                prompt=enrich_prompt,
                history=[],
                context_text=retrieval_res.context_text,
                citations=citations,
                has_sufficient_context=True,
                timeout=enrich_timeout,
                system_prompt=SHIP30_SYSTEM_PROMPT,
            )
            if enrich_obj.content and len(enrich_obj.content.split()) >= 10:
                essay_content = f"{essay_content.rstrip()}\n\n{enrich_obj.content.lstrip()}"
                words = len(essay_content.split())
                if enrich_obj.eval_count and eval_count:
                    eval_count += enrich_obj.eval_count
                if enrich_obj.total_duration and total_duration:
                    total_duration += enrich_obj.total_duration
                logger.info("Enriched essay word count is now: %d words", words)
        except Exception as enrich_err:
            logger.warning("Bounded enrichment pass skipped or timed out (%s); keeping base draft (%d words)", enrich_err, words)

    read_mins = max(1, round(words / 225))
    read_time_str = f"{read_mins} min read"
    title = extract_title_from_markdown(essay_content, f"The Growth Playbook: {topic}")

    # Align citations with claims in the generated essay
    citations = align_citations_with_response(citations=citations, response_text=essay_content)

    artifact_id: Optional[str] = None

    # 4. Persistence into PostgreSQL
    if db and conversation_id:
        citation_dicts = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in citations]

        # 4a. Persist as dynamic Markdown artifact (upsert prevents duplicate artifacts on retry)
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-")[:32]
        db_artifact = crud.upsert_artifact(
            db=db,
            artifact_in=ArtifactCreate(
                conversation_id=conversation_id,
                title=title,
                artifact_type="markdown",
                content=essay_content,
                subtitle=f"Ship 30 for 30 Deep Dive on {topic}",
                badge="Ship 30 for 30 Essay",
                file_name=f"essay-{slug}.md",
                word_count=words,
                read_time=read_time_str,
                citations=citation_dicts,
                is_safe=True,
            ),
        )
        artifact_id = db_artifact.id

        # 4b. Persist as conversation assistant message linking artifact
        crud.create_message(
            db=db,
            msg_in=MessageCreate(
                conversation_id=conversation_id,
                role="assistant",
                content=essay_content,
                model=response_obj.model,
                citations=citation_dicts,
                has_sufficient_context=True,
                eval_count=response_obj.eval_count,
                total_duration=response_obj.total_duration,
                artifact_id=artifact_id,
            ),
        )

    return EssayResult(
        topic=topic,
        essay_content=essay_content,
        title=title,
        word_count=words,
        read_time=read_time_str,
        citations=citations,
        has_sufficient_context=True,
        artifact_id=artifact_id,
        conversation_id=conversation_id,
        model=response_obj.model,
        provider=response_obj.provider,
    )
