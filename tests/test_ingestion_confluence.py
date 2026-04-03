from deview.ingestion.confluence import parse_confluence_pages


def _make_page(page_id: str, title: str, body: str, author: str, modified: str) -> dict:
    """Confluence API 응답 형태의 페이지 dict를 만든다."""
    return {
        "id": page_id,
        "title": title,
        "body": {"storage": {"value": body}},
        "version": {"by": {"displayName": author}, "when": modified},
    }


def test_parse_short_page():
    """짧은 문서는 하나의 청크로 만든다."""
    pages = [
        _make_page(
            page_id="12345",
            title="코딩 컨벤션",
            body="<p>변수명은 camelCase를 사용합니다.</p>",
            author="박지민",
            modified="2025-10-15T10:00:00.000Z",
        ),
    ]

    chunks = parse_confluence_pages(pages, scope="team/proj")
    assert len(chunks) == 1
    assert "코딩 컨벤션" in chunks[0].content
    assert "camelCase" in chunks[0].content
    assert chunks[0].metadata["source"] == "confluence"
    assert chunks[0].metadata["document_id"] == "confluence-12345"
    assert chunks[0].metadata["document_title"] == "코딩 컨벤션"
    assert chunks[0].metadata["author"] == "박지민"


def test_parse_long_page_split_by_headings():
    """긴 문서는 헤딩 기준으로 분할하고 document_id로 그루핑한다."""
    long_body = (
        "<h2>1. 개요</h2><p>이 문서는 API 설계 가이드입니다.</p>"
        "<h2>2. 인증</h2><p>" + "인증 관련 상세 내용입니다. " * 200 + "</p>"
        "<h2>3. 에러 핸들링</h2><p>" + "에러 핸들링 상세 내용입니다. " * 200 + "</p>"
    )
    pages = [
        _make_page(
            page_id="67890",
            title="API 설계 가이드",
            body=long_body,
            author="김철수",
            modified="2025-11-01T10:00:00.000Z",
        ),
    ]

    chunks = parse_confluence_pages(pages, scope="team/proj")
    assert len(chunks) >= 2
    doc_ids = {c.metadata["document_id"] for c in chunks}
    assert len(doc_ids) == 1
    assert "confluence-67890" in doc_ids
    sections = [c.metadata.get("section", "") for c in chunks]
    assert any("개요" in s for s in sections)


def test_parse_page_html_stripped():
    """HTML 태그가 제거된 텍스트가 content에 들어간다."""
    pages = [
        _make_page(
            page_id="11111",
            title="테스트",
            body="<p>일반 텍스트</p><ul><li>항목 1</li><li>항목 2</li></ul>",
            author="테스터",
            modified="2025-12-01T10:00:00.000Z",
        ),
    ]

    chunks = parse_confluence_pages(pages, scope="team/proj")
    assert "<p>" not in chunks[0].content
    assert "일반 텍스트" in chunks[0].content
