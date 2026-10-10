import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from main import app


@pytest.fixture
def client_with_test_db():
    # Use StaticPool so all connections in the test share the same in-memory database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_create_and_list_conversations_api(client_with_test_db):
    # 1. Create a conversation
    resp = client_with_test_db.post(
        "/api/conversations",
        json={"id": "conv-test-1", "title": "Onboarding Loops", "category": "Product Strategy"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "conv-test-1"
    assert data["title"] == "Onboarding Loops"
    assert data["messages"] == []

    # 2. List conversations
    list_resp = client_with_test_db.get("/api/conversations")
    assert list_resp.status_code == 200
    summaries = list_resp.json()
    assert len(summaries) == 1
    assert summaries[0]["id"] == "conv-test-1"


def test_get_and_update_conversation_api(client_with_test_db):
    client_with_test_db.post(
        "/api/conversations",
        json={"id": "conv-test-2", "title": "Initial Title"},
    )

    # Update title
    patch_resp = client_with_test_db.patch(
        "/api/conversations/conv-test-2",
        json={"title": "Updated Executive Memo"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Executive Memo"

    # Get details
    get_resp = client_with_test_db.get("/api/conversations/conv-test-2")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Updated Executive Memo"


def test_delete_conversation_api(client_with_test_db):
    client_with_test_db.post(
        "/api/conversations",
        json={"id": "conv-to-delete", "title": "Temporary Session"},
    )

    del_resp = client_with_test_db.delete("/api/conversations/conv-to-delete")
    assert del_resp.status_code == 200

    # 404 on subsequent get
    get_resp = client_with_test_db.get("/api/conversations/conv-to-delete")
    assert get_resp.status_code == 404


def test_conversation_not_found_errors(client_with_test_db):
    get_resp = client_with_test_db.get("/api/conversations/non-existent-id")
    assert get_resp.status_code == 404

    del_resp = client_with_test_db.delete("/api/conversations/non-existent-id")
    assert del_resp.status_code == 404


@patch("httpx.AsyncClient.post")
def test_chat_persists_messages_in_session(mock_post, client_with_test_db):
    # Mock Ollama chat response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5:3b",
        "created_at": "2026-10-10T12:00:00Z",
        "message": {"content": "Here is the strategic growth analysis."},
        "eval_count": 95,
        "total_duration": 1200000000,
    }
    mock_post.return_value = mock_resp

    # Create conversation first
    client_with_test_db.post(
        "/api/conversations",
        json={"id": "session-live", "title": "Live Strategy Session"},
    )

    # Send chat with conversation_id
    chat_resp = client_with_test_db.post(
        "/api/chat",
        json={
            "message": "What is the key takeaway from the April Dunford episode?",
            "conversation_id": "session-live",
            "use_rag": False,
        },
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["conversation_id"] == "session-live"

    # Verify both user and assistant messages are persisted in DB
    get_conv = client_with_test_db.get("/api/conversations/session-live")
    assert get_conv.status_code == 200
    conv_data = get_conv.json()
    messages = conv_data["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "April Dunford" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"
    assert "strategic growth analysis" in messages[1]["content"]
