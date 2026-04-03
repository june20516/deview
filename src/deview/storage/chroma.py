"""ChromaDB 벡터 데이터베이스 래퍼."""
from __future__ import annotations

import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "deview_contexts"


class ChromaStore:
    def __init__(self, persist_dir: str | None = None) -> None:
        if persist_dir is None:
            persist_dir = str(Path.home() / ".deview" / "data" / "chroma")
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    _BATCH_SIZE = 5000

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        contents: list[str],
        metadatas: list[dict],
    ) -> None:
        """청크를 저장한다. ChromaDB 배치 제한을 초과하면 자동 분할."""
        for i in range(0, len(ids), self._BATCH_SIZE):
            end = i + self._BATCH_SIZE
            self._collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=contents[i:end],
                metadatas=metadatas[i:end],
            )
        logger.debug("%d개 청크 저장 완료", len(ids))

    def search(
        self,
        query_embedding: list[float],
        scope: str | None = None,
        top_k: int = 5,
        file_path: str | None = None,
    ) -> list[dict]:
        """scope 내에서 유사도 검색을 수행한다. scope가 None이면 전체 통합 검색."""
        where_filter: dict | None = {"scope": scope} if scope else None

        try:
            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
            }
            if where_filter:
                query_kwargs["where"] = where_filter
            results = self._collection.query(**query_kwargs)
        except Exception:
            logger.exception("ChromaDB 검색 중 오류 발생")
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            item = {
                "id": doc_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
            }
            items.append(item)

        if file_path:
            items.sort(
                key=lambda x: (
                    file_path not in x["metadata"].get("file_paths", ""),
                    -x["score"],
                )
            )

        return items

    def count_by_source(self, scope: str) -> dict[str, int]:
        """scope 내 소스별 청크 수를 반환한다."""
        counts: dict[str, int] = {}
        for source in ("git", "markdown", "manual", "comment"):
            try:
                result = self._collection.get(
                    where={"$and": [{"scope": scope}, {"source": source}]}
                )
                count = len(result["ids"]) if result["ids"] else 0
            except Exception:
                logger.exception("소스별 카운트 조회 중 오류: source=%s", source)
                count = 0
            if count > 0:
                counts[source] = count
        return counts

    def get_latest_commit_hash(self, scope: str) -> str | None:
        """scope의 git 소스 중 가장 최근 commit_hash를 반환한다."""
        try:
            result = self._collection.get(
                where={"$and": [{"scope": scope}, {"source": "git"}]}
            )
            if not result["metadatas"]:
                return None
            entries = [
                (m.get("timestamp", ""), m.get("commit_hash", ""))
                for m in result["metadatas"]
                if m.get("commit_hash")
            ]
            if not entries:
                return None
            entries.sort(key=lambda x: x[0], reverse=True)
            return entries[0][1]
        except Exception:
            logger.exception("최신 commit_hash 조회 중 오류")
            return None

    def get_latest_timestamp(self, scope: str, source: str) -> str | None:
        """scope + source 조합의 최신 timestamp를 반환한다."""
        try:
            result = self._collection.get(
                where={"$and": [{"scope": scope}, {"source": source}]}
            )
            if not result["metadatas"]:
                return None
            timestamps = [
                m.get("timestamp", "")
                for m in result["metadatas"]
                if m.get("timestamp")
            ]
            return max(timestamps) if timestamps else None
        except Exception:
            logger.exception("최신 timestamp 조회 중 오류: source=%s", source)
            return None

    def get_last_indexed(self, scope: str) -> str | None:
        """scope의 마지막 인덱싱 시각을 반환한다."""
        try:
            result = self._collection.get(where={"scope": scope})
            if not result["metadatas"]:
                return None
            timestamps = [
                m.get("timestamp", "")
                for m in result["metadatas"]
                if m.get("timestamp")
            ]
            return max(timestamps) if timestamps else None
        except Exception:
            logger.exception("마지막 인덱싱 시각 조회 중 오류")
            return None
