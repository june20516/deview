import os
from pathlib import Path
from deview.config import DeviewConfig, load_config


def test_default_config():
    """설정 파일 없이 기본값으로 동작한다."""
    config = DeviewConfig()
    assert config.embedding.provider == "voyage"
    assert config.ingestion.git.target_branch == "main"
    assert config.ingestion.git.max_commits is None


def test_load_from_yaml(tmp_path: Path):
    """yaml 파일에서 설정을 읽는다."""
    yaml_content = """
scope: "my-project"
embedding:
  provider: "openai"
  providers:
    openai:
      model: "text-embedding-3-small"
      api_key: "sk-test-key"
ingestion:
  git:
    target_branch: "develop"
    max_commits: 500
"""
    yaml_file = tmp_path / ".deview.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(tmp_path)
    assert config.scope == "my-project"
    assert config.embedding.provider == "openai"
    assert config.embedding.providers["openai"].model == "text-embedding-3-small"
    assert config.embedding.providers["openai"].api_key == "sk-test-key"
    assert config.ingestion.git.target_branch == "develop"
    assert config.ingestion.git.max_commits == 500


def test_env_var_substitution(tmp_path: Path, monkeypatch):
    """yaml에서 ${ENV_VAR} 형식의 환경변수를 치환한다."""
    monkeypatch.setenv("VOYAGE_API_KEY", "voy-test-key-123")
    yaml_content = """
embedding:
  provider: "voyage"
  providers:
    voyage:
      api_key: "${VOYAGE_API_KEY}"
"""
    yaml_file = tmp_path / ".deview.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(tmp_path)
    assert config.embedding.providers["voyage"].api_key == "voy-test-key-123"


def test_missing_yaml_returns_defaults(tmp_path: Path):
    """yaml 파일이 없으면 기본값을 반환한다."""
    config = load_config(tmp_path)
    assert config.scope is None
    assert config.embedding.provider == "voyage"
