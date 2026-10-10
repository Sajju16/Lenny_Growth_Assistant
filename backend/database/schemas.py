from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class MessageCreate(BaseModel):
    conversation_id: str
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    model: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    has_sufficient_context: Optional[bool] = True
    eval_count: Optional[int] = None
    total_duration: Optional[int] = None
    artifact_id: Optional[str] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    model: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    has_sufficient_context: Optional[bool] = True
    eval_count: Optional[int] = None
    total_duration: Optional[int] = None
    artifact_id: Optional[str] = None
    created_at: Optional[str] = None


class ConversationCreate(BaseModel):
    id: Optional[str] = Field(default=None, description="Optional custom conversation ID")
    title: Optional[str] = Field(default="New Strategy Discussion", min_length=1)
    category: Optional[str] = Field(default="Strategic Planning")
    artifact_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = None
    artifact_id: Optional[str] = None


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    artifact_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0
    last_message: Optional[str] = None


class ArtifactCreate(BaseModel):
    conversation_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    artifact_type: str = Field(default="markdown", pattern="^(markdown|html)$")
    content: str = Field(..., min_length=1)
    subtitle: Optional[str] = None
    badge: Optional[str] = "Synthesized Playbook"
    file_name: Optional[str] = None
    word_count: Optional[int] = None
    read_time: Optional[str] = None
    is_safe: Optional[bool] = True
    security_warnings: Optional[List[str]] = Field(default_factory=list)
    citations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class ArtifactUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    file_name: Optional[str] = None


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: Optional[str] = None
    title: str
    artifact_type: str
    content: str
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    file_name: Optional[str] = None
    word_count: Optional[int] = None
    read_time: Optional[str] = None
    is_safe: bool = True
    security_warnings: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    artifact_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    messages: List[MessageResponse] = Field(default_factory=list)
    artifacts: List[ArtifactResponse] = Field(default_factory=list)
    active_artifact: Optional[ArtifactResponse] = None

