import pytest
from pathlib import Path
from deview.ingestion.git import parse_git_history, Chunk

import git as gitmodule


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """테스트용 git 저장소를 만든다."""
    repo = gitmodule.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    # 첫 번째 커밋: 파일 생성
    (tmp_path / "main.py").write_text("# Main module\ndef hello():\n    pass\n")
    repo.index.add(["main.py"])
    repo.index.commit("feat: add main module")

    # 두 번째 커밋: 주석 추가
    (tmp_path / "main.py").write_text(
        "# Main module\ndef hello():\n    # 인사를 출력한다\n    print('hello')\n"
    )
    repo.index.add(["main.py"])
    repo.index.commit("feat: implement hello function")

    return tmp_path


def test_parse_git_history(git_repo: Path):
    """git 히스토리에서 청크를 추출한다."""
    chunks = parse_git_history(git_repo, branch="master", scope="test/project")
    assert len(chunks) >= 2

    for chunk in chunks:
        assert chunk.content
        assert chunk.metadata["scope"] == "test/project"
        assert chunk.metadata["source"] in ("git", "comment")
        assert chunk.metadata["author"]
        assert chunk.metadata["timestamp"]


def test_parse_git_history_max_commits(git_repo: Path):
    """max_commits로 인덱싱 범위를 제한한다."""
    chunks = parse_git_history(
        git_repo, branch="master", scope="test/project", max_commits=1,
    )
    commit_chunks = [c for c in chunks if c.metadata["source"] == "git"]
    assert len(commit_chunks) == 1


def test_comment_extraction(git_repo: Path):
    """주석 변경을 별도 청크로 추출한다."""
    chunks = parse_git_history(git_repo, branch="master", scope="test/project")
    comment_chunks = [c for c in chunks if c.metadata["source"] == "comment"]
    assert len(comment_chunks) >= 1
    assert "인사를 출력한다" in comment_chunks[0].content
