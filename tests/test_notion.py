from weread2notion.notion import NotionWorkspace


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
