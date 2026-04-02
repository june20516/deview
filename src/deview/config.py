"""설정 로드: .deview.yaml + 환경변수."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    model: str = ""
    api_key: str = ""


@dataclass
class EmbeddingConfig:
    provider: str = "voyage"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)


@dataclass
class GitIngestionConfig:
    target_branch: str = "main"
    max_commits: int | None = None


@dataclass
class IngestionConfig:
    git: GitIngestionConfig = field(default_factory=GitIngestionConfig)


@dataclass
class DeviewConfig:
    scope: str | None = None
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _substitute_env_vars(value: str) -> str:
    """${ENV_VAR} 패턴을 환경변수 값으로 치환한다."""
    def replacer(match: re.Match) -> str:
        env_name = match.group(1)
        return os.environ.get(env_name, match.group(0))
    return _ENV_VAR_PATTERN.sub(replacer, value)


def _parse_providers(raw: dict) -> dict[str, ProviderConfig]:
    providers: dict[str, ProviderConfig] = {}
    for name, settings in raw.items():
        if not isinstance(settings, dict):
            continue
        api_key = settings.get("api_key", "")
        if isinstance(api_key, str):
            api_key = _substitute_env_vars(api_key)
        providers[name] = ProviderConfig(
            model=settings.get("model", ""),
            api_key=api_key,
        )
    return providers


def load_config(project_path: Path) -> DeviewConfig:
    """프로젝트 경로에서 .deview.yaml을 읽어 DeviewConfig를 반환한다."""
    yaml_path = project_path / ".deview.yaml"
    if not yaml_path.exists():
        return DeviewConfig()

    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    embedding_raw = raw.get("embedding", {})
    providers_raw = embedding_raw.get("providers", {})
    embedding = EmbeddingConfig(
        provider=embedding_raw.get("provider", "voyage"),
        providers=_parse_providers(providers_raw),
    )

    git_raw = raw.get("ingestion", {}).get("git", {})
    ingestion = IngestionConfig(
        git=GitIngestionConfig(
            target_branch=git_raw.get("target_branch", "main"),
            max_commits=git_raw.get("max_commits"),
        ),
    )

    return DeviewConfig(
        scope=raw.get("scope"),
        embedding=embedding,
        ingestion=ingestion,
    )
