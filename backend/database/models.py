import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Integer,
    BigInteger,
    JSON,
)
from sqlalchemy.orm import relationship
from database.connection import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True, default=generate_uuid, index=True)
    title = Column(String(255), nullable=False, default="New Strategy Discussion")
    category = Column(String(64), nullable=False, default="Strategic Planning")
    artifact_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )
    artifacts = relationship(
        "Artifact",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Artifact.created_at.desc()",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "artifact_id": self.artifact_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }



class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, default=lambda: f"msg-{uuid.uuid4().hex[:12]}", index=True)
    conversation_id = Column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    model = Column(String(64), nullable=True)
    citations = Column(JSON, nullable=True)
    has_sufficient_context = Column(Boolean, default=True)
    eval_count = Column(Integer, nullable=True)
    total_duration = Column(BigInteger, nullable=True)
    artifact_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "model": self.model,
            "citations": self.citations or [],
            "has_sufficient_context": self.has_sufficient_context,
            "eval_count": self.eval_count,
            "total_duration": self.total_duration,
            "artifact_id": self.artifact_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def generate_artifact_id() -> str:
    return f"art-{uuid.uuid4().hex[:12]}"


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(64), primary_key=True, default=generate_artifact_id, index=True)
    conversation_id = Column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    artifact_type = Column(String(32), nullable=False, default="markdown")  # 'markdown' or 'html'
    content = Column(Text, nullable=False)
    subtitle = Column(String(255), nullable=True)
    badge = Column(String(64), nullable=True, default="Synthesized Playbook")
    file_name = Column(String(128), nullable=True)
    word_count = Column(Integer, nullable=True)
    read_time = Column(String(32), nullable=True)
    is_safe = Column(Boolean, default=True)
    security_warnings = Column(JSON, nullable=True)
    citations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="artifacts")

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "title": self.title,
            "artifact_type": self.artifact_type,
            "content": self.content,
            "subtitle": self.subtitle,
            "badge": self.badge,
            "file_name": self.file_name,
            "word_count": self.word_count,
            "read_time": self.read_time,
            "is_safe": self.is_safe,
            "security_warnings": self.security_warnings or [],
            "citations": self.citations or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

