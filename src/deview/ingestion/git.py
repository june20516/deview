"""Git 히스토리 파싱 및 청크 생성."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import git

from deview.ingestion import Chunk

logger = logging.getLogger(__name__)

_COMMENT_PATTERNS = [
    re.compile(r"^\+\s*(?:#|//|/\*|\*|<!--)\s*(.+)", re.MULTILINE),
]

def _extract_comment_additions(diff_text: str) -> list[str]:
    """diff에서 추가된 주석 라인을 추출한다."""
    comments: list[str] = []
    for pattern in _COMMENT_PATTERNS:
        for match in pattern.finditer(diff_text):
            comment = match.group(1).strip()
            if comment and len(comment) > 5:
                comments.append(comment)
    return comments

def _extract_file_paths(diff_index) -> list[str]:
    """diff에서 변경된 파일 경로 목록을 추출한다."""
    paths: list[str] = []
    for diff_item in diff_index:
        if diff_item.b_path:
            paths.append(diff_item.b_path)
        elif diff_item.a_path:
            paths.append(diff_item.a_path)
    return paths

def _summarize_diff(diff_index) -> str:
    """diff를 파일별 변경 요약으로 축소한다."""
    summaries: list[str] = []
    for diff_item in diff_index:
        path = diff_item.b_path or diff_item.a_path or "unknown"
        if diff_item.new_file:
            summaries.append(f"{path} (신규)")
        elif diff_item.deleted_file:
            summaries.append(f"{path} (삭제)")
        else:
            summaries.append(f"{path} (수정)")
    return "변경 파일: " + ", ".join(summaries) if summaries else ""

def parse_git_history(
    repo_path: Path,
    branch: str = "main",
    scope: str = "",
    max_commits: int | None = None,
    since_commit: str | None = None,
) -> list[Chunk]:
    """git 히스토리를 파싱하여 청크 리스트를 반환한다."""
    repo = git.Repo(repo_path)
    chunks: list[Chunk] = []

    # 지정된 브랜치가 없으면 현재 active branch로 폴백한다
    try:
        ref = branch
        repo.commit(ref)
    except git.BadName:
        ref = repo.active_branch.name
        logger.info("브랜치 '%s'를 찾을 수 없어 '%s'로 폴백", branch, ref)

    iter_kwargs: dict = {"rev": ref}
    if max_commits is not None:
        iter_kwargs["max_count"] = max_commits
    commits = list(repo.iter_commits(**iter_kwargs))

    # since_commit이 지정되면 해당 커밋까지 잘라낸다
    if since_commit:
        filtered = []
        for commit in commits:
            if commit.hexsha.startswith(since_commit):
                break
            filtered.append(commit)
        commits = filtered
        logger.info("증분 인덱싱: %s 이후 %d개 커밋 발견", since_commit, len(commits))

    for commit in commits:
        author = commit.author.name or "unknown"
        timestamp = commit.committed_datetime.strftime("%Y-%m-%d")
        message = commit.message.strip()

        if commit.parents:
            diff_index = commit.parents[0].diff(commit, create_patch=True)
        else:
            diff_index = commit.diff(git.NULL_TREE, create_patch=True)

        file_paths = _extract_file_paths(diff_index)
        diff_summary = _summarize_diff(diff_index)

        content_parts = [message]
        if diff_summary:
            content_parts.append(diff_summary)
        commit_content = "\n\n".join(content_parts)

        chunks.append(Chunk(
            content=commit_content,
            metadata={
                "scope": scope,
                "source": "git",
                "author": author,
                "file_paths": json.dumps(file_paths),
                "commit_hash": commit.hexsha[:7],
                "timestamp": timestamp,
            },
        ))

        for diff_item in diff_index:
            try:
                diff_text = diff_item.diff.decode("utf-8", errors="ignore")
            except Exception:
                continue
            comments = _extract_comment_additions(diff_text)
            if comments:
                comment_file = diff_item.b_path or diff_item.a_path or "unknown"
                chunks.append(Chunk(
                    content="주석 추가: " + " | ".join(comments),
                    metadata={
                        "scope": scope,
                        "source": "comment",
                        "author": author,
                        "file_paths": json.dumps([comment_file]),
                        "commit_hash": commit.hexsha[:7],
                        "timestamp": timestamp,
                    },
                ))

    logger.info("Git 히스토리 파싱 완료: %d개 청크 생성", len(chunks))
    return chunks
