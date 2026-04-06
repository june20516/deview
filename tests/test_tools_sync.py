import pytest
from unittest.mock import MagicMock, patch
from deview.tools.sync import handle_sync
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
async def test_sync_jira(store: ChromaStore, embedding: FakeEmbedding):
    """Jira 동기화로 이슈를 인덱싱한다."""
    mock_jira = MagicMock()
    mock_jira.jql.return_value = {
        "issues": [
            {
                "key": "PROJ-1",
                "fields": {
                    "summary": "테스트 이슈",
                    "description": "설명입니다",
                    "assignee": {"displayName": "김철수"},
                    "updated": "2025-03-17T10:00:00.000+0900",
                    "comment": {"comments": []},
                },
            },
        ],
    }

    with patch("deview.tools.sync._create_jira_client", return_value=mock_jira):
        result = await handle_sync(
            source="jira",
            scope="team/proj",
            store=store,
            embedding=embedding,
            atlassian_url="https://team.atlassian.net",
            atlassian_email="user@team.com",
            atlassian_token="token",
            jira_project="PROJ",
        )

    assert result["source"] == "jira"
    assert result["chunks_indexed"] == 1


@pytest.mark.asyncio
async def test_sync_confluence(store: ChromaStore, embedding: FakeEmbedding):
    """Confluence 동기화로 페이지를 인덱싱한다."""
    mock_confluence = MagicMock()
    mock_confluence.get_all_pages_from_space.return_value = [
        {
            "id": "12345",
            "title": "가이드",
            "body": {"storage": {"value": "<p>내용입니다</p>"}},
            "version": {"by": {"displayName": "박지민"}, "when": "2025-10-15T10:00:00.000Z"},
        },
    ]

    with patch("deview.tools.sync._create_confluence_client", return_value=mock_confluence):
        result = await handle_sync(
            source="confluence",
            scope="team/proj",
            store=store,
            embedding=embedding,
            atlassian_url="https://team.atlassian.net",
            atlassian_email="user@team.com",
            atlassian_token="token",
            confluence_space="DEV",
        )

    assert result["source"] == "confluence"
    assert result["chunks_indexed"] == 1


@pytest.mark.asyncio
async def test_sync_jira_incremental(store: ChromaStore, embedding: FakeEmbedding):
    """증분 동기화: 기존 데이터의 최신 timestamp 이후만 가져온다."""
    store.add(
        ids=["jira-existing"],
        embeddings=[[0.1, 0.2, 0.3]],
        contents=["기존 이슈"],
        metadatas=[{"scope": "team/proj", "source": "jira", "timestamp": "2025-03-01"}],
    )

    mock_jira = MagicMock()
    mock_jira.jql.return_value = {"issues": []}

    with patch("deview.tools.sync._create_jira_client", return_value=mock_jira):
        result = await handle_sync(
            source="jira",
            scope="team/proj",
            store=store,
            embedding=embedding,
            atlassian_url="https://team.atlassian.net",
            atlassian_email="user@team.com",
            atlassian_token="token",
            jira_project="PROJ",
        )

    jql_call = mock_jira.jql.call_args[0][0]
    assert "2025-03-01" in jql_call


@pytest.mark.asyncio
async def test_sync_confluence_by_page_ids(store: ChromaStore, embedding: FakeEmbedding):
    """특정 페이지 ID로 Confluence 동기화한다."""
    mock_confluence = MagicMock()
    mock_confluence.get_page_by_id.side_effect = lambda pid, **kw: {
        "id": pid,
        "title": f"페이지 {pid}",
        "body": {"storage": {"value": f"<p>{pid} 내용</p>"}},
        "version": {"by": {"displayName": "작성자"}, "when": "2025-11-01T10:00:00.000Z"},
    }

    with patch("deview.tools.sync._create_confluence_client", return_value=mock_confluence):
        result = await handle_sync(
            source="confluence",
            scope="team/proj",
            store=store,
            embedding=embedding,
            atlassian_url="https://team.atlassian.net",
            atlassian_email="user@team.com",
            atlassian_token="token",
            confluence_page_ids=["111", "222"],
        )

    assert result["source"] == "confluence"
    assert result["chunks_indexed"] == 2
    # get_all_pages_from_space는 호출되지 않아야 함
    mock_confluence.get_all_pages_from_space.assert_not_called()


@pytest.mark.asyncio
async def test_sync_confluence_incremental_uses_cql(store: ChromaStore, embedding: FakeEmbedding):
    """스페이스 증분 동기화 시 CQL을 사용한다."""
    store.add(
        ids=["conf-existing"],
        embeddings=[[0.1, 0.2, 0.3]],
        contents=["기존 문서"],
        metadatas=[{"scope": "team/proj", "source": "confluence", "timestamp": "2025-06-01"}],
    )

    mock_confluence = MagicMock()
    mock_confluence.cql.return_value = {"results": []}

    with patch("deview.tools.sync._create_confluence_client", return_value=mock_confluence):
        result = await handle_sync(
            source="confluence",
            scope="team/proj",
            store=store,
            embedding=embedding,
            atlassian_url="https://team.atlassian.net",
            atlassian_email="user@team.com",
            atlassian_token="token",
            confluence_space="DEV",
        )

    # CQL이 호출되고 날짜 필터가 포함되어야 함
    mock_confluence.cql.assert_called_once()
    cql_call = mock_confluence.cql.call_args[0][0]
    assert "2025-06-01" in cql_call
    # get_all_pages_from_space는 호출되지 않아야 함
    mock_confluence.get_all_pages_from_space.assert_not_called()
