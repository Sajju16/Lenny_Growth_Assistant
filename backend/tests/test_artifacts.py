import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from artifacts.sanitizer import validate_and_sanitize_html
from database.schemas import ArtifactCreate
from llm.base import ProviderResponse


client = TestClient(app)


def test_html_sanitizer_safe_html():
    safe_markup = "<div class='card'><h2>Executive Summary</h2><p>Safe content</p></div>"
    is_safe, sanitized, warnings = validate_and_sanitize_html(safe_markup)
    assert is_safe is True
    assert len(warnings) == 0
    assert "Executive Summary" in sanitized
    assert "<!DOCTYPE html>" in sanitized


def test_html_sanitizer_removes_script_tags():
    malicious = "<div><h1>Title</h1><script>alert('XSS Attack!');</script><p>Text</p></div>"
    is_safe, sanitized, warnings = validate_and_sanitize_html(malicious)
    assert is_safe is False
    assert "<script>" not in sanitized
    assert "alert('XSS Attack!')" not in sanitized
    assert any("Disallowed <script>" in w for w in warnings)


def test_html_sanitizer_removes_inline_event_handlers():
    malicious = "<img src='invalid.jpg' onerror='alert(\"hacked\")' onload='stealCookies()' />"
    is_safe, sanitized, warnings = validate_and_sanitize_html(malicious)
    assert is_safe is False
    assert "onerror" not in sanitized
    assert "onload" not in sanitized
    assert any("event handler" in w for w in warnings)


def test_html_sanitizer_neutralizes_javascript_uri():
    malicious = "<a href='javascript:alert(document.cookie)'>Click here</a>"
    is_safe, sanitized, warnings = validate_and_sanitize_html(malicious)
    assert is_safe is False
    assert "javascript:" not in sanitized
    assert 'href="#"' in sanitized
    assert any("javascript:" in w for w in warnings)


def test_create_markdown_artifact_api():
    session_id = f"test-art-session-{uuid.uuid4().hex[:8]}"
    client.post("/api/conversations", json={"id": session_id, "title": "Artifact Test Session"})

    art_payload = {
        "conversation_id": session_id,
        "title": "PLG Growth Architecture",
        "artifact_type": "markdown",
        "content": "# PLG Architecture\n\n## 1. Acquisition Loop\nCompounding viral invites.",
        "badge": "Growth Blueprint",
    }
    resp = client.post("/api/artifacts", json=art_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "PLG Growth Architecture"
    assert data["artifact_type"] == "markdown"
    assert data["is_safe"] is True
    assert data["word_count"] > 0
    art_id = data["id"]

    # Verify retrieval
    get_resp = client.get(f"/api/artifacts/{art_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == art_id

    # Verify conversation lists it
    conv_arts_resp = client.get(f"/api/conversations/{session_id}/artifacts")
    assert conv_arts_resp.status_code == 200
    assert len(conv_arts_resp.json()) == 1

    # Cleanup
    client.delete(f"/api/conversations/{session_id}")


def test_create_html_artifact_with_sanitization():
    session_id = f"test-html-session-{uuid.uuid4().hex[:8]}"
    client.post("/api/conversations", json={"id": session_id, "title": "HTML Session"})

    art_payload = {
        "conversation_id": session_id,
        "title": "Interactive Dashboard Snippet",
        "artifact_type": "html",
        "content": "<div class='metric'><h3>ARR</h3><script>steal()</script><p>$10M</p></div>",
    }
    resp = client.post("/api/artifacts", json=art_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["artifact_type"] == "html"
    assert data["is_safe"] is False  # Flagged because of script tag
    assert "<script>" not in data["content"]
    assert len(data["security_warnings"]) > 0

    client.delete(f"/api/conversations/{session_id}")


def test_ordinary_chat_does_not_create_artifact():
    """
    Ensure normal chat messages do not accidentally become artifacts.
    """
    session_id = f"test-no-art-{uuid.uuid4().hex[:8]}"
    client.post("/api/conversations", json={"id": session_id, "title": "No Artifact Test"})

    mock_resp = ProviderResponse(
        content="Normal quick answer about pricing metrics.",
        model="qwen2.5:3b",
        provider="ollama",
        citations=[],
        has_sufficient_context=True,
    )

    with patch("main.get_llm_provider") as mock_get_p:
        mock_p = MagicMock()
        mock_p.model_name = "qwen2.5:3b"
        mock_p.generate_response = AsyncMock(return_value=mock_resp)
        mock_get_p.return_value = mock_p

        chat_resp = client.post(
            "/api/chat",
            json={
                "message": "What is ARPU?",
                "conversation_id": session_id,
                "use_rag": False,
                "create_artifact": False,
            },
        )
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        assert data["artifact_id"] is None
        assert data["artifact"] is None

    # Check conversation artifacts in DB
    arts_resp = client.get(f"/api/conversations/{session_id}/artifacts")
    assert arts_resp.status_code == 200
    assert len(arts_resp.json()) == 0

    client.delete(f"/api/conversations/{session_id}")


def test_chat_with_explicit_create_artifact():
    """
    Ensure chat creates an artifact only when create_artifact=True.
    """
    session_id = f"test-with-art-{uuid.uuid4().hex[:8]}"
    client.post("/api/conversations", json={"id": session_id, "title": "Explicit Artifact Test"})

    mock_resp = ProviderResponse(
        content="# Pricing Strategy Blueprint\n\n## 1. Value Metric\nTie pricing to usage.",
        model="qwen2.5:3b",
        provider="ollama",
        citations=[],
        has_sufficient_context=True,
    )

    with patch("main.get_llm_provider") as mock_get_p:
        mock_p = MagicMock()
        mock_p.model_name = "qwen2.5:3b"
        mock_p.generate_response = AsyncMock(return_value=mock_resp)
        mock_get_p.return_value = mock_p

        chat_resp = client.post(
            "/api/chat",
            json={
                "message": "Generate a pricing playbook",
                "conversation_id": session_id,
                "use_rag": False,
                "create_artifact": True,
                "artifact_type": "markdown",
                "artifact_title": "Custom Pricing Blueprint",
            },
        )
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        assert data["artifact_id"] is not None
        assert data["artifact"] is not None
        assert data["artifact"]["title"] == "Custom Pricing Blueprint"

    # Verify conversation active artifact was updated
    conv_resp = client.get(f"/api/conversations/{session_id}")
    assert conv_resp.status_code == 200
    conv_data = conv_resp.json()
    assert conv_data["active_artifact"] is not None
    assert conv_data["active_artifact"]["title"] == "Custom Pricing Blueprint"

    client.delete(f"/api/conversations/{session_id}")
