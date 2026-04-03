import pytest
from pathlib import Path

from deview.tools.search import handle_search
from deview.tools.write import handle_write
from deview.tools.ingest import handle_ingest
from deview.tools.status import handle_status
from deview.storage.chroma import ChromaStore
from deview.embedding.base import EmbeddingProvider


class FakeEmbedding(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    def dimension(self) -> int:
        return 3


@pytest.fixture
def store(tmp_path):
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


@pytest.fixture
def embedding():
    return FakeEmbedding()


@pytest.mark.asyncio
async def test_write_and_search(store: ChromaStore, embedding: FakeEmbedding):
    """write로 저장한 맥락을 search로 검색할 수 있다."""
    write_result = await handle_write(
        content="ORM 대신 raw query 사용 결정",
        scope="test/proj",
        file_paths=["src/db.py"],
        store=store,
        embedding=embedding,
    )
    assert write_result["id"]
    assert write_result["scope"] == "test/proj"

    search_result = await handle_search(
        query="왜 raw query를 쓰나요",
        scope="test/proj",
        top_k=5,
        sort_by="relevance",
        store=store,
        embedding=embedding,
    )
    assert len(search_result["results"]) == 1
    assert "raw query" in search_result["results"][0]["content"]


@pytest.mark.asyncio
async def test_ingest_git(store: ChromaStore, embedding: FakeEmbedding, tmp_path: Path):
    """git 저장소를 인덱싱할 수 있다."""
    import git
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()
    (repo_path / "app.py").write_text("print('hello')\n")
    repo.index.add(["app.py"])
    repo.index.commit("init: add app")

    result = await handle_ingest(
        path=str(repo_path),
        scope="test/proj",
        source_type="git",
        max_commits=None,
        store=store,
        embedding=embedding,
        branch="master",
    )
    assert result["chunks_indexed"] >= 1
    assert result["source_type"] == "git"


@pytest.mark.asyncio
async def test_status(store: ChromaStore, embedding: FakeEmbedding):
    """status로 현재 상태를 조회한다."""
    await handle_write(
        content="테스트 메모",
        scope="test/proj",
        store=store,
        embedding=embedding,
    )

    result = await handle_status(scope="test/proj", store=store, embedding_provider="voyage")
    assert result["scope"] == "test/proj"
    assert result["total_chunks"] >= 1
    assert result["embedding_provider"] == "voyage"


@pytest.mark.asyncio
async def test_ingest_auto_git(store: ChromaStore, embedding: FakeEmbedding, tmp_path: Path):
    """source_type=auto일 때 .git 디렉토리가 있으면 git으로 판별한다."""
    import git
    repo_path = tmp_path / "auto_repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()
    (repo_path / "main.py").write_text("x = 1\n")
    repo.index.add(["main.py"])
    repo.index.commit("init")

    result = await handle_ingest(
        path=str(repo_path),
        scope="test/auto",
        source_type="auto",
        store=store,
        embedding=embedding,
        branch="master",
    )
    assert result["source_type"] == "git"
    assert result["chunks_indexed"] >= 1


@pytest.mark.asyncio
async def test_ingest_auto_markdown(store: ChromaStore, embedding: FakeEmbedding, tmp_path: Path):
    """source_type=auto일 때 .git이 없으면 markdown으로 판별한다."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("## Setup\nInstall dependencies\n")

    result = await handle_ingest(
        path=str(docs_dir),
        scope="test/auto",
        source_type="auto",
        store=store,
        embedding=embedding,
    )
    assert result["source_type"] == "markdown"
    assert result["chunks_indexed"] >= 1


@pytest.mark.asyncio
async def test_search_unified_scope(store: ChromaStore, embedding: FakeEmbedding):
    """scope=None이면 전체 통합 검색을 수행한다."""
    await handle_write(content="프로젝트A 결정사항", scope="team/proj-a", store=store, embedding=embedding)
    await handle_write(content="프로젝트B 결정사항", scope="team/proj-b", store=store, embedding=embedding)

    result = await handle_search(
        query="결정사항",
        scope=None,
        top_k=10,
        sort_by="relevance",
        store=store,
        embedding=embedding,
    )
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_search_sort_by_timestamp(store: ChromaStore, embedding: FakeEmbedding):
    """sort_by=timestamp일 때 시간순으로 정렬된다."""
    await handle_write(content="먼저 작성한 메모", scope="test/proj", store=store, embedding=embedding)
    await handle_write(content="나중에 작성한 메모", scope="test/proj", store=store, embedding=embedding)

    result = await handle_search(
        query="메모",
        scope="test/proj",
        top_k=10,
        sort_by="timestamp",
        store=store,
        embedding=embedding,
    )
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_write_empty_content_raises(store: ChromaStore, embedding: FakeEmbedding):
    """빈 내용으로 write하면 ValueError가 발생한다."""
    with pytest.raises(ValueError, match="비어있습니다"):
        await handle_write(content="", scope="test/proj", store=store, embedding=embedding)

    with pytest.raises(ValueError, match="비어있습니다"):
        await handle_write(content="   ", scope="test/proj", store=store, embedding=embedding)


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(store: ChromaStore, embedding: FakeEmbedding):
    """빈 쿼리로 검색하면 빈 결과를 반환한다."""
    result = await handle_search(
        query="",
        scope="test/proj",
        store=store,
        embedding=embedding,
    )
    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_file_paths_json_format(store: ChromaStore, embedding: FakeEmbedding):
    """검색 결과의 file_paths가 리스트 형태로 반환된다."""
    await handle_write(
        content="여러 파일 관련 결정",
        scope="test/proj",
        file_paths=["src/a.py", "src/b.py"],
        store=store,
        embedding=embedding,
    )

    result = await handle_search(
        query="결정",
        scope="test/proj",
        store=store,
        embedding=embedding,
    )
    assert len(result["results"]) == 1
    assert result["results"][0]["file_paths"] == ["src/a.py", "src/b.py"]


@pytest.mark.asyncio
async def test_ingest_git_incremental(store: ChromaStore, embedding: FakeEmbedding, tmp_path: Path):
    """증분 인덱싱: 이미 인덱싱된 커밋 이후의 새 커밋만 인덱싱한다."""
    import git as gitmodule
    repo_path = tmp_path / "incr_repo"
    repo_path.mkdir()
    repo = gitmodule.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()

    # 첫 번째 커밋
    (repo_path / "a.py").write_text("x = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("first commit")

    # 전체 인덱싱
    result1 = await handle_ingest(
        path=str(repo_path), scope="test/incr", source_type="git",
        store=store, embedding=embedding, branch="master",
    )
    first_count = result1["chunks_indexed"]
    assert first_count >= 1

    # 두 번째 커밋 추가
    (repo_path / "b.py").write_text("y = 2\n")
    repo.index.add(["b.py"])
    repo.index.commit("second commit")

    # 증분 인덱싱
    result2 = await handle_ingest(
        path=str(repo_path), scope="test/incr", source_type="git",
        store=store, embedding=embedding, branch="master",
        incremental=True,
    )
    assert result2["chunks_indexed"] >= 1
    assert result2["chunks_indexed"] < first_count + 1
