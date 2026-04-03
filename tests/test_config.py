import os
from pathlib import Path
from deview.config import DeviewConfig, load_config


def test_default_config():
    """설정 파일 없이 기본값으로 동작한다."""
    config = DeviewConfig()
    assert config.embedding.provider == "voyage"
    assert config.ingestion.git.target_branch == "main"
    assert config.ingestion.git.max_commits is None


def test_load_from_project_yaml(tmp_path: Path):
    """프로젝트 .deview.yaml에서 scope, ingestion 설정을 읽는다."""
    yaml_content = """
scope: "my-project"
ingestion:
  git:
    target_branch: "develop"
    max_commits: 500
"""
    (tmp_path / ".deview.yaml").write_text(yaml_content)

    config = load_config(tmp_path, global_config_path=tmp_path / "nonexistent.yaml")
    assert config.scope == "my-project"
    assert config.ingestion.git.target_branch == "develop"
    assert config.ingestion.git.max_commits == 500


def test_load_from_global_yaml(tmp_path: Path):
    """글로벌 config.yaml에서 임베딩 설정을 읽는다."""
    global_yaml = tmp_path / "global.yaml"
    global_yaml.write_text("""
embedding:
  provider: "openai"
  providers:
    openai:
      model: "text-embedding-3-small"
      api_key: "sk-test-key"
""")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = load_config(project_dir, global_config_path=global_yaml)
    assert config.embedding.provider == "openai"
    assert config.embedding.providers["openai"].model == "text-embedding-3-small"
    assert config.embedding.providers["openai"].api_key == "sk-test-key"


def test_project_overrides_global(tmp_path: Path):
    """프로젝트 설정이 글로벌 설정을 오버라이드한다."""
    global_yaml = tmp_path / "global.yaml"
    global_yaml.write_text("""
embedding:
  provider: "voyage"
  providers:
    voyage:
      api_key: "global-key"
""")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".deview.yaml").write_text("""
embedding:
  provider: "local"
""")

    config = load_config(project_dir, global_config_path=global_yaml)
    assert config.embedding.provider == "local"
    # 글로벌 providers는 유지됨
    assert config.embedding.providers["voyage"].api_key == "global-key"


def test_env_var_substitution(tmp_path: Path):
    """yaml에서 ${ENV_VAR} 형식의 환경변수를 치환한다."""
    os.environ["TEST_VOYAGE_KEY"] = "voy-test-key-123"
    try:
        global_yaml = tmp_path / "global.yaml"
        global_yaml.write_text("""
embedding:
  provider: "voyage"
  providers:
    voyage:
      api_key: "${TEST_VOYAGE_KEY}"
""")
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        config = load_config(project_dir, global_config_path=global_yaml)
        assert config.embedding.providers["voyage"].api_key == "voy-test-key-123"
    finally:
        del os.environ["TEST_VOYAGE_KEY"]


def test_missing_both_returns_defaults(tmp_path: Path):
    """양쪽 파일 다 없으면 기본값을 반환한다."""
    config = load_config(tmp_path, global_config_path=tmp_path / "nonexistent.yaml")
    assert config.scope is None
    assert config.embedding.provider == "voyage"


def test_load_integrations_from_global(tmp_path: Path):
    """글로벌 설정에서 atlassian 통합 integrations를 로드한다."""
    global_yaml = tmp_path / "global.yaml"
    global_yaml.write_text(
        "integrations:\n"
        "  atlassian:\n"
        "    url: 'https://team.atlassian.net'\n"
        "    email: 'user@team.com'\n"
        "    api_token: 'atlas-token-123'\n"
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = load_config(project_dir, global_config_path=global_yaml)
    assert config.integrations.atlassian.url == "https://team.atlassian.net"
    assert config.integrations.atlassian.email == "user@team.com"
    assert config.integrations.atlassian.api_token == "atlas-token-123"
    # 편의 프로퍼티
    assert config.integrations.jira_url == "https://team.atlassian.net"
    assert config.integrations.confluence_url == "https://team.atlassian.net/wiki"
    assert config.integrations.email == "user@team.com"
    assert config.integrations.api_token == "atlas-token-123"


def test_load_integrations_legacy_format(tmp_path: Path):
    """레거시 jira/confluence 개별 설정에서도 AtlassianConfig로 변환된다."""
    global_yaml = tmp_path / "global.yaml"
    global_yaml.write_text(
        "integrations:\n"
        "  jira:\n"
        "    url: 'https://team.atlassian.net'\n"
        "    email: 'user@team.com'\n"
        "    api_token: 'jira-token-123'\n"
        "  confluence:\n"
        "    url: 'https://team.atlassian.net/wiki'\n"
        "    email: 'user@team.com'\n"
        "    api_token: 'conf-token-456'\n"
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = load_config(project_dir, global_config_path=global_yaml)
    # 레거시: jira 블록의 값으로 AtlassianConfig가 채워짐
    assert config.integrations.atlassian.url == "https://team.atlassian.net"
    assert config.integrations.atlassian.email == "user@team.com"
    assert config.integrations.atlassian.api_token == "jira-token-123"


def test_load_integrations_empty(tmp_path: Path):
    """integrations가 없으면 기본값(빈 설정)을 사용한다."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = load_config(project_dir, global_config_path=tmp_path / "nonexistent.yaml")
    assert config.integrations.atlassian.url == ""
    assert config.integrations.jira_url == ""
    assert config.integrations.confluence_url == ""
