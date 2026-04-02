from pathlib import Path
from deview.ingestion.markdown import parse_markdown_files


def test_parse_single_file(tmp_path: Path):
    """Markdown 파일을 헤딩 기준으로 분할한다."""
    md_file = tmp_path / "design.md"
    md_file.write_text("""# 프로젝트 설계

## 아키텍처
마이크로서비스 기반 구조를 사용한다.

## 데이터베이스
PostgreSQL을 메인 DB로 사용한다.
""")

    chunks = parse_markdown_files(tmp_path, scope="test/project")
    assert len(chunks) == 2
    assert "마이크로서비스" in chunks[0].content
    assert "PostgreSQL" in chunks[1].content
    assert chunks[0].metadata["section"] == "## 아키텍처"
    assert chunks[0].metadata["source"] == "markdown"


def test_parse_directory(tmp_path: Path):
    """디렉토리 내 모든 .md 파일을 파싱한다."""
    (tmp_path / "a.md").write_text("## 섹션A\n내용A\n")
    (tmp_path / "b.md").write_text("## 섹션B\n내용B\n")
    (tmp_path / "skip.txt").write_text("이건 무시")

    chunks = parse_markdown_files(tmp_path, scope="test/project")
    assert len(chunks) == 2
    contents = {c.content for c in chunks}
    assert any("내용A" in c for c in contents)
    assert any("내용B" in c for c in contents)


def test_parse_no_headings(tmp_path: Path):
    """헤딩이 없는 파일은 전체를 하나의 청크로 처리한다."""
    md_file = tmp_path / "notes.md"
    md_file.write_text("그냥 메모입니다.\n여러 줄.\n")

    chunks = parse_markdown_files(tmp_path, scope="test/project")
    assert len(chunks) == 1
    assert "그냥 메모" in chunks[0].content
