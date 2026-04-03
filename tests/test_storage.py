import pytest
from deview.storage.chroma import ChromaStore


@pytest.fixture
def store(tmp_path):
    """테스트용 임시 ChromaDB 스토어."""
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


def test_add_and_search(store: ChromaStore):
    """청크를 저장하고 검색할 수 있다."""
    store.add(
        ids=["chunk-1"],
        embeddings=[[0.1, 0.2, 0.3]],
        contents=["공용 Button 대신 커스텀 구현"],
        metadatas=[{
            "scope": "team/project",
            "source": "git",
            "author": "kim",
            "file_paths": "[\"src/Button.tsx\"]",
            "timestamp": "2025-11-03",
        }],
    )

    results = store.search(
        query_embedding=[0.1, 0.2, 0.3],
        scope="team/project",
        top_k=5,
    )
    assert len(results) == 1
    assert results[0]["content"] == "공용 Button 대신 커스텀 구현"
    assert results[0]["metadata"]["author"] == "kim"


def test_search_with_file_path_filter(store: ChromaStore):
    """file_path 필터로 관련 청크를 우선 검색한다."""
    store.add(
        ids=["chunk-1", "chunk-2"],
        embeddings=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]],
        contents=["Button.tsx 관련 변경", "Header.tsx 관련 변경"],
        metadatas=[
            {"scope": "proj", "source": "git", "file_paths": "[\"src/Button.tsx\"]", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "git", "file_paths": "[\"src/Header.tsx\"]", "timestamp": "2025-01-01"},
        ],
    )

    results = store.search(
        query_embedding=[0.1, 0.2, 0.3],
        scope="proj",
        top_k=5,
        file_path="src/Button.tsx",
    )
    assert len(results) >= 1
    assert results[0]["content"] == "Button.tsx 관련 변경"


def test_search_empty_scope(store: ChromaStore):
    """존재하지 않는 scope로 검색하면 빈 리스트를 반환한다."""
    results = store.search(
        query_embedding=[0.1, 0.2, 0.3],
        scope="nonexistent",
        top_k=5,
    )
    assert results == []


def test_count_by_scope(store: ChromaStore):
    """scope별 청크 수를 조회한다."""
    store.add(
        ids=["c1", "c2", "c3"],
        embeddings=[[0.1, 0.2, 0.3]] * 3,
        contents=["a", "b", "c"],
        metadatas=[
            {"scope": "proj", "source": "git", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "markdown", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "manual", "timestamp": "2025-01-01"},
        ],
    )

    counts = store.count_by_source(scope="proj")
    assert counts == {"git": 1, "markdown": 1, "manual": 1}


def test_get_latest_commit_hash(store: ChromaStore):
    """scope의 git 소스 중 가장 최근 commit_hash를 반환한다."""
    store.add(
        ids=["g1", "g2"],
        embeddings=[[0.1, 0.2, 0.3]] * 2,
        contents=["first commit", "second commit"],
        metadatas=[
            {"scope": "proj", "source": "git", "commit_hash": "aaa1111", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "git", "commit_hash": "bbb2222", "timestamp": "2025-06-15"},
        ],
    )
    assert store.get_latest_commit_hash("proj") == "bbb2222"


def test_get_latest_commit_hash_empty(store: ChromaStore):
    """데이터가 없으면 None을 반환한다."""
    assert store.get_latest_commit_hash("nonexistent") is None


def test_get_latest_timestamp(store: ChromaStore):
    """scope + source 조합의 최신 timestamp를 반환한다."""
    store.add(
        ids=["j1", "j2"],
        embeddings=[[0.1, 0.2, 0.3]] * 2,
        contents=["issue 1", "issue 2"],
        metadatas=[
            {"scope": "proj", "source": "jira", "timestamp": "2025-03-01"},
            {"scope": "proj", "source": "jira", "timestamp": "2025-09-20"},
        ],
    )
    assert store.get_latest_timestamp("proj", "jira") == "2025-09-20"


def test_get_latest_timestamp_empty(store: ChromaStore):
    """데이터가 없으면 None을 반환한다."""
    assert store.get_latest_timestamp("proj", "jira") is None
