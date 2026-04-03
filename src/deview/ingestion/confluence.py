"""Confluence 페이지 파싱 및 청크 생성."""
from __future__ import annotations

import logging
import re
from html.parser import HTMLParser

from deview.ingestion import Chunk

logger = logging.getLogger(__name__)

_CHUNK_THRESHOLD = 2000  # 이 글자 수 이하면 분할하지 않음


class _HTMLTextExtractor(HTMLParser):
    """HTML에서 텍스트와 헤딩 위치를 추출한다."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._current_heading: str = ""
        self._in_heading: bool = False
        self._heading_positions: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if re.match(r"h[1-3]", tag):
            self._in_heading = True
            self._current_heading = ""

    def handle_endtag(self, tag: str) -> None:
        if re.match(r"h[1-3]", tag) and self._in_heading:
            self._in_heading = False
            pos = len("".join(self._parts))
            self._heading_positions.append((self._current_heading.strip(), pos))

    def handle_data(self, data: str) -> None:
        self._parts.append(data)
        if self._in_heading:
            self._current_heading += data

    def get_text(self) -> str:
        return "".join(self._parts).strip()

    def get_heading_positions(self) -> list[tuple[str, int]]:
        return self._heading_positions


def _strip_html(html: str) -> tuple[str, list[tuple[str, int]]]:
    """HTML에서 텍스트와 헤딩 위치를 추출한다."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text(), extractor.get_heading_positions()


def _split_by_headings(text: str, heading_positions: list[tuple[str, int]]) -> list[tuple[str, str]]:
    """텍스트를 헤딩 위치 기준으로 (헤딩, 내용) 쌍으로 분할한다."""
    if not heading_positions:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    for i, (heading, pos) in enumerate(heading_positions):
        end = heading_positions[i + 1][1] if i + 1 < len(heading_positions) else len(text)
        content = text[pos:end].strip()
        # 헤딩 텍스트 자체가 content 시작에 포함되어 있으므로 제거
        if content.startswith(heading):
            content = content[len(heading):].strip()
        if content:
            sections.append((heading, content))

    return sections


def parse_confluence_pages(pages: list[dict], scope: str = "") -> list[Chunk]:
    """Confluence API 응답의 페이지 목록을 청크 리스트로 변환한다.

    짧은 문서는 통째로, 긴 문서는 헤딩 기준으로 분할하되 document_id로 그루핑한다.
    """
    chunks: list[Chunk] = []

    for page in pages:
        page_id = page["id"]
        title = page.get("title", "")
        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        version = page.get("version", {})
        author = version.get("by", {}).get("displayName", "unknown")
        modified = version.get("when", "")
        timestamp = modified[:10] if modified else ""
        document_id = f"confluence-{page_id}"

        text, heading_positions = _strip_html(body_html)

        if len(text) <= _CHUNK_THRESHOLD or not heading_positions:
            chunks.append(Chunk(
                content=f"{title}\n\n{text}" if text else title,
                metadata={
                    "scope": scope,
                    "source": "confluence",
                    "author": author,
                    "document_id": document_id,
                    "document_title": title,
                    "section": "",
                    "file_paths": "[]",
                    "timestamp": timestamp,
                },
            ))
        else:
            sections = _split_by_headings(text, heading_positions)
            for heading, content in sections:
                chunks.append(Chunk(
                    content=f"{title} > {heading}\n\n{content}" if heading else f"{title}\n\n{content}",
                    metadata={
                        "scope": scope,
                        "source": "confluence",
                        "author": author,
                        "document_id": document_id,
                        "document_title": title,
                        "section": heading,
                        "file_paths": "[]",
                        "timestamp": timestamp,
                    },
                ))

    logger.info("Confluence 페이지 파싱 완료: %d개 청크 생성", len(chunks))
    return chunks
