"""Scope 추론: yaml > git remote URL > 디렉토리명."""

from __future__ import annotations

import re
from pathlib import Path

import git


_SSH_PATTERN = re.compile(r"git@[^:]+:(.+?)(?:\.git)?$")
_HTTPS_PATTERN = re.compile(r"https?://[^/]+/(.+?)(?:\.git)?$")


def _parse_remote_url(url: str) -> str | None:
    """git remote URL에서 'owner/repo' 형태의 scope를 추출한다."""
    for pattern in (_SSH_PATTERN, _HTTPS_PATTERN):
        match = pattern.match(url)
        if match:
            return match.group(1)
    return None


def _get_git_remote_scope(project_path: Path) -> str | None:
    """프로젝트의 git remote origin URL에서 scope를 추론한다."""
    try:
        repo = git.Repo(project_path, search_parent_directories=True)
        if "origin" not in [r.name for r in repo.remotes]:
            return None
        url = repo.remotes.origin.url
        return _parse_remote_url(url)
    except (git.InvalidGitRepositoryError, git.GitCommandNotFound):
        return None


def resolve_scope(
    yaml_scope: str | None,
    project_path: Path,
) -> str:
    """Scope를 결정한다. 우선순위: yaml > git remote > 디렉토리명."""
    if yaml_scope:
        return yaml_scope

    git_scope = _get_git_remote_scope(project_path)
    if git_scope:
        return git_scope

    return project_path.name
