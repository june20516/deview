import pytest
from pathlib import Path
from typer.testing import CliRunner
from deview.cli import app

runner = CliRunner()


def test_cli_status_help():
    """status 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0


def test_cli_search_help():
    """search 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0


def test_cli_ingest_help():
    """ingest 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0


def test_cli_sync_help():
    """sync 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0


def test_cli_hook_install(tmp_path: Path):
    """hook install이 post-merge 스크립트를 생성한다."""
    import git
    repo_path = tmp_path / "hook_repo"
    repo_path.mkdir()
    git.Repo.init(repo_path)

    result = runner.invoke(app, ["hook", "install"], env={"DEVIEW_PROJECT_PATH": str(repo_path)})
    assert result.exit_code == 0

    hook_path = repo_path / ".git" / "hooks" / "post-merge"
    assert hook_path.exists()
    content = hook_path.read_text()
    assert "deview ingest" in content


def test_cli_hook_uninstall(tmp_path: Path):
    """hook uninstall이 post-merge 스크립트를 제거한다."""
    import git
    repo_path = tmp_path / "hook_repo"
    repo_path.mkdir()
    git.Repo.init(repo_path)

    runner.invoke(app, ["hook", "install"], env={"DEVIEW_PROJECT_PATH": str(repo_path)})

    result = runner.invoke(app, ["hook", "uninstall"], env={"DEVIEW_PROJECT_PATH": str(repo_path)})
    assert result.exit_code == 0

    hook_path = repo_path / ".git" / "hooks" / "post-merge"
    assert not hook_path.exists()
