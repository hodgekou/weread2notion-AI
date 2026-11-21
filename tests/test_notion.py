import httpx
import pytest
from notion_client.errors import RequestTimeoutError

from weread2notion.blocks import get_callout, split_text
from weread2notion.notion import NotionWorkspace, text_value


class TransientError(RuntimeError):
    status = 520


class Client:
    def __init__(self):
        self.calls = 0

    def request(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise TransientError("temporary Notion failure")
        return {"ok": True}


def test_request_retries_transient_notion_errors(monkeypatch):
    monkeypatch.setattr("weread2notion.notion.time.sleep", lambda _: None)
    client = Client()
    notion = NotionWorkspace("token", "page", "version", client=client)
    assert notion.request("pages/page", "PATCH", {}) == {"ok": True}
    assert client.calls == 2


def test_upsert_refreshes_existing_page_icon(monkeypatch):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    notion.schemas["year"] = {}
    monkeypatch.setattr(
        notion, "properties", lambda database, raw: {"Name": raw["Name"]}
    )
    monkeypatch.setattr(
        notion, "find", lambda database, key, value: {"id": "year-page"}
    )
    calls = []
    monkeypatch.setattr(
        notion, "request", lambda path, method, body: calls.append((path, method, body))
    )

    page_id = notion.upsert(
        "year",
        "Name",
        "2026",
        {"Name": "2026"},
        "https://www.notion.so/icons/target_red.svg",
    )

    assert page_id == "year-page"
    assert calls[0][2]["icon"] == {
        "type": "external",
        "external": {"url": "https://www.notion.so/icons/target_red.svg"},
    }


def test_upsert_reuses_known_page_without_query(monkeypatch):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    notion.schemas["book"] = {}
    monkeypatch.setattr(notion, "properties", lambda database, raw: {"Name": "Book"})
    monkeypatch.setattr(
        notion,
        "find",
        lambda *args: (_ for _ in ()).throw(AssertionError("find should not run")),
    )
    calls = []
    monkeypatch.setattr(
        notion,
        "request",
        lambda path, method, body: calls.append((path, method, body)),
    )
    page_id = notion.upsert(
        "book", "BookId", "book-1", {"Name": "Book"}, existing_id="page-1"
    )
    assert page_id == "page-1"
    assert calls[0][0] == "pages/page-1"


def test_row_index_normalizes_integer_float_keys(monkeypatch):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    monkeypatch.setattr(
        notion,
        "query_all",
        lambda database: [
            {
                "id": "record-page",
                "properties": {"时间戳": {"type": "number", "number": 1.0}},
            }
        ],
    )
    assert notion.row_index("阅读记录", "时间戳")["1"]["page_id"] == "record-page"


def test_existing_sync_settings_are_read_from_notion(monkeypatch):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    notion.sources["设置"] = "settings-source"
    notion.schemas["设置"] = {
        "配置": "title",
        "阅读完成进度强制改为100%": "checkbox",
        "只同步我的书架书籍": "checkbox",
        "同步划线和笔记": "checkbox",
        "保存阅读快照": "checkbox",
        "阅读统计起始年份": "number",
        "同步配置版本（不可删除）": "number",
    }
    monkeypatch.setattr(
        notion,
        "query_all",
        lambda database: [
            {
                "properties": {
                    "阅读完成进度强制改为100%": {
                        "type": "checkbox",
                        "checkbox": True,
                    },
                    "只同步我的书架书籍": {
                        "type": "checkbox",
                        "checkbox": False,
                    },
                    "同步划线和笔记": {
                        "type": "checkbox",
                        "checkbox": True,
                    },
                    "阅读统计起始年份": {"type": "number", "number": 2025},
                    "同步配置版本（不可删除）": {
                        "type": "number",
                        "number": 0,
                    },
                }
            }
        ],
    )
    settings = notion.ensure_sync_settings()
    assert {key: settings[key] for key in (
        "completed_progress_100",
        "delete_removed",
        "sync_notes",
        "start_year",
    )} == {
        "completed_progress_100": True,
        "delete_removed": False,
        "sync_notes": True,
        "start_year": 2025,
    }
    assert settings["settings_changed"] is True


def test_legacy_sync_setting_names_remain_compatible(monkeypatch):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    notion.sources["设置"] = "settings-source"
    notion.schemas["设置"] = {
        "配置": "title",
        "已读进度显示为100%": "checkbox",
        "移出书架时删除": "checkbox",
        "同步划线和笔记": "checkbox",
        "阅读统计起始年份": "number",
        "已应用配置码": "number",
    }
    monkeypatch.setattr(
        notion,
        "query_all",
        lambda database: [
            {
                "id": "settings-page",
                "properties": {
                    "已读进度显示为100%": {
                        "type": "checkbox",
                        "checkbox": True,
                    },
                    "移出书架时删除": {
                        "type": "checkbox",
                        "checkbox": False,
                    },
                    "同步划线和笔记": {
                        "type": "checkbox",
                        "checkbox": True,
                    },
                    "阅读统计起始年份": {"type": "number", "number": 2024},
                    "已应用配置码": {"type": "number", "number": 0},
                },
            }
        ],
    )
    monkeypatch.setattr(notion, "request", lambda *args, **kwargs: {})
    settings = notion.ensure_sync_settings()
    assert settings["completed_progress_100"] is True
    assert settings["delete_removed"] is False
    assert settings["_config_property"] == "已应用配置码"


def test_missing_sync_settings_database_is_created(monkeypatch):
    notion = NotionWorkspace("token", "root-page", "version", client=Client())
    calls = []
    rows = []

    def request(path, method="GET", body=None):
        calls.append((path, method, body))
        if path == "databases":
            return {"id": "settings-db", "data_sources": [{"id": "settings-source"}]}
        return {}

    def query_all(database):
        if not rows:
            return []
        return rows

    def create(database, raw, icon=None, cover=None):
        rows.append(
            {
                "properties": {
                    "阅读完成进度强制改为100%": {
                        "type": "checkbox",
                        "checkbox": raw["阅读完成进度强制改为100%"],
                    },
                    "只同步我的书架书籍": {
                        "type": "checkbox",
                        "checkbox": raw["只同步我的书架书籍"],
                    },
                    "同步划线和笔记": {
                        "type": "checkbox",
                        "checkbox": raw["同步划线和笔记"],
                    },
                    "阅读统计起始年份": {
                        "type": "number",
                        "number": raw["阅读统计起始年份"],
                    },
                    "同步配置版本（不可删除）": {
                        "type": "number",
                        "number": raw["同步配置版本（不可删除）"],
                    },
                }
            }
        )
        return "settings-page"

    monkeypatch.setattr(notion, "request", request)
    monkeypatch.setattr(notion, "query_all", query_all)
    monkeypatch.setattr(notion, "create", create)

    settings = notion.ensure_sync_settings(2024)
    assert settings["start_year"] == 2024
    assert notion.sources["设置"] == "settings-source"
    assert calls[0][0:2] == ("databases", "POST")
    assert any(call[0] == "blocks/settings-page/children" for call in calls)


def test_missing_reading_snapshots_database_is_created(monkeypatch):
    notion = NotionWorkspace("token", "root-page", "version", client=Client())
    calls = []

    def request(path, method="GET", body=None):
        calls.append((path, method, body))
        return {
            "id": "snapshots-db",
            "data_sources": [{"id": "snapshots-source"}],
        }

    monkeypatch.setattr(notion, "request", request)
    notion.ensure_reading_snapshots()

    assert calls[0][0:2] == ("databases", "POST")
    properties = calls[0][2]["initial_data_source"]["properties"]
    assert properties["快照"] == {"title": {}}
    assert properties["SnapshotKey"] == {"rich_text": {}}
    assert properties["阅读进度"] == {"number": {"format": "percent"}}
    assert notion.sources["阅读快照"] == "snapshots-source"
    assert notion.titles["阅读快照"] == "快照"


def test_existing_reading_snapshots_database_gets_missing_properties(monkeypatch):
    notion = NotionWorkspace("token", "root-page", "version", client=Client())
    notion.sources["阅读快照"] = "snapshots-source"
    notion.schemas["阅读快照"] = {"快照": "title", "SnapshotKey": "rich_text"}
    notion.titles["阅读快照"] = "快照"
    calls = []
    monkeypatch.setattr(
        notion,
        "request",
        lambda path, method="GET", body=None: calls.append((path, method, body))
        or {},
    )

    notion.ensure_reading_snapshots()

    assert calls[0][0:2] == ("data_sources/snapshots-source", "PATCH")
    assert "日期" in calls[0][2]["properties"]
    assert "SnapshotKey" not in calls[0][2]["properties"]


class ScriptedClient:
    """Raise the scripted errors in order, then answer every request."""

    def __init__(self, errors=(), response=None):
        self.errors = list(errors)
        self.response = response or {"ok": True}
        self.requests = []

    def request(self, **kwargs):
        self.requests.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        return self.response


class StatusError(RuntimeError):
    def __init__(self, status):
        super().__init__(f"status {status}")
        self.status = status


def workspace(monkeypatch, client):
    monkeypatch.setattr("weread2notion.notion.time.sleep", lambda _: None)
    return NotionWorkspace("token", "page", "version", client=client)


def read_timeout():
    # notion-client converts httpx timeouts this way; the original error is
    # only reachable through the exception context.
    try:
        try:
            raise httpx.ReadTimeout("read timed out")
        except httpx.TimeoutException:
            raise RequestTimeoutError()
    except RequestTimeoutError as exc:
        return exc


def connect_timeout():
    try:
        try:
            raise httpx.ConnectTimeout("connect timed out")
        except httpx.TimeoutException:
            raise RequestTimeoutError()
    except RequestTimeoutError as exc:
        return exc


@pytest.mark.parametrize("status", [409, 429, 500, 502, 503, 504])
def test_request_retries_transient_statuses(monkeypatch, status):
    client = ScriptedClient([StatusError(status)])
    notion = workspace(monkeypatch, client)
    assert notion.request("pages", "POST", {}) == {"ok": True}
    assert len(client.requests) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_request_does_not_retry_permanent_statuses(monkeypatch, status):
    client = ScriptedClient([StatusError(status)])
    notion = workspace(monkeypatch, client)
    with pytest.raises(StatusError):
        notion.request("pages/page-1", "PATCH", {})
    assert len(client.requests) == 1


def test_request_gives_up_after_five_attempts(monkeypatch):
    client = ScriptedClient([StatusError(503)] * 9)
    notion = workspace(monkeypatch, client)
    with pytest.raises(StatusError):
        notion.request("pages/page-1", "PATCH", {})
    assert len(client.requests) == 5


@pytest.mark.parametrize(
    "path, method",
    [
        ("blocks/block-1/children", "GET"),
        ("blocks/block-1", "DELETE"),
        ("data_sources/source-1/query", "POST"),
        ("pages/page-1", "PATCH"),
    ],
)
def test_dropped_connection_is_retried_for_repeatable_requests(
    monkeypatch, path, method
):
    for error in (read_timeout(), httpx.ReadError("connection reset")):
        client = ScriptedClient([error])
        notion = workspace(monkeypatch, client)
        assert notion.request(path, method, {}) == {"ok": True}
        assert len(client.requests) == 2


@pytest.mark.parametrize(
    "path, method",
    [("pages", "POST"), ("databases", "POST"), ("blocks/block-1/children", "PATCH")],
)
def test_dropped_connection_never_repeats_a_create_or_append(
    monkeypatch, path, method
):
    # Notion may already have created the page or appended the blocks.
    for error in (read_timeout(), httpx.ReadError("connection reset")):
        client = ScriptedClient([error])
        notion = workspace(monkeypatch, client)
        with pytest.raises(type(error)):
            notion.request(path, method, {})
        assert len(client.requests) == 1


@pytest.mark.parametrize(
    "path, method", [("pages", "POST"), ("blocks/block-1/children", "PATCH")]
)
def test_failed_connection_is_always_retried(monkeypatch, path, method):
    # Nothing was sent, so even a create is safe to repeat.
    for error in (connect_timeout(), httpx.ConnectError("no route to host")):
        client = ScriptedClient([error])
        notion = workspace(monkeypatch, client)
        assert notion.request(path, method, {}) == {"ok": True}
        assert len(client.requests) == 2


def test_unknown_errors_are_not_retried(monkeypatch):
    client = ScriptedClient([ValueError("bug")])
    notion = workspace(monkeypatch, client)
    with pytest.raises(ValueError):
        notion.request("pages/page-1", "GET")
    assert len(client.requests) == 1


def test_list_children_paginates_and_survives_a_transient_error(monkeypatch):
    class Pages(ScriptedClient):
        def request(self, **kwargs):
            super().request(**kwargs)
            if (kwargs.get("query") or {}).get("start_cursor") == "next":
                return {"results": [{"id": "b"}], "has_more": False}
            return {"results": [{"id": "a"}], "has_more": True, "next_cursor": "next"}

    client = Pages([StatusError(502)])
    notion = workspace(monkeypatch, client)

    assert notion.list_children("block-1") == [{"id": "a"}, {"id": "b"}]
    assert [item["path"] for item in client.requests] == ["blocks/block-1/children"] * 3
    assert client.requests[1]["query"] == {"page_size": 100}
    assert client.requests[2]["query"] == {"page_size": 100, "start_cursor": "next"}


@pytest.mark.parametrize("method", ["list_children", "query_all"])
def test_pagination_stops_when_notion_returns_no_cursor(monkeypatch, method):
    client = ScriptedClient(response={"results": [{"id": "a"}], "has_more": True})
    notion = workspace(monkeypatch, client)
    notion.sources["书架"] = "source-1"
    target = "block-1" if method == "list_children" else "书架"
    assert getattr(notion, method)(target) == [{"id": "a"}]
    assert len(client.requests) == 1


MARKER = "由 WeRead2Notion 自动同步"


class BookPage:
    """A book page that already holds one generated block and one user block."""

    def __init__(self, fail_on=None):
        self.fail_on = fail_on
        self.log = []

    def request(self, path, method="GET", body=None, query=None):
        self.log.append((method, path))
        if self.fail_on == (method, path):
            raise StatusError(400)
        if (method, path) == ("GET", "blocks/page-1/children"):
            return {
                "results": [
                    {"id": "user-block", "type": "paragraph", "has_children": False},
                    {"id": "old-block", "type": "synced_block", "has_children": True},
                    {"id": "user-synced", "type": "synced_block", "has_children": True},
                ]
            }
        if (method, path) == ("GET", "blocks/old-block/children"):
            return {
                "results": [
                    {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": MARKER}]}}
                ]
            }
        if (method, path) == ("GET", "blocks/user-synced/children"):
            return {
                "results": [
                    {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "我的笔记"}]}}
                ]
            }
        if (method, path) == ("PATCH", "blocks/page-1/children"):
            return {"results": [{"id": "new-block"}]}
        return {}


