import os
import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger("lenny-growth-database")

# Environment variable for database URL
# Default points to local PostgreSQL running on port 5432
RAW_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234@127.0.0.1:5432/lenny_growth_db"
)

# Normalize postgresql:// to postgresql+psycopg2:// for SQLAlchemy
if RAW_DATABASE_URL.startswith("postgresql://") and not RAW_DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = RAW_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    DATABASE_URL = RAW_DATABASE_URL

# Connect arguments
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
except Exception as e:
    logger.error("Failed to create engine with DATABASE_URL '%s': %s", DATABASE_URL, e)
    # Fallback to local SQLite if postgres configuration fails
    logger.warning("Falling back to sqlite:///./lenny_growth_fallback.db")
    DATABASE_URL = "sqlite:///./lenny_growth_fallback.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    """
    FastAPI dependency yielding an isolated database session per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize all database tables.
    """
    from database.models import Conversation, Message, Artifact
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        raise


def check_db_health() -> dict:
    """
    Check if the database connection is alive and healthy.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "connected": True,
            "engine": engine.dialect.name,
            "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
            "error": None
        }
    except Exception as exc:
        return {
            "connected": False,
            "engine": engine.dialect.name,
            "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
            "error": str(exc)
        }
