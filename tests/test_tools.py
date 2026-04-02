import pytest
from pathlib import Path
from unittest.mock import MagicMock

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
