"""Jira 이슈 파싱 및 청크 생성."""
from __future__ import annotations

import logging

from deview.ingestion import Chunk

logger = logging.getLogger(__name__)


def parse_jira_issues(issues: list[dict], scope: str = "") -> list[Chunk]:
    """Jira API 응답의 이슈 목록을 청크 리스트로 변환한다.

    각 이슈는 제목 + 설명 + 전체 댓글을 하나의 청크로 만든다.
    """
    chunks: list[Chunk] = []

    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]
        summary = fields.get("summary", "")
        description = fields.get("description") or ""
        assignee_obj = fields.get("assignee")
        author = assignee_obj["displayName"] if assignee_obj and assignee_obj.get("displayName") else "unknown"
        updated = fields.get("updated", "")
        timestamp = updated[:10] if updated else ""

        parts = [f"[{key}] {summary}"]
        if description:
            parts.append(f"\n설명:\n{description}")

        comment_entries = fields.get("comment", {}).get("comments", [])
        if comment_entries:
            comment_lines = []
            for c in comment_entries:
                c_author = c.get("author", {}).get("displayName", "unknown")
                c_created = c.get("created", "")[:10]
                c_body = c.get("body", "")
                comment_lines.append(f"[{c_created} {c_author}] {c_body}")
            parts.append("\n댓글:\n" + "\n".join(comment_lines))

        content = "\n".join(parts)

        chunks.append(Chunk(
            content=content,
            metadata={
                "scope": scope,
                "source": "jira",
                "author": author,
                "jira_key": key,
                "file_paths": "[]",
                "timestamp": timestamp,
            },
        ))

    logger.info("Jira 이슈 파싱 완료: %d개 청크 생성", len(chunks))
    return chunks
