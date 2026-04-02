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
