"""설정 로드: ~/.deview/config.yaml (글로벌) + .deview.yaml (프로젝트) + 환경변수."""

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
class AtlassianConfig:
    url: str = ""
    email: str = ""
    api_token: str = ""


@dataclass
class IntegrationsConfig:
    atlassian: AtlassianConfig = field(default_factory=AtlassianConfig)

    @property
    def jira_url(self) -> str:
        return self.atlassian.url

    @property
    def confluence_url(self) -> str:
        if not self.atlassian.url:
            return ""
        return self.atlassian.url.rstrip("/") + "/wiki"

    @property
    def email(self) -> str:
        return self.atlassian.email

    @property
    def api_token(self) -> str:
        return self.atlassian.api_token


@dataclass
class DeviewConfig:
    scope: str | None = None
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")

_GLOBAL_CONFIG_PATH = Path.home() / ".deview" / "config.yaml"


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


def _load_yaml(path: Path) -> dict:
    """YAML 파일을 읽어 dict로 반환한다. 파일이 없으면 빈 dict."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_atlassian(integrations_raw: dict) -> AtlassianConfig:
    """integrations 블록에서 AtlassianConfig를 파싱한다.

    신규 포맷(atlassian 블록) 우선, 레거시 포맷(jira/confluence 개별) 하위호환.
    """
    atlassian_raw = integrations_raw.get("atlassian", {})
    if atlassian_raw:
        return AtlassianConfig(
            url=atlassian_raw.get("url", ""),
            email=atlassian_raw.get("email", ""),
            api_token=_substitute_env_vars(atlassian_raw.get("api_token", "")),
        )

    # 레거시: jira/confluence 개별 설정에서 변환
    jira_raw = integrations_raw.get("jira", {})
    if jira_raw:
        return AtlassianConfig(
            url=jira_raw.get("url", ""),
            email=jira_raw.get("email", ""),
            api_token=_substitute_env_vars(jira_raw.get("api_token", "")),
        )

    return AtlassianConfig()


def load_config(
    project_path: Path,
    global_config_path: Path | None = None,
) -> DeviewConfig:
    """글로벌 설정과 프로젝트 설정을 병합하여 DeviewConfig를 반환한다.

    - 글로벌 (~/.deview/config.yaml): 임베딩 provider, API 키 등 서버 설정
    - 프로젝트 (.deview.yaml): scope, 인덱싱 대상 브랜치 등 프로젝트별 설정
    - 프로젝트 설정이 글로벌과 겹치면 프로젝트 설정이 우선
    """
    global_path = global_config_path or _GLOBAL_CONFIG_PATH
    global_raw = _load_yaml(global_path)
    project_raw = _load_yaml(project_path / ".deview.yaml")

    # 임베딩: 글로벌 기본, 프로젝트가 오버라이드
    global_emb = global_raw.get("embedding", {})
    project_emb = project_raw.get("embedding", {})

    global_providers = _parse_providers(global_emb.get("providers", {}))
    project_providers = _parse_providers(project_emb.get("providers", {}))
    merged_providers = {**global_providers, **project_providers}

    embedding = EmbeddingConfig(
        provider=project_emb.get("provider") or global_emb.get("provider", "voyage"),
        providers=merged_providers,
    )

    # 인제스션: 프로젝트 설정만
    git_raw = project_raw.get("ingestion", {}).get("git", {})
    ingestion = IngestionConfig(
        git=GitIngestionConfig(
            target_branch=git_raw.get("target_branch", "main"),
            max_commits=git_raw.get("max_commits"),
        ),
    )

    # 인테그레이션: 글로벌 설정만 (신규 atlassian 포맷 우선, 레거시 jira/confluence 하위호환)
    integrations_raw = global_raw.get("integrations", {})
    integrations = IntegrationsConfig(
        atlassian=_parse_atlassian(integrations_raw),
    )

    return DeviewConfig(
        scope=project_raw.get("scope"),
        embedding=embedding,
        ingestion=ingestion,
        integrations=integrations,
    )