def book_page_workspace(monkeypatch, page):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    monkeypatch.setattr(notion, "request", page.request)
    return notion


def test_generated_content_is_written_before_the_old_block_is_deleted(monkeypatch):
    page = BookPage()
    notion = book_page_workspace(monkeypatch, page)

    notion.replace_generated_book_content("page-1", [{"type": "callout"}])

    writes = [item for item in page.log if item[0] != "GET"]
    assert writes == [
        ("PATCH", "blocks/page-1/children"),
        ("PATCH", "blocks/new-block/children"),
        ("DELETE", "blocks/old-block"),
    ]


def test_old_notes_survive_when_writing_the_new_ones_fails(monkeypatch):
    page = BookPage(fail_on=("PATCH", "blocks/new-block/children"))
    notion = book_page_workspace(monkeypatch, page)

    with pytest.raises(StatusError):
        notion.replace_generated_book_content("page-1", [{"type": "callout"}])

    assert ("DELETE", "blocks/old-block") not in page.log


def test_user_blocks_are_never_deleted(monkeypatch):
    page = BookPage()
    notion = book_page_workspace(monkeypatch, page)

    notion.replace_generated_book_content("page-1", [])

    assert [item for item in page.log if item[0] != "GET"] == [
        ("DELETE", "blocks/old-block")
    ]


