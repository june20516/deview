from pathlib import Path
from deview.scope import resolve_scope


def test_scope_from_yaml_override():
    """yaml에 scope가 명시되면 그것을 사용한다."""
    result = resolve_scope(
        yaml_scope="my-project",
        project_path=Path("/some/path"),
    )
    assert result == "my-project"


def test_scope_from_ssh_remote(tmp_path: Path):
    """git SSH remote URL에서 scope를 추론한다."""
    _init_git_repo(tmp_path, "git@github.com:team/my-project.git")
    result = resolve_scope(yaml_scope=None, project_path=tmp_path)
    assert result == "team/my-project"


def test_scope_from_https_remote(tmp_path: Path):
    """git HTTPS remote URL에서 scope를 추론한다."""
    _init_git_repo(tmp_path, "https://github.com/team/my-project.git")
    result = resolve_scope(yaml_scope=None, project_path=tmp_path)
    assert result == "team/my-project"


def test_scope_fallback_to_dirname(tmp_path: Path):
    """git이 아닌 경우 디렉토리명으로 fallback한다."""
    result = resolve_scope(yaml_scope=None, project_path=tmp_path)
    assert result == tmp_path.name


def _init_git_repo(path: Path, remote_url: str) -> None:
    """테스트용 git 저장소를 초기화하고 remote를 설정한다."""
    import git
    repo = git.Repo.init(path)
    repo.create_remote("origin", remote_url)
