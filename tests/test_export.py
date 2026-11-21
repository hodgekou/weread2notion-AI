import json

import pytest

from weread2notion.export import export_weread
from weread2notion.weread import WeReadError


class Client:
    def shelf(self):
        return {"books": [{"bookId": "b1", "title": "测试书"}]}

    def book_bundle(self, book_id):
        return {
            "info": {"intro": "简介"},
            "highlights": [{"markText": "划线内容"}],
            "reviews": [{"content": "我的想法"}],
        }


def test_export_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = export_weread(Client(), "export", "markdown")
    assert result["books"] == 1
    payload = json.loads((tmp_path / "export" / "manifest.json").read_text())
    assert payload["books"][0]["entry"]["bookId"] == "b1"
    markdown = (tmp_path / "export" / "books" / "测试书.md").read_text()
    assert "划线内容" in markdown
    assert "我的想法" in markdown


class MixedShelf:
    """A shelf with an audiobook, the article collection and an unreadable book."""

    def __init__(self):
        self.requested = []

    def shelf(self):
        return {
            "books": [
                {"bookId": "b1", "title": "同名书"},
                {"bookId": "b2", "title": "同名书"},
                {"bookId": "broken", "title": "读取失败的书"},
            ],
            "albums": [{"albumInfo": {"albumId": 7, "name": "有声书"}}],
            "mp": {"book": {"bookId": "mp1", "title": "文章收藏"}},
        }

    def book_bundle(self, book_id):
        self.requested.append(book_id)
        if book_id == "broken":
            raise WeReadError("阶段=基本信息; 接口=/book/info; errcode=-2010")
        return {"info": {}, "highlights": [{"markText": f"{book_id} 的划线"}], "reviews": []}


def test_export_only_requests_details_for_books(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = MixedShelf()

    result = export_weread(client, "export", "json")

    # Audiobooks and the article collection have no book details to fetch.
    assert client.requested == ["b1", "b2", "broken"]
    assert result["books"] == 5


def test_export_continues_after_one_book_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = export_weread(MixedShelf(), "export", "markdown")

    assert result["failed_books"] == [
        {"book_id": "broken", "error": "阶段=基本信息; 接口=/book/info; errcode=-2010"}
    ]
    payload = json.loads((tmp_path / "export" / "manifest.json").read_text())
    by_id = {item["entry"]["bookId"]: item for item in payload["books"]}
    assert "error" in by_id["broken"] and by_id["broken"]["bundle"] == {}
    assert "error" not in by_id["b1"]
    assert (tmp_path / "export" / "books" / "有声书.md").exists()


def test_export_keeps_both_books_with_the_same_title(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    export_weread(MixedShelf(), "export", "markdown")

    books_dir = tmp_path / "export" / "books"
    assert "b1 的划线" in (books_dir / "同名书.md").read_text()
    assert "b2 的划线" in (books_dir / "同名书-b2.md").read_text()


@pytest.mark.parametrize("output", ["../outside", "/tmp/absolute"])
def test_export_rejects_paths_outside_the_working_directory(tmp_path, monkeypatch, output):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        export_weread(MixedShelf(), output, "json")