def test_generated_content_is_written_in_batches_of_100(monkeypatch):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    bodies = []

    def request(path, method="GET", body=None, query=None):
        if method == "PATCH":
            bodies.append((path, body))
            return {"results": [{"id": "new-block"}]}
        return {"results": []}

    monkeypatch.setattr(notion, "request", request)
    notion.replace_generated_book_content(
        "page-1", [{"type": "callout", "n": index} for index in range(250)]
    )

    batches = [body["children"] for path, body in bodies if path == "blocks/new-block/children"]
    assert [len(batch) for batch in batches] == [100, 100, 51]
    assert batches[0][0]["paragraph"]["rich_text"][0]["text"]["content"] == MARKER
    assert [block["n"] for batch in batches for block in batch[1:] if "n" in block][-1] == 249


def test_long_text_is_split_instead_of_truncated():
    text = "字" * 4500
    parts = text_value(text)
    assert [len(part["text"]["content"]) for part in parts] == [2000, 2000, 500]
    assert "".join(part["text"]["content"] for part in parts) == text
    assert text_value(None) == [{"type": "text", "text": {"content": ""}}]


def test_text_split_counts_emoji_as_two_characters():
    text = "😀" * 1500
    parts = split_text(text)
    assert [len(part) for part in parts] == [1000, 500]
    assert "".join(parts) == text


