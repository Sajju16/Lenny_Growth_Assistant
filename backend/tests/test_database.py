import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models import Conversation, Message
from database.schemas import ConversationCreate, ConversationUpdate, MessageCreate
import database.crud as crud


@pytest.fixture
def db_session():
    """
    Creates an isolated in-memory SQLite database session for unit testing.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_and_get_conversation(db_session):
    conv_in = ConversationCreate(
        id="test-conv-01",
        title="Positioning Strategy Session",
        category="GTM",
        artifact_id="artifact-01",
    )
    created = crud.create_conversation(db_session, conv_in)
    assert created.id == "test-conv-01"
    assert created.title == "Positioning Strategy Session"
    assert created.category == "GTM"
    assert created.artifact_id == "artifact-01"

    fetched = crud.get_conversation(db_session, "test-conv-01")
    assert fetched is not None
    assert fetched.title == "Positioning Strategy Session"


def test_list_conversations_with_counts(db_session):
    crud.create_conversation(db_session, ConversationCreate(id="c1", title="Conv One"))
    crud.create_conversation(db_session, ConversationCreate(id="c2", title="Conv Two"))

    crud.create_message(
        db_session,
        MessageCreate(
            conversation_id="c1",
            role="user",
            content="Hello C1",
        ),
    )
    crud.create_message(
        db_session,
        MessageCreate(
            conversation_id="c1",
            role="assistant",
            content="Reply C1",
        ),
    )

    summaries = crud.list_conversations(db_session)
    assert len(summaries) == 2

    c1_summary = next(s for s in summaries if s["id"] == "c1")
    assert c1_summary["message_count"] == 2
    assert "Reply C1" in c1_summary["last_message"]

    c2_summary = next(s for s in summaries if s["id"] == "c2")
    assert c2_summary["message_count"] == 0


def test_message_ordering_deterministic_on_identical_timestamp(db_session):
    """
    Regression test: When multiple messages share the exact same created_at timestamp,
    secondary ordering ensures:
    1. Reverse-chronological queries (list_conversations, get_last_message) return the assistant response.
    2. Chronological queries (get_conversation_messages) preserve user -> assistant order.
    """
    from datetime import datetime, timezone

    same_time = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    crud.create_conversation(db_session, ConversationCreate(id="c-tie", title="Tie Breaking Conv"))

    # Explicitly create user message and assistant message with identical created_at
    msg_user = Message(
        conversation_id="c-tie",
        role="user",
        content="What is product-market fit?",
        created_at=same_time,
    )
    msg_assistant = Message(
        conversation_id="c-tie",
        role="assistant",
        content="PMF is when retention curves flatten.",
        created_at=same_time,
    )
    db_session.add(msg_user)
    db_session.add(msg_assistant)
    db_session.commit()

    # 1. get_last_message should return the assistant response
    last_msg = crud.get_last_message(db_session, "c-tie")
    assert last_msg is not None
    assert last_msg.role == "assistant"
    assert "retention curves flatten" in last_msg.content

    # 2. list_conversations summary should display the assistant response as last_message
    summaries = crud.list_conversations(db_session)
    tie_summary = next(s for s in summaries if s["id"] == "c-tie")
    assert "retention curves flatten" in tie_summary["last_message"]

    # 3. get_conversation_messages should return in chronological order: user -> assistant
    messages = crud.get_conversation_messages(db_session, "c-tie")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"



def test_update_conversation_metadata(db_session):
    crud.create_conversation(db_session, ConversationCreate(id="c-update", title="Old Title"))

    updated = crud.update_conversation(
        db_session,
        "c-update",
        ConversationUpdate(title="Refined Executive Playbook", category="Pricing Architecture"),
    )
    assert updated.title == "Refined Executive Playbook"
    assert updated.category == "Pricing Architecture"


def test_delete_conversation_cascades_messages(db_session):
    crud.create_conversation(db_session, ConversationCreate(id="c-del", title="To Delete"))
    crud.create_message(
        db_session,
        MessageCreate(conversation_id="c-del", role="user", content="Will be deleted"),
    )

    assert len(crud.get_conversation_messages(db_session, "c-del")) == 1

    success = crud.delete_conversation(db_session, "c-del")
    assert success is True
    assert crud.get_conversation(db_session, "c-del") is None
    assert len(crud.get_conversation_messages(db_session, "c-del")) == 0


def test_create_message_with_citations_and_metadata(db_session):
    crud.create_conversation(db_session, ConversationCreate(id="c-rag", title="RAG Thread"))

    sample_citations = [
        {
            "chunk_id": "chunk_01",
            "guest": "April Dunford",
            "episode_title": "Positioning Masterclass",
            "youtube_url": "https://youtube.com/watch?v=123",
            "relevance_score": 0.88,
            "excerpt": "Positioning is context setting.",
        }
    ]

    msg = crud.create_message(
        db_session,
        MessageCreate(
            conversation_id="c-rag",
            role="assistant",
            content="Here is the strategic positioning advice.",
            model="qwen2.5:3b",
            citations=sample_citations,
            has_sufficient_context=True,
            eval_count=120,
            total_duration=1500000000,
        ),
    )

    assert msg.id.startswith("msg-")
    assert msg.model == "qwen2.5:3b"
    assert len(msg.citations) == 1
    assert msg.citations[0]["guest"] == "April Dunford"
    assert msg.eval_count == 120


def test_session_isolation_independent_messages(db_session):
    """
    Ensure messages in Session A never appear in Session B.
    """
    crud.create_conversation(db_session, ConversationCreate(id="session-alpha", title="Alpha"))
    crud.create_conversation(db_session, ConversationCreate(id="session-beta", title="Beta"))

    crud.create_message(
        db_session,
        MessageCreate(conversation_id="session-alpha", role="user", content="Alpha secret data"),
    )
    crud.create_message(
        db_session,
        MessageCreate(conversation_id="session-beta", role="user", content="Beta public data"),
    )

    alpha_msgs = crud.get_conversation_messages(db_session, "session-alpha")
    beta_msgs = crud.get_conversation_messages(db_session, "session-beta")

    assert len(alpha_msgs) == 1
    assert len(beta_msgs) == 1
    assert alpha_msgs[0].content == "Alpha secret data"
    assert beta_msgs[0].content == "Beta public data"
    assert not any("Alpha" in m.content for m in beta_msgs)
    assert not any("Beta" in m.content for m in alpha_msgs)
