import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models import Conversation, Message
from database.schemas import ConversationCreate, MessageCreate
import database.crud as crud

REAL_POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234@127.0.0.1:5432/lenny_growth_db"
)
if REAL_POSTGRES_URL.startswith("postgresql://") and not REAL_POSTGRES_URL.startswith("postgresql+"):
    REAL_POSTGRES_URL = REAL_POSTGRES_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


@pytest.fixture(scope="module")
def real_postgres_db():
    """
    Connects to the actual running PostgreSQL instance on port 5432.
    """
    try:
        engine = create_engine(REAL_POSTGRES_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Real PostgreSQL instance is not reachable: {exc}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    test_conv_id = f"pg-test-{uuid.uuid4().hex[:8]}"

    yield session, test_conv_id

    # Cleanup test data
    try:
        crud.delete_conversation(session, test_conv_id)
        session.close()
    except Exception:
        pass


def test_real_postgres_crud_and_json_citations(real_postgres_db):
    session, conv_id = real_postgres_db

    # 1. Create conversation on real PostgreSQL
    conv = crud.create_conversation(
        session,
        ConversationCreate(
            id=conv_id,
            title="Postgres Verification Session",
            category="Database Testing",
        ),
    )
    assert conv.id == conv_id

    # 2. Persist message with structured JSON citations in PostgreSQL JSON column
    citations_data = [
        {
            "chunk_id": "april-dunford_c0012",
            "guest": "April Dunford",
            "episode_title": "A step-by-step guide to crafting a sales pitch that wins",
            "youtube_url": "https://www.youtube.com/watch?v=-VqmFI9vY7w",
            "relevance_score": 0.824,
            "excerpt": "Product leaders need to master positioning before sales pitch drafting.",
        }
    ]

    msg = crud.create_message(
        session,
        MessageCreate(
            conversation_id=conv_id,
            role="assistant",
            content="Real PostgreSQL persisted message content.",
            model="qwen2.5:3b",
            citations=citations_data,
            has_sufficient_context=True,
        ),
    )
    assert msg.id is not None

    # 3. Query back from PostgreSQL
    fetched_messages = crud.get_conversation_messages(session, conv_id)
    assert len(fetched_messages) == 1
    assert fetched_messages[0].role == "assistant"
    assert fetched_messages[0].content == "Real PostgreSQL persisted message content."
    assert len(fetched_messages[0].citations) == 1
    assert fetched_messages[0].citations[0]["guest"] == "April Dunford"
    assert fetched_messages[0].citations[0]["relevance_score"] == 0.824

    # 4. Verify list_conversations on real PostgreSQL
    summaries = crud.list_conversations(session)
    assert any(s["id"] == conv_id for s in summaries)
