import os
import re
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import yaml

class TranscriptDoc(BaseModel):
    episode_slug: str = Field(..., description="Folder or file-based slug for episode")
    guest: str = Field(..., description="Guest name(s)")
    title: str = Field(..., description="Episode title")
    youtube_url: Optional[str] = Field(None, description="YouTube URL")
    video_id: Optional[str] = Field(None, description="YouTube Video ID")
    publish_date: Optional[str] = Field(None, description="Publication date")
    description: Optional[str] = Field(None, description="Episode summary")
    duration: Optional[str] = Field(None, description="Human readable duration")
    content: str = Field(..., min_length=10, description="Full transcript text")
    source_file: str = Field(..., description="Relative or absolute path to source file")


def parse_frontmatter(raw_text: str) -> tuple[Dict[str, Any], str]:
    """
    Extracts YAML frontmatter and body from markdown text.
    Handles malformed delimiters gracefully.
    """
    if not raw_text.startswith("---"):
        return {}, raw_text

    # Match --- frontmatter --- rest
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
    if not match:
        return {}, raw_text

    fm_text, body = match.groups()
    try:
        metadata = yaml.safe_load(fm_text) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except Exception:
        metadata = {}

    return metadata, body.strip()


def parse_transcript_file(file_path: Path) -> Optional[TranscriptDoc]:
    """
    Parses a single transcript markdown file into a TranscriptDoc.
    Returns None if file should be ignored, is empty, or invalid.
    """
    file_path = Path(file_path)

    # Exclude non-transcript files
    ignored_names = {"readme.md", "claude.md", "design.md"}
    if file_path.name.lower() in ignored_names:
        return None

    if not file_path.is_file() or file_path.suffix.lower() != ".md":
        return None

    try:
        raw_text = file_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None

    if not raw_text:
        return None

    metadata, body = parse_frontmatter(raw_text)

    # If body is too short, skip
    if len(body) < 20:
        return None

    # Derive episode slug and guest fallback from directory structure
    parent_dir_name = file_path.parent.name
    guest = str(metadata.get("guest") or parent_dir_name.replace("-", " ").title())
    title = str(metadata.get("title") or f"{guest} Interview")
    
    # YouTube URL formatting
    youtube_url = metadata.get("youtube_url")
    if not youtube_url and metadata.get("video_id"):
        youtube_url = f"https://www.youtube.com/watch?v={metadata['video_id']}"

    # Clean date
    publish_date = metadata.get("publish_date")
    if publish_date:
        publish_date = str(publish_date)

    return TranscriptDoc(
        episode_slug=parent_dir_name,
        guest=guest,
        title=title,
        youtube_url=youtube_url,
        video_id=metadata.get("video_id"),
        publish_date=publish_date,
        description=metadata.get("description"),
        duration=str(metadata.get("duration") or ""),
        content=body,
        source_file=str(file_path),
    )
