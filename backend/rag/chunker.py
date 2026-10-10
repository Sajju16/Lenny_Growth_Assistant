import re
from typing import List
from pydantic import BaseModel, Field
from .parser import TranscriptDoc

class TranscriptChunk(BaseModel):
    chunk_id: str = Field(..., description="Stable deterministic ID for chunk")
    text: str = Field(..., description="Chunk text content")
    episode_slug: str
    guest: str
    title: str
    youtube_url: str = ""
    publish_date: str = ""
    source_file: str
    chunk_index: int


def split_text_into_chunks(text: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> List[str]:
    """
    Splits long transcript text into overlapping chunks, attempting to break at paragraph
    or newline boundaries first.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    # Split primarily on double newlines or speaker turns
    paragraphs = re.split(r'(\n\n+)', text)
    
    current_chunk = []
    current_len = 0

    for part in paragraphs:
        part_len = len(part)
        if current_len + part_len > chunk_size and current_chunk:
            chunk_str = "".join(current_chunk).strip()
            if chunk_str:
                chunks.append(chunk_str)
            
            # Keep overlap from the end of the current chunk
            overlap_text = chunk_str[-chunk_overlap:] if len(chunk_str) > chunk_overlap else chunk_str
            current_chunk = [overlap_text, part]
            current_len = len(overlap_text) + part_len
        else:
            current_chunk.append(part)
            current_len += part_len

    if current_chunk:
        tail = "".join(current_chunk).strip()
        if tail and (not chunks or tail != chunks[-1]):
            chunks.append(tail)

    # In case any individual chunk is excessively large (no newlines)
    final_chunks = []
    for c in chunks:
        if len(c) > chunk_size * 2:
            # Hard window splitting
            for start in range(0, len(c), chunk_size - chunk_overlap):
                segment = c[start:start + chunk_size].strip()
                if segment:
                    final_chunks.append(segment)
        else:
            final_chunks.append(c)

    return final_chunks


def chunk_transcript(
    doc: TranscriptDoc, 
    chunk_size: int = 1200, 
    chunk_overlap: int = 200
) -> List[TranscriptChunk]:
    """
    Splits a TranscriptDoc into structured, traceable TranscriptChunks with stable IDs.
    """
    text_chunks = split_text_into_chunks(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    structured_chunks = []

    for idx, text in enumerate(text_chunks):
        if not text.strip():
            continue
        
        # Stable chunk ID format
        chunk_id = f"{doc.episode_slug}_c{idx:04d}"
        
        structured_chunks.append(
            TranscriptChunk(
                chunk_id=chunk_id,
                text=text,
                episode_slug=doc.episode_slug,
                guest=doc.guest,
                title=doc.title,
                youtube_url=doc.youtube_url or "",
                publish_date=doc.publish_date or "",
                source_file=doc.source_file,
                chunk_index=idx,
            )
        )

    return structured_chunks
