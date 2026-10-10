import re
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rag.retriever import KnowledgeRetriever, Citation
from llm.base import BaseLLMProvider, ProviderResponse
import database.crud as crud
from database.schemas import ArtifactCreate, MessageCreate

logger = logging.getLogger("lenny-growth-backend.skills.essay")

SHIP30_SYSTEM_PROMPT = (
    "You are an elite product growth essayist specializing in the 'Ship 30 for 30' long-form framework. "
    "Your mission is to produce a compelling, authoritative, and deeply practical growth strategy essay "
    "of approximately 1,250 words based strictly on verified podcast transcript evidence from Lenny's Podcast.\n\n"
    "ESSAY STRUCTURE AND STYLE REQUIREMENTS:\n"
    "1. ATOMIC HEADLINE: Create a punchy, high-signal title promising a tangible growth transformation.\n"
    "2. THE HOOK (Opening): Grab executive attention immediately. Expose a common industry failure, myth, or counter-intuitive truth in modern SaaS.\n"
    "3. COHERENT NARRATIVE ARC: Organize the core argument into 3 to 5 logical sections using clear, skimmable H2 and H3 markdown headers.\n"
    "4. HIGHLY SKIMMABLE EXECUTION: Keep paragraphs concise (2-4 sentences max). Use bold emphasis on key principles, frameworks, and metrics.\n"
    "5. STRICT GROUNDING & ATTRIBUTION: Attribute every strategy, mental model, and benchmark directly to the podcast guests present in the provided transcript evidence. Never fabricate quotes, guests, or episodes.\n"
    "6. PRACTICAL MONDAY TAKEAWAYS: Conclude with a dedicated 'Monday Morning Action Plan' containing 3-5 concrete, actionable steps an operator can immediately execute.\n"
    "7. TARGET LENGTH: Generate a comprehensive, deep-dive essay of approximately 1,250 words."
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
) -> EssayResult:
    """
    Generates a structured, evidence-grounded 'Ship 30 for 30' essay (~1,250 words).
    Reuses the existing RAG retrieval pipeline and persists the resulting essay
    both as a conversation message and as a dynamic Markdown artifact.
    """
    logger.info("Executing Ship 30 for 30 Essay Skill on topic: '%s'", topic)

    # 1. Retrieve evidence from Lenny's Podcast transcripts
    retrieval_res = retriever.retrieve(query=topic, top_k=6)
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

    # 2. Build structured generation prompt
    prompt = (
        f"Write a comprehensive 'Ship 30 for 30' executive essay on the following topic:\n"
        f"TOPIC: {topic}\n\n"
        "Follow all Ship 30 for 30 guidelines: atomic headline, compelling opening hook, coherent narrative arc, "
        "concise skimmable paragraphs, bold key terms, direct guest attributions from the transcript evidence, "
        "and concrete Monday Morning Action takeaways. Aim for approximately 1,250 words."
    )

    # 3. Call LLM provider
    response_obj = await provider.generate_response(
        prompt=prompt,
        history=[],
        context_text=retrieval_res.context_text,
        citations=citations,
        has_sufficient_context=True,
    )

    essay_content = response_obj.content
    words = len(essay_content.split())
    read_mins = max(1, round(words / 225))
    read_time_str = f"{read_mins} min read"
    title = extract_title_from_markdown(essay_content, f"The Growth Playbook: {topic}")

    artifact_id: Optional[str] = None

    # 4. Persistence into PostgreSQL
    if db and conversation_id:
        citation_dicts = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in citations]

        # 4a. Persist as dynamic Markdown artifact
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-")[:32]
        db_artifact = crud.create_artifact(
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
