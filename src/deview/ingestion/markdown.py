"""Markdown 파일 파싱 및 청크 생성."""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from deview.ingestion.git import Chunk

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Markdown 텍스트를 헤딩 기준으로 (헤딩, 내용) 쌍으로 분할한다."""
    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        stripped = text.strip()
        if stripped:
            return [("", stripped)]
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading = match.group(0)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))
    return sections

def parse_markdown_files(path: Path, scope: str = "") -> list[Chunk]:
    """경로에서 .md 파일을 찾아 청크 리스트를 반환한다."""
    if path.is_file():
        files = [path] if path.suffix == ".md" else []
    else:
        files = sorted(path.rglob("*.md"))

    chunks: list[Chunk] = []
    for md_file in files:
        text = md_file.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(md_file.stat().st_mtime).strftime("%Y-%m-%d")
        sections = _split_by_headings(text)
        for heading, content in sections:
            chunks.append(Chunk(
                content=f"{heading}\n{content}" if heading else content,
                metadata={
                    "scope": scope,
                    "source": "markdown",
                    "file_paths": str(md_file),
                    "section": heading,
                    "timestamp": mtime,
                },
            ))
    return chunks
