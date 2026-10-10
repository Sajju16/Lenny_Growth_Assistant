import os
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from sqlalchemy.orm import Session

from rag.vector_store import VectorStore, EMBEDDING_MODEL
from rag.retriever import KnowledgeRetriever, Citation
from rag.ingest import run_ingestion

from database.connection import get_db, init_db, check_db_health
from database.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ConversationSummary,
    ConversationDetail,
    MessageCreate,
    MessageResponse,
    ArtifactCreate,
    ArtifactResponse,
    ArtifactUpdate,
)
import database.crud as crud

from llm import (
    get_llm_provider,
    BaseLLMProvider,
    OllamaProvider,
    AnthropicProvider,
    is_valid_anthropic_key,
    GROUNDED_SYSTEM_PROMPT,
)
from agent import ClaudeTranscriptAgent
from artifacts import validate_and_sanitize_html
from skills import generate_ship30_essay, extract_title_from_markdown

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lenny-growth-backend")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

GROUNDED_SYSTEM_PROMPT = (
    "You are Lenny Growth Assistant, an executive product intelligence advisor. "
    "Your objective is to answer the user's question strictly and accurately based on the "
    "verified transcript excerpts provided from Lenny's Podcast archives.\n\n"
    "CRITICAL GROUNDING INSTRUCTIONS:\n"
    "1. Base your response SOLELY on the transcript excerpts provided below. Do not guess or invent facts.\n"
    "2. If the provided excerpts do not contain enough relevant information to answer with confidence, "
    "you MUST explicitly state: 'Based on the verified podcast transcripts currently indexed, there is insufficient evidence to answer this question.'\n"
    "3. Directly cite and attribute advice, playbooks, and frameworks to the specific guest(s) named in the excerpts.\n"
    "4. Format your advice with crisp executive structure, bold key concepts, and numbered points."
)

