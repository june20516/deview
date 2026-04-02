"""수동 메모 청크 생성."""
from __future__ import annotations
import uuid
from datetime import datetime
from deview.ingestion.git import Chunk

def create_manual_chunk(content: str, scope: str, file_paths: list[str] | None = None) -> Chunk:
    """수동 메모를 청크로 변환한다."""
    return Chunk(
        content=content,
        metadata={
            "scope": scope,
            "source": "manual",
            "file_paths": ",".join(file_paths) if file_paths else "",
            "timestamp": datetime.now().strftime("%Y-%m-%d"),
        },
    )

def generate_chunk_id() -> str:
    """청크 ID를 생성한다."""
    return f"manual-{uuid.uuid4().hex[:12]}"