def test_callout_keeps_text_longer_than_notion_limit():
    text = "很长的想法" * 900
    rich_text = get_callout(text, "💭")["callout"]["rich_text"]
    assert len(rich_text) == 3
    assert all(len(item["text"]["content"]) <= 2000 for item in rich_text)
    assert "".join(item["text"]["content"] for item in rich_text) == text
    assert get_callout("", "💭")["callout"]["rich_text"][0]["text"]["content"] == ""


def test_select_names_never_contain_a_comma():
    notion = NotionWorkspace("token", "page", "version", client=Client())
    notion.schemas["书架"] = {"出版社": "select", "标签": "multi_select", "阅读状态": "status"}
    assert notion.property("书架", "出版社", "A,B") == {"select": {"name": "A，B"}}
    assert notion.property("书架", "标签", ["A,B", "", "C"]) == {
        "multi_select": [{"name": "A，B"}, {"name": "C"}]
    }
    assert notion.property("书架", "阅读状态", "在读") == {"status": {"name": "在读"}}
    assert notion.property("书架", "出版社", "") == {"select": None}


@pytest.mark.parametrize("year", [0, 1, 20233, -5])
def test_invalid_start_year_setting_falls_back_to_default(monkeypatch, year):
    notion = NotionWorkspace("token", "page", "version", client=Client())
    notion.sources["设置"] = "settings-source"
    monkeypatch.setattr(
        notion,
        "query_all",
        lambda database: [
            {
                "id": "settings-page",
                "properties": {"阅读统计起始年份": {"type": "number", "number": year}},
            }
        ],
    )
    assert notion.ensure_sync_settings(2023)["start_year"] == 2023