app = FastAPI(
    title="Lenny Growth Assistant Backend",
    description="FastAPI service connecting Lenny Growth Assistant to PostgreSQL persistence, Ollama runtime, and ChromaDB RAG knowledge base",
    version="0.4.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton RAG instances
vector_store = VectorStore()
retriever = KnowledgeRetriever(vector_store=vector_store)


@app.on_event("startup")
def on_startup():
    try:
        init_db()
        logger.info("Database schemas initialized.")
    except Exception as exc:
        logger.error("Startup database initialization warning: %s", exc)


class ChatMessageItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$", description="Role: user, assistant, or system")
    content: str = Field(..., min_length=1, description="Message text content")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's query message")
    model: Optional[str] = Field(default=None, description="Model identifier (e.g. qwen2.5:3b or claude-3-5-sonnet-20241022)")
    history: Optional[List[ChatMessageItem]] = Field(default_factory=list, description="Prior conversation messages")
    use_rag: Optional[bool] = Field(default=True, description="Enable local transcript retrieval grounding")
    conversation_id: Optional[str] = Field(default=None, description="Optional active conversation/session ID")
    provider: Optional[str] = Field(default=None, description="LLM provider: 'ollama' or 'anthropic'")
    use_agent: Optional[bool] = Field(default=False, description="Enable Claude autonomous agent mode with tool execution")
    skill: Optional[str] = Field(default=None, description="Optional skill execution ('essay' or 'ship30')")
    create_artifact: Optional[bool] = Field(default=False, description="Explicitly generate a dynamic artifact")
    artifact_type: Optional[str] = Field(default="markdown", pattern="^(markdown|html)$", description="Type of artifact: 'markdown' or 'html'")
    artifact_title: Optional[str] = Field(default=None, description="Custom title for generated artifact")


class ChatResponse(BaseModel):
    response: str
    model: str
    provider: str = Field(default="ollama", description="Active LLM provider used")
    created_at: Optional[str] = None
    done: bool = True
    citations: List[Citation] = Field(default_factory=list, description="Structured verified citations")
    has_sufficient_context: bool = True
    eval_count: Optional[int] = None
    total_duration: Optional[int] = None
    conversation_id: Optional[str] = None
    artifact_id: Optional[str] = None
    artifact: Optional[ArtifactResponse] = None


class EssayRequest(BaseModel):
    topic: str = Field(..., min_length=2, description="Essay topic or growth strategy theme")
    conversation_id: Optional[str] = Field(default=None, description="Optional active conversation session ID")
    provider: Optional[str] = Field(default=None, description="LLM provider: 'ollama' or 'anthropic'")
    model: Optional[str] = Field(default=None, description="Optional model override")


class EssayResponse(BaseModel):
    topic: str
    essay: str
    title: str
    word_count: int
    read_time: str
    citations: List[Citation] = Field(default_factory=list)
    has_sufficient_context: bool = True
    artifact_id: Optional[str] = None
    artifact: Optional[ArtifactResponse] = None
    conversation_id: Optional[str] = None
    model: str
    provider: str



class IngestionRequest(BaseModel):
    limit: Optional[int] = Field(default=10, description="Number of episodes to index")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Check the health of FastAPI, PostgreSQL database, Ollama, ChromaDB, and configured LLM providers.
    """
    ollama_status = {
        "connected": False,
        "url": OLLAMA_BASE_URL,
        "chat_model": DEFAULT_MODEL,
        "chat_model_available": False,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_model_available": False,
        "available_models": [],
        "error": None,
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                ollama_status["connected"] = True
                ollama_status["available_models"] = models
                ollama_status["chat_model_available"] = any(DEFAULT_MODEL in m for m in models)
                ollama_status["embedding_model_available"] = any(EMBEDDING_MODEL in m for m in models)
            else:
                ollama_status["error"] = f"Ollama returned HTTP {resp.status_code}"
    except httpx.ConnectError:
        ollama_status["error"] = f"Could not connect to Ollama at {OLLAMA_BASE_URL}. Ensure Ollama is running."
    except Exception as exc:
        ollama_status["error"] = str(exc)

    # Anthropic Cloud Provider health check
    anthropic_provider = AnthropicProvider()
    anthropic_status = await anthropic_provider.check_health()

    kb_stats = vector_store.get_stats()
    db_stats = check_db_health()

    configured_provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if configured_provider == "anthropic":
        active_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        active_provider_ok = anthropic_status.get("connected", False)
    else:
        active_model = DEFAULT_MODEL
        active_provider_ok = ollama_status["connected"]

    overall_status = "ok" if (active_provider_ok and kb_stats.get("is_ready") and db_stats.get("connected")) else "degraded"

    return {
        "status": overall_status,
        "backend": "healthy",
        "llm_provider": configured_provider,
        "active_provider": configured_provider,
        "active_model": active_model,
        "database": db_stats,
        "ollama": ollama_status,
        "anthropic": anthropic_status,
        "knowledge_base": kb_stats,
        "available_providers": ["ollama", "anthropic"],
    }



# ==============================================================================
# Conversation Persistence API
# ==============================================================================

@app.post("/api/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def create_conversation_endpoint(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new conversation session.
    """
    conv = crud.create_conversation(db, payload)
    return {
        "id": conv.id,
        "title": conv.title,
        "category": conv.category,
        "artifact_id": conv.artifact_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": [],
        "artifacts": [],
        "active_artifact": None,
    }


@app.get("/api/conversations", response_model=List[ConversationSummary])
async def list_conversations_endpoint(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    List all persistent conversations sorted by most recent activity.
    """
    return crud.list_conversations(db, limit=limit, offset=offset)


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve full conversation details including chronologically ordered messages,
    citations, and associated dynamic artifacts.
    """
    conv = crud.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    messages = crud.get_conversation_messages(db, conversation_id)
    artifacts = crud.list_conversation_artifacts(db, conversation_id)
    
    active_artifact = None
    if conv.artifact_id:
        active_art = crud.get_artifact(db, conv.artifact_id)
        if active_art:
            active_artifact = active_art.to_dict()
    elif artifacts:
        active_artifact = artifacts[0].to_dict()

    return {
        "id": conv.id,
        "title": conv.title,
        "category": conv.category,
        "artifact_id": conv.artifact_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": [m.to_dict() for m in messages],
        "artifacts": [a.to_dict() for a in artifacts],
        "active_artifact": active_artifact,
    }


# ==============================================================================
# Dynamic Artifact Management & Security Endpoints
# ==============================================================================

@app.post("/api/artifacts", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact_endpoint(payload: ArtifactCreate, db: Session = Depends(get_db)):
    """
    Explicitly create and persist an artifact (Markdown or HTML) associated with a conversation.
    Applies security validation and sanitization for HTML artifacts.
    """
    if payload.artifact_type == "html":
        is_safe, sanitized_content, warnings = validate_and_sanitize_html(payload.content)
        payload.content = sanitized_content
        payload.is_safe = is_safe
        payload.security_warnings = warnings
    else:
        payload.is_safe = True
        payload.security_warnings = []

    art = crud.create_artifact(db, payload)
    return art.to_dict()


@app.get("/api/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_endpoint(artifact_id: str, db: Session = Depends(get_db)):
    """
    Retrieve artifact content, type, and security metadata.
    """
    art = crud.get_artifact(db, artifact_id)
    if not art:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )
    return art.to_dict()


@app.get("/api/conversations/{conversation_id}/artifacts", response_model=List[ArtifactResponse])
async def list_conversation_artifacts_endpoint(conversation_id: str, db: Session = Depends(get_db)):
    """
    List all dynamic artifacts generated within this conversation session.
    """
    artifacts = crud.list_conversation_artifacts(db, conversation_id)
    return [a.to_dict() for a in artifacts]


@app.delete("/api/artifacts/{artifact_id}")
async def delete_artifact_endpoint(artifact_id: str, db: Session = Depends(get_db)):
    """
    Delete an artifact from PostgreSQL persistence.
    """
    deleted = crud.delete_artifact(db, artifact_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )
    return {"status": "success", "message": f"Artifact '{artifact_id}' deleted."}


# ==============================================================================
# Ship 30 for 30 Essay Skill Endpoint
# ==============================================================================

@app.post("/api/skills/essay", response_model=EssayResponse)
async def generate_essay_endpoint(payload: EssayRequest, db: Session = Depends(get_db)):
    """
    Executes the 'Ship 30 for 30' Essay Skill on the requested topic.
    Generates an approximately 1,250-word structured executive essay strictly grounded
    in retrieved Lenny's Podcast transcripts. Automatically persists the essay both as
    a conversation message and as a dynamic Markdown artifact.
    """
    provider_name = (payload.provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
    llm_provider = get_llm_provider(provider_name)
    if payload.model:
        llm_provider._model_name = payload.model

    result = await generate_ship30_essay(
        topic=payload.topic,
        provider=llm_provider,
        retriever=retriever,
        conversation_id=payload.conversation_id,
        db=db,
    )

    artifact_obj = None
    if result.artifact_id:
        db_art = crud.get_artifact(db, result.artifact_id)
        if db_art:
            artifact_obj = db_art.to_dict()

    return EssayResponse(
        topic=result.topic,
        essay=result.essay_content,
        title=result.title,
        word_count=result.word_count,
        read_time=result.read_time,
        citations=result.citations,
        has_sufficient_context=result.has_sufficient_context,
        artifact_id=result.artifact_id,
        artifact=artifact_obj,
        conversation_id=result.conversation_id,
        model=result.model,
        provider=result.provider,
    )



@app.patch("/api/conversations/{conversation_id}", response_model=ConversationSummary)
async def update_conversation_endpoint(
    conversation_id: str,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
):
    """
    Update conversation metadata (title, category, artifact_id).
    """
    conv = crud.update_conversation(db, conversation_id, payload)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    msg_count = len(conv.messages) if conv.messages else 0
    return {
        "id": conv.id,
        "title": conv.title,
        "category": conv.category,
        "artifact_id": conv.artifact_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "message_count": msg_count,
        "last_message": conv.messages[-1].content[:80] if conv.messages else None,
    }


@app.delete("/api/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
async def delete_conversation_endpoint(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a conversation and all its persisted messages.
    """
    success = crud.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return {"status": "success", "message": f"Conversation '{conversation_id}' deleted."}


# ==============================================================================
# Knowledge & RAG Endpoints
# ==============================================================================

@app.get("/api/knowledge/status")
async def knowledge_status():
    """
    Returns index readiness, total chunks, episode count, and embedding model.
    """
    stats = vector_store.get_stats()
    return stats


@app.post("/api/knowledge/ingest")
async def trigger_ingestion(request: IngestionRequest, background_tasks: BackgroundTasks):
    """
    Triggers local transcript ingestion safely.
    """
    limit = request.limit or 10
    try:
        res = run_ingestion(limit=limit)
        return {
            "status": "success",
            "message": f"Successfully ingested {res['processed_files']} episodes ({res['total_chunks_indexed']} chunks).",
            "details": res,
        }
    except Exception as exc:
        logger.error("Ingestion error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ==============================================================================
# Chat Endpoint with Persistent Conversation Support
# ==============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a validated prompt to configurable LLM provider (Ollama or Anthropic Claude)
    or execute autonomous Claude Agent with transcript tool grounding and PostgreSQL persistence.
    """
    # 1. Resolve Provider
    provider_name = (request.provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()

    if request.use_agent:
        # Agent execution path (Assignment-required Claude Agent integration)
        logger.info("Executing autonomous ClaudeTranscriptAgent (conv_id=%s)", request.conversation_id)
        target_model = request.model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    else:
        # Provider execution path
        llm_provider = get_llm_provider(provider_name)
        target_model = request.model or llm_provider.model_name
        logger.info(
            "Chat request via provider '%s' (model='%s', use_rag=%s, conv_id=%s)",
            provider_name,
            target_model,
            request.use_rag,
            request.conversation_id,
        )

    conv_id = request.conversation_id
    if conv_id:
        # Ensure conversation session exists in database
        conv = crud.get_conversation(db, conv_id)
        if not conv:
            crud.create_conversation(db, ConversationCreate(id=conv_id, title="New Strategy Discussion"))

        # Persist user message
        crud.create_message(
            db=db,
            msg_in=MessageCreate(
                conversation_id=conv_id,
                role="user",
                content=request.message,
                model=target_model,
            ),
        )

    # 2. Skill Execution Path (e.g. Ship 30 for 30 Essay Skill)
    if request.skill in ("essay", "ship30"):
        logger.info("Executing Ship 30 for 30 Essay Skill via /api/chat (conv_id=%s)", conv_id)
        llm_provider = get_llm_provider(provider_name)
        if target_model:
            llm_provider._model_name = target_model

        essay_res = await generate_ship30_essay(
            topic=request.message,
            provider=llm_provider,
            retriever=retriever,
            conversation_id=conv_id,
            db=db,
        )

        artifact_obj = None
        if essay_res.artifact_id and db:
            db_art = crud.get_artifact(db, essay_res.artifact_id)
            if db_art:
                artifact_obj = db_art.to_dict()

        return ChatResponse(
            response=essay_res.essay_content,
            model=essay_res.model,
            provider=essay_res.provider,
            citations=essay_res.citations,
            has_sufficient_context=essay_res.has_sufficient_context,
            conversation_id=conv_id,
            artifact_id=essay_res.artifact_id,
            artifact=artifact_obj,
            done=True,
        )

    # 3. Agent Execution Path
    if request.use_agent:
        agent = ClaudeTranscriptAgent(retriever=retriever, model_name=target_model)
        agent_res = await agent.run(
            prompt=request.message,
            history=[item.dict() for item in (request.history or [])],
        )

        artifact_id = None
        artifact_obj = None

        if conv_id:
            citation_dicts = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in agent_res.citations]
            
            # Explicit artifact generation if requested
            if request.create_artifact:
                art_title = request.artifact_title or extract_title_from_markdown(agent_res.content, "Agent Executive Artifact")
                is_safe, sanitized, warnings = (True, agent_res.content, [])
                if request.artifact_type == "html":
                    is_safe, sanitized, warnings = validate_and_sanitize_html(agent_res.content)
                db_art = crud.create_artifact(
                    db=db,
                    artifact_in=ArtifactCreate(
                        conversation_id=conv_id,
                        title=art_title,
                        artifact_type=request.artifact_type or "markdown",
                        content=sanitized,
                        is_safe=is_safe,
                        security_warnings=warnings,
                        citations=citation_dicts,
                    ),
                )
                artifact_id = db_art.id
                artifact_obj = db_art.to_dict()

            crud.create_message(
                db=db,
                msg_in=MessageCreate(
                    conversation_id=conv_id,
                    role="assistant",
                    content=agent_res.content,
                    model=agent_res.model,
                    citations=citation_dicts,
                    has_sufficient_context=agent_res.has_sufficient_context,
                    eval_count=agent_res.eval_count,
                    total_duration=agent_res.total_duration,
                    artifact_id=artifact_id,
                ),
            )

        return ChatResponse(
            response=agent_res.content,
            model=agent_res.model,
            provider="anthropic-agent",
            citations=agent_res.citations,
            has_sufficient_context=agent_res.has_sufficient_context,
            eval_count=agent_res.eval_count,
            total_duration=agent_res.total_duration,
            conversation_id=conv_id,
            artifact_id=artifact_id,
            artifact=artifact_obj,
            done=True,
        )

    # 4. Provider Generation Path (Ollama or Anthropic Claude)
    citations: List[Citation] = []
    has_sufficient_context = True
    context_block = ""

    # RAG Retrieval Step
    if request.use_rag:
        try:
            retrieval_res = retriever.retrieve(query=request.message, top_k=4)
            citations = retrieval_res.citations
            has_sufficient_context = retrieval_res.has_sufficient_context
            context_block = retrieval_res.context_text

            if not has_sufficient_context:
                logger.info("Insufficient evidence retrieved for: '%s'", request.message)
                refusal_response = (
                    "Based on the verified podcast transcripts currently indexed in the knowledge base, "
                    "there is insufficient evidence to answer this question. Please ask about topics covered "
                    "in the indexed episodes (e.g. founder-led sales, positioning, PMF benchmarks, pricing architecture, or PLG loops)."
                )

                if conv_id:
                    crud.create_message(
                        db=db,
                        msg_in=MessageCreate(
                            conversation_id=conv_id,
                            role="assistant",
                            content=refusal_response,
                            model=target_model,
                            citations=[],
                            has_sufficient_context=False,
                        ),
                    )

                return ChatResponse(
                    response=refusal_response,
                    model=target_model,
                    provider=provider_name,
                    citations=[],
                    has_sufficient_context=False,
                    done=True,
                    conversation_id=conv_id,
                )
        except Exception as exc:
            logger.error("Retrieval pipeline failure: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Knowledge retrieval error: {str(exc)}",
            )

    # Invoke selected provider
    response_obj = await llm_provider.generate_response(
        prompt=request.message,
        history=[item.dict() for item in (request.history or [])],
        context_text=context_block,
        citations=citations,
        has_sufficient_context=has_sufficient_context,
    )

    artifact_id = None
    artifact_obj = None

    # Persist assistant response and optional artifact to database
    if conv_id:
        citation_dicts = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in response_obj.citations]

        # Explicit artifact generation if requested
        if request.create_artifact:
            art_title = request.artifact_title or extract_title_from_markdown(response_obj.content, "Synthesized Growth Artifact")
            is_safe, sanitized, warnings = (True, response_obj.content, [])
            if request.artifact_type == "html":
                is_safe, sanitized, warnings = validate_and_sanitize_html(response_obj.content)
            db_art = crud.create_artifact(
                db=db,
                artifact_in=ArtifactCreate(
                    conversation_id=conv_id,
                    title=art_title,
                    artifact_type=request.artifact_type or "markdown",
                    content=sanitized,
                    is_safe=is_safe,
                    security_warnings=warnings,
                    citations=citation_dicts,
                ),
            )
            artifact_id = db_art.id
            artifact_obj = db_art.to_dict()

        crud.create_message(
            db=db,
            msg_in=MessageCreate(
                conversation_id=conv_id,
                role="assistant",
                content=response_obj.content,
                model=response_obj.model,
                citations=citation_dicts,
                has_sufficient_context=response_obj.has_sufficient_context,
                eval_count=response_obj.eval_count,
                total_duration=response_obj.total_duration,
                artifact_id=artifact_id,
            ),
        )

    return ChatResponse(
        response=response_obj.content,
        model=response_obj.model,
        provider=response_obj.provider,
        citations=response_obj.citations,
        has_sufficient_context=response_obj.has_sufficient_context,
        eval_count=response_obj.eval_count,
        total_duration=response_obj.total_duration,
        conversation_id=conv_id,
        artifact_id=artifact_id,
        artifact=artifact_obj,
        done=True,
    )


