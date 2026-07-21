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
    monkeypatch.setattr(notion, "properties", lambda database, raw: {"Name": raw["Name"]})
    monkeypatch.setattr(notion, "find", lambda database, key, value: {"id": "year-page"})
    calls = []
    monkeypatch.setattr(notion, "request", lambda path, method, body: calls.append((path, method, body)))

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
