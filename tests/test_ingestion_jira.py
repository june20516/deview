from deview.ingestion.jira import parse_jira_issues


def _make_issue(key: str, summary: str, description: str, assignee: str, updated: str, comments: list[dict]) -> dict:
    """Jira API 응답 형태의 이슈 dict를 만든다."""
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": description,
            "assignee": {"displayName": assignee} if assignee else None,
            "updated": updated,
            "comment": {
                "comments": [
                    {
                        "author": {"displayName": c["author"]},
                        "created": c["created"],
                        "body": c["body"],
                    }
                    for c in comments
                ],
            },
        },
    }


def test_parse_jira_issues_basic():
    """Jira 이슈를 청크로 변환한다."""
    issues = [
        _make_issue(
            key="PROJ-123",
            summary="API 응답 포맷 통일",
            description="각 API 엔드포인트마다 응답 포맷이 달라서 통일합니다.",
            assignee="이영희",
            updated="2025-03-17T10:00:00.000+0900",
            comments=[
                {"author": "김철수", "created": "2025-03-15T09:00:00.000+0900", "body": "v2로 분리하는게 낫지 않을까요?"},
                {"author": "이영희", "created": "2025-03-16T14:00:00.000+0900", "body": "기존 API에 래퍼를 씌우는 방향으로 결정했습니다."},
            ],
        ),
    ]

    chunks = parse_jira_issues(issues, scope="team/proj")
    assert len(chunks) == 1
    chunk = chunks[0]
    assert "PROJ-123" in chunk.content
    assert "API 응답 포맷 통일" in chunk.content
    assert "v2로 분리하는게 낫지 않을까요?" in chunk.content
    assert "래퍼를 씌우는 방향으로 결정" in chunk.content
    assert chunk.metadata["source"] == "jira"
    assert chunk.metadata["scope"] == "team/proj"
    assert chunk.metadata["jira_key"] == "PROJ-123"
    assert chunk.metadata["author"] == "이영희"


def test_parse_jira_issues_no_comments():
    """댓글이 없는 이슈도 정상 변환된다."""
    issues = [
        _make_issue(
            key="PROJ-456",
            summary="버그 수정",
            description="로그인 실패 시 에러 메시지 미표시",
            assignee="박지민",
            updated="2025-04-01T10:00:00.000+0900",
            comments=[],
        ),
    ]

    chunks = parse_jira_issues(issues, scope="team/proj")
    assert len(chunks) == 1
    assert "PROJ-456" in chunks[0].content
    assert "댓글" not in chunks[0].content


def test_parse_jira_issues_no_assignee():
    """담당자가 없는 이슈는 author가 unknown이다."""
    issues = [
        _make_issue(
            key="PROJ-789",
            summary="담당자 미지정 이슈",
            description="설명",
            assignee="",
            updated="2025-04-01T10:00:00.000+0900",
            comments=[],
        ),
    ]

    chunks = parse_jira_issues(issues, scope="team/proj")
    assert chunks[0].metadata["author"] == "unknown"
