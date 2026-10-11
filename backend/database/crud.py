import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import Conversation, Message, Artifact
from database.schemas import ConversationCreate, ConversationUpdate, MessageCreate, ArtifactCreate


def get_conversation(db: Session, conversation_id: str) -> Optional[Conversation]:
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def list_conversations(db: Session, limit: int = 50, offset: int = 0) -> List[dict]:
    conversations = (
        db.query(Conversation)
        .order_by(desc(Conversation.updated_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for conv in conversations:
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .first()
        )
        msg_count = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .count()
        )
        results.append({
            "id": conv.id,
            "title": conv.title,
            "category": conv.category,
            "artifact_id": conv.artifact_id,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "message_count": msg_count,
            "last_message": last_msg.content[:80] if last_msg else None,
        })
    return results


def create_conversation(db: Session, conv_in: ConversationCreate) -> Conversation:
    conv_id = conv_in.id or f"conv-{uuid.uuid4().hex[:10]}"
    existing = get_conversation(db, conv_id)
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    db_conv = Conversation(
        id=conv_id,
        title=conv_in.title or "New Strategy Discussion",
        category=conv_in.category or "Strategic Planning",
        artifact_id=conv_in.artifact_id,
        created_at=now,
        updated_at=now,
    )
    db.add(db_conv)
    db.commit()
    db.refresh(db_conv)
    return db_conv


def update_conversation(
    db: Session, conversation_id: str, conv_update: ConversationUpdate
) -> Optional[Conversation]:
    db_conv = get_conversation(db, conversation_id)
    if not db_conv:
        return None

    if conv_update.title is not None:
        db_conv.title = conv_update.title
    if conv_update.category is not None:
        db_conv.category = conv_update.category
    if conv_update.artifact_id is not None:
        db_conv.artifact_id = conv_update.artifact_id

    db_conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_conv)
    return db_conv


def delete_conversation(db: Session, conversation_id: str) -> bool:
    db_conv = get_conversation(db, conversation_id)
    if not db_conv:
        return False

    db.delete(db_conv)
    db.commit()
    return True


def create_message(db: Session, msg_in: MessageCreate) -> Message:
    # Ensure conversation exists
    conv = get_conversation(db, msg_in.conversation_id)
    if not conv:
        conv = create_conversation(
            db,
            ConversationCreate(
                id=msg_in.conversation_id,
                title="New Strategy Discussion",
            ),
        )

    now = datetime.now(timezone.utc)
    db_msg = Message(
        conversation_id=msg_in.conversation_id,
        role=msg_in.role,
        content=msg_in.content,
        model=msg_in.model,
        citations=msg_in.citations,
        has_sufficient_context=msg_in.has_sufficient_context,
        eval_count=msg_in.eval_count,
        total_duration=msg_in.total_duration,
        artifact_id=msg_in.artifact_id,
        created_at=now,
    )
    db.add(db_msg)

    # Touch conversation updated_at
    conv.updated_at = now
    # Update title if it's the first message and still default
    if conv.title == "New Strategy Discussion" and msg_in.role == "user":
        content_preview = msg_in.content.strip().split("\n")[0]
        conv.title = content_preview[:40] + ("..." if len(content_preview) > 40 else "")

    db.commit()
    db.refresh(db_msg)
    return db_msg


def get_conversation_messages(db: Session, conversation_id: str) -> List[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )


def create_artifact(db: Session, artifact_in: ArtifactCreate) -> Artifact:
    """
    Persist an artifact into PostgreSQL and associate it with a conversation.
    """
    now = datetime.now(timezone.utc)
    words = len(artifact_in.content.split())
    read_mins = max(1, round(words / 225))
    read_time_str = f"{read_mins} min read"

    db_artifact = Artifact(
        conversation_id=artifact_in.conversation_id,
        title=artifact_in.title,
        artifact_type=artifact_in.artifact_type,
        content=artifact_in.content,
        subtitle=artifact_in.subtitle,
        badge=artifact_in.badge or ("HTML Component" if artifact_in.artifact_type == "html" else "Synthesized Playbook"),
        file_name=artifact_in.file_name or ("component.html" if artifact_in.artifact_type == "html" else "playbook.md"),
        word_count=artifact_in.word_count or words,
        read_time=artifact_in.read_time or read_time_str,
        is_safe=artifact_in.is_safe if artifact_in.is_safe is not None else True,
        security_warnings=artifact_in.security_warnings or [],
        citations=artifact_in.citations or [],
        created_at=now,
        updated_at=now,
    )
    db.add(db_artifact)

    # Link artifact as active artifact on conversation if conversation exists
    if artifact_in.conversation_id:
        conv = get_conversation(db, artifact_in.conversation_id)
        if conv:
            conv.artifact_id = db_artifact.id
            conv.updated_at = now

    db.commit()
    db.refresh(db_artifact)
    return db_artifact


def get_artifact(db: Session, artifact_id: str) -> Optional[Artifact]:
    return db.query(Artifact).filter(Artifact.id == artifact_id).first()


def list_conversation_artifacts(db: Session, conversation_id: str) -> List[Artifact]:
    return (
        db.query(Artifact)
        .filter(Artifact.conversation_id == conversation_id)
        .order_by(desc(Artifact.created_at))
        .all()
    )


def delete_artifact(db: Session, artifact_id: str) -> bool:
    art = get_artifact(db, artifact_id)
    if not art:
        return False
    # If conversation points to this artifact, clear the pointer
    if art.conversation_id:
        conv = get_conversation(db, art.conversation_id)
        if conv and conv.artifact_id == artifact_id:
            conv.artifact_id = None
    db.delete(art)
    db.commit()
    return True


def get_last_message(db: Session, conversation_id: str) -> Optional[Message]:
    """
    Returns the most recent message in the specified conversation.
    """
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .first()
    )


def get_conversation_artifact_by_filename(
    db: Session, conversation_id: str, file_name: str
) -> Optional[Artifact]:
    """
    Returns an artifact in the specified conversation with the given filename.
    """
    return (
        db.query(Artifact)
        .filter(
            Artifact.conversation_id == conversation_id,
            Artifact.file_name == file_name,
        )
        .first()
    )


def upsert_artifact(db: Session, artifact_in: ArtifactCreate) -> Artifact:
    """
    Creates an artifact or updates an existing one if the file_name already exists
    for this conversation, preventing duplicate artifacts on retry attempts.
    """
    if artifact_in.conversation_id and artifact_in.file_name:
        existing = get_conversation_artifact_by_filename(
            db, artifact_in.conversation_id, artifact_in.file_name
        )
        if existing:
            now = datetime.now(timezone.utc)
            words = len(artifact_in.content.split())
            read_mins = max(1, round(words / 225))
            read_time_str = f"{read_mins} min read"

            existing.title = artifact_in.title
            existing.content = artifact_in.content
            existing.subtitle = artifact_in.subtitle or existing.subtitle
            existing.badge = artifact_in.badge or existing.badge
            existing.word_count = artifact_in.word_count or words
            existing.read_time = artifact_in.read_time or read_time_str
            existing.citations = artifact_in.citations or existing.citations
            existing.is_safe = artifact_in.is_safe if artifact_in.is_safe is not None else existing.is_safe
            existing.security_warnings = artifact_in.security_warnings or existing.security_warnings
            existing.updated_at = now

            conv = get_conversation(db, artifact_in.conversation_id)
            if conv:
                conv.artifact_id = existing.id
                conv.updated_at = now

            db.commit()
            db.refresh(existing)
            return existing

    return create_artifact(db, artifact_in)
