"""End-to-end: git 인덱싱 → 검색 → 결과 확인."""

import pytest
from pathlib import Path

import git as gitmodule

from deview.embedding.base import EmbeddingProvider
from deview.scope import resolve_scope
from deview.storage.chroma import ChromaStore
from deview.tools.ingest import handle_ingest
from deview.tools.search import handle_search
from deview.tools.write import handle_write
from deview.tools.status import handle_status


class FakeEmbedding(EmbeddingProvider):
    """테스트용: 텍스트 길이 기반의 결정론적 임베딩."""
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            length = len(text) % 100 / 100.0
            vectors.append([length, length * 0.5, length * 0.3])
        return vectors

    def dimension(self) -> int:
        return 3


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "project"
    repo_path.mkdir()
    repo = gitmodule.Repo.init(repo_path)
    repo.create_remote("origin", "git@github.com:team/test-project.git")
    repo.config_writer().set_value("user", "name", "Kim").release()
    repo.config_writer().set_value("user", "email", "kim@test.com").release()

    (repo_path / "button.tsx").write_text(
        "// 공용 Button의 ripple이 미지원이라 커스텀\n"
        "export function CustomButton() {}\n"
    )
    repo.index.add(["button.tsx"])
    repo.index.commit("feat: 공용 Button 대신 커스텀 버튼 구현")

    return repo_path


@pytest.fixture
def store(tmp_path: Path) -> ChromaStore:
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


@pytest.fixture
def embedding() -> FakeEmbedding:
    return FakeEmbedding()


@pytest.mark.asyncio
async def test_full_flow(test_repo: Path, store: ChromaStore, embedding: FakeEmbedding):
    """전체 흐름: scope 추론 → 인덱싱 → 수동 기록 → 검색 → 상태 확인."""

    # 1. Scope 추론
    scope = resolve_scope(yaml_scope=None, project_path=test_repo)
    assert scope == "team/test-project"

    # 2. Git 인덱싱
    ingest_result = await handle_ingest(
        path=str(test_repo),
        scope=scope,
        source_type="git",
        store=store,
        embedding=embedding,
        branch="master",
    )
    assert ingest_result["chunks_indexed"] >= 1

    # 3. 수동 메모 저장
    write_result = await handle_write(
        content="공용 Button v2 출시 후 전환 예정",
        scope=scope,
        file_paths=["button.tsx"],
        store=store,
        embedding=embedding,
    )
    assert write_result["id"]

    # 4. 검색
    search_result = await handle_search(
        query="버튼을 왜 커스텀으로 만들었나",
        scope=scope,
        top_k=5,
        sort_by="relevance",
        store=store,
        embedding=embedding,
    )
    assert len(search_result["results"]) >= 1

    # 5. 상태 확인
    status_result = await handle_status(
        scope=scope,
        store=store,
        embedding_provider="fake",
    )
    assert status_result["total_chunks"] >= 2
    assert status_result["scope"] == "team/test-project"


@pytest.mark.asyncio
async def test_incremental_ingest_only_adds_new_commits(tmp_path: Path):
    """증분 인덱싱이 기존 커밋을 건너뛰고 새 커밋만 추가하는지 검증한다."""
    store = ChromaStore(persist_dir=str(tmp_path / "chroma"))
    embedding = FakeEmbedding()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = gitmodule.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()

    (repo_path / "a.py").write_text("x = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("commit 1")

    (repo_path / "b.py").write_text("y = 2\n")
    repo.index.add(["b.py"])
    repo.index.commit("commit 2")

    # 전체 인덱싱
    result1 = await handle_ingest(
        path=str(repo_path), scope="test/e2e", source_type="git",
        store=store, embedding=embedding, branch="master",
    )
    total_first = result1["chunks_indexed"]

    # 커밋 1개 추가
    (repo_path / "c.py").write_text("z = 3\n")
    repo.index.add(["c.py"])
    repo.index.commit("commit 3")

    # 증분 인덱싱
    result2 = await handle_ingest(
        path=str(repo_path), scope="test/e2e", source_type="git",
        store=store, embedding=embedding, branch="master",
        incremental=True,
    )
    incremental_count = result2["chunks_indexed"]

    assert incremental_count >= 1
    assert incremental_count < total_first

    # 전체 데이터 확인
    status = await handle_status(scope="test/e2e", store=store)
    assert status["total_chunks"] == total_first + incremental_count
