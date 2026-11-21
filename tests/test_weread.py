import logging

import pytest

from weread2notion.weread import WeReadClient, WeReadError


class Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class Session:
    def __init__(self, pages):
        self.headers = {}
        self.pages = iter(pages)
        self.payloads = []

    def post(self, url, json, timeout):
        self.payloads.append(json)
        return Response(next(self.pages))


@pytest.mark.parametrize(
    "options, expected_version", [({}, "1.0.6"), ({"skill_version": "1.0.5"}, "1.0.5")]
)
def test_shelf_request_reports_skill_version(options, expected_version):
    session = Session([{"errcode": 0, "books": [], "albums": []}])
    client = WeReadClient("test-key", session=session, **options)

    client.shelf()

    assert session.payloads[0]["api_name"] == "/shelf/sync"
    assert session.payloads[0]["skill_version"] == expected_version


def test_shelf_uses_data_from_response_with_upgrade_notice(caplog):
    data = {
        "errcode": 0,
        "books": [{"bookId": "book-1"}],
        "albums": [{"albumInfo": {"albumId": "album-1"}}],
        "upgrade_info": {"message": "Update available"},
    }
    session = Session([data])
    client = WeReadClient("test-key", session=session)

    assert client.shelf() is data
    assert len(session.payloads) == 1
    assert any(
        record.levelno == logging.WARNING and "Update available" in record.getMessage()
        for record in caplog.records
    )


def test_future_upgrade_notice_keeps_using_the_configured_version():
    data = {
        "books": [{"bookId": "book-1"}],
        "albums": [],
        "upgrade_info": {"message": "Skill 9.8.0 is available"},
    }
    session = Session([data])
    client = WeReadClient("test-key", skill_version="9.7.0", session=session)

    assert client.shelf() is data
    assert session.payloads == [{"api_name": "/shelf/sync", "skill_version": "9.7.0"}]


def test_gateway_reports_business_error_before_upgrade_notice(caplog):
    session = Session(
        [
            {
                "errcode": 123,
                "errmsg": "Example business error",
                "upgrade_info": {"message": "Update available"},
            }
        ]
    )
    client = WeReadClient("test-key", session=session)

    with pytest.raises(WeReadError, match="errcode=123: Example business error"):
        client.shelf()

    assert len(session.payloads) == 1
    assert not caplog.records


@pytest.mark.parametrize(
    "data, field",
    [
        ({"albums": []}, "books"),
        ({"books": []}, "albums"),
        ({"books": {}, "albums": []}, "books"),
        ({"books": [], "albums": None}, "albums"),
        ({"books": [{"title": "No ID"}], "albums": []}, "bookId"),
        ({"books": [], "albums": [{"albumInfo": {}}]}, "albumId"),
        ({"books": [], "albums": [], "mp": []}, "mp"),
    ],
)
def test_shelf_rejects_invalid_response(data, field):
    client = WeReadClient("test-key", session=Session([data]))

    with pytest.raises(WeReadError, match=rf"/shelf/sync.*{field}"):
        client.shelf()


def test_shelf_accepts_explicitly_empty_lists():
    data = {"books": [], "albums": [], "mp": None}
    client = WeReadClient("test-key", session=Session([data]))

    assert client.shelf() is data


def test_notebook_pagination_is_flat_and_uses_last_sort():
    session = Session(
        [
            {"books": [{"sort": 20}], "hasMore": 1, "totalNoteCount": 3},
            {"books": [{"sort": 10}], "hasMore": 0, "totalNoteCount": 3},
        ]
    )
    client = WeReadClient("key", session=session)
    rows, totals = client.notebooks()
    assert len(rows) == 2
    assert totals["notes"] == 3
    assert session.payloads[1]["lastSort"] == 20
    assert "params" not in session.payloads[1]


def test_reading_days_falls_back_to_monthly_day_buckets():
    session = Session(
        [
            {"totalReadTime": 120},
            {"readTimes": {"1767196800": 120}, "totalReadTime": 120},
            {"readTimes": {"1767283200": 120}},
        ]
    )
    client = WeReadClient("key", session=session)
    days, _ = client.reading_days(2026)
    assert days == [{"timestamp": 1767283200, "duration": 120}]
    assert session.payloads[2]["mode"] == "monthly"


def test_book_bundle_reports_the_failing_stage():
    client = WeReadClient("key")
    responses = {
        "/book/info": {"bookId": "book-1", "title": "导入书"},
        "/book/getprogress": {"book": {"progress": 40}},
    }

    def call(api_name, **params):
        if api_name == "/book/chapterinfo":
            raise WeReadError("/book/chapterinfo 请求失败：499")
        return responses[api_name]

    client.call = call
    try:
        client.book_bundle("book-1")
    except WeReadError as exc:
        assert "阶段=章节目录" in str(exc)
        assert "接口=/book/chapterinfo" in str(exc)
    else:
        raise AssertionError("expected chapter stage failure")


def test_book_bundle_reports_progress_failure_before_chapter_lookup():
    client = WeReadClient("key")

    def call(api_name, **params):
        if api_name == "/book/getprogress":
            raise WeReadError("请求失败：499")
        return {"bookId": "book-2"}

    client.call = call
    try:
        client.book_bundle("book-2")
    except WeReadError as exc:
        assert "阶段=阅读进度" in str(exc)
        assert "接口=/book/getprogress" in str(exc)
    else:
        raise AssertionError("expected progress stage failure")


def test_notebook_pagination_stops_when_the_cursor_does_not_advance():
    page = {"books": [{"sort": 20}], "hasMore": 1}
    session = Session([page, page, page, page])
    client = WeReadClient("key", session=session)

    rows, _ = client.notebooks()

    # Without the guard this asks for lastSort=20 until the gateway gives up.
    assert len(session.payloads) == 2
    assert len(rows) == 2


def test_transport_errors_are_retried_then_reported(monkeypatch):
    monkeypatch.setattr("weread2notion.weread.time.sleep", lambda _: None)

    class Flaky(Session):
        def post(self, url, json, timeout):
            self.payloads.append(json)
            if len(self.payloads) < 3:
                raise ConnectionError("connection reset")
            return Response({"books": [], "albums": []})

    session = Flaky([])
    assert WeReadClient("key", session=session).shelf() == {"books": [], "albums": []}
    assert len(session.payloads) == 3

    class Down(Session):
        def post(self, url, json, timeout):
            self.payloads.append(json)
            raise ConnectionError("connection reset")

    session = Down([])
    with pytest.raises(WeReadError, match="/shelf/sync 请求失败"):
        WeReadClient("key", session=session).shelf()
    assert len(session.payloads) == 3
