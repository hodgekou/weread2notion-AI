from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from notion_client import Client


REQUIRED_DATABASES = (
    "书架",
    "日",
    "周",
    "月",
    "年",
    "分类",
    "作者",
)

SETTINGS_DATABASE = "设置"
SETTINGS_TITLE = "同步设置"
SETTINGS_ICON = "https://www.notion.so/icons/settings_gray.svg"


def chunks(values: list[Any], size: int = 100) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def text_value(value: Any) -> list[dict[str, Any]]:
    value = "" if value is None else str(value)
    return [
        {"type": "text", "text": {"content": value[index : index + 2000]}}
        for index in range(0, len(value), 2000)
    ] or [{"type": "text", "text": {"content": ""}}]


class NotionWorkspace:
    """Operate on database rows only; never replace the dashboard page content."""

    def __init__(
        self,
        token: str,
        page_id: str,
        notion_version: str,
        interval: float = 0.34,
        client=None,
    ):
        self.client = client or Client(auth=token, notion_version=notion_version)
        self.page_id = page_id
        self.interval = interval
        self.databases: dict[str, str] = {}
        self.sources: dict[str, str] = {}
        self.schemas: dict[str, dict[str, str]] = {}
        self.titles: dict[str, str] = {}

    def request(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        last_error = None
        for attempt in range(5):
            time.sleep(self.interval if attempt == 0 else min(2**attempt, 8))
            try:
                return self.client.request(path=path, method=method, body=body)
            except Exception as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                status = getattr(exc, "status", None) or getattr(
                    response, "status_code", None
                )
                # Notion occasionally returns transient 429/5xx responses
                # during large syncs. Retry those, but surface validation and
                # permission errors immediately.
                if status != 429 and (status is None or status < 500):
                    raise
        raise last_error

    def list_children(self, block_id: str) -> list[dict[str, Any]]:
        rows, cursor = [], None
        while True:
            response = self.client.blocks.children.list(
                block_id=block_id, page_size=100, start_cursor=cursor
            )
            rows.extend(response.get("results") or [])
            if not response.get("has_more"):
                return rows
            cursor = response.get("next_cursor")

    def discover(self) -> "NotionWorkspace":
        def walk(block_id: str) -> None:
            for block in self.list_children(block_id):
                if block.get("type") == "child_database":
                    title = (block.get("child_database") or {}).get("title") or ""
                    self.databases.setdefault(title, block["id"])
                if block.get("has_children") and block.get("type") != "child_database":
                    walk(block["id"])

        walk(self.page_id)
        missing = [name for name in REQUIRED_DATABASES if name not in self.databases]
        if missing:
            raise RuntimeError(f"模板缺少数据库：{', '.join(missing)}")
        for name, database_id in self.databases.items():
            database = self.request(f"databases/{database_id}")
            sources = database.get("data_sources") or []
            source_id = sources[0]["id"] if sources else database_id
            self.sources[name] = source_id
            data_source = self.request(f"data_sources/{source_id}")
            properties = data_source.get("properties") or {}
            self.schemas[name] = {
                prop_name: (definition or {}).get("type")
                for prop_name, definition in properties.items()
            }
            self.titles[name] = next(
                (prop for prop, kind in self.schemas[name].items() if kind == "title"),
                "Name",
            )
        return self

    def ensure_sync_settings(self, default_start_year: int = 2023) -> dict[str, Any]:
        """Read user preferences, creating the settings database when absent."""
        if SETTINGS_DATABASE not in self.sources:
            database = self.request(
                "databases",
                "POST",
                {
                    "parent": {"type": "page_id", "page_id": self.page_id},
                    "title": text_value(SETTINGS_DATABASE),
                    "is_inline": True,
                    "icon": {"type": "external", "external": {"url": SETTINGS_ICON}},
                    "initial_data_source": {
                        "properties": {
                            "配置": {"title": {}},
                            "阅读完成进度强制改为100%": {"checkbox": {}},
                            "只同步我的书架书籍": {"checkbox": {}},
                            "同步划线和笔记": {"checkbox": {}},
                            "阅读统计起始年份": {
                                "number": {"format": "number"}
                            },
                            "同步配置版本（不可删除）": {
                                "number": {"format": "number"}
                            },
                        }
                    },
                },
            )
            database_id = database["id"]
            sources = database.get("data_sources") or []
            source_id = sources[0]["id"] if sources else database_id
            self.databases[SETTINGS_DATABASE] = database_id
            self.sources[SETTINGS_DATABASE] = source_id
            self.schemas[SETTINGS_DATABASE] = {
                "配置": "title",
                "阅读完成进度强制改为100%": "checkbox",
                "只同步我的书架书籍": "checkbox",
                "同步划线和笔记": "checkbox",
                "阅读统计起始年份": "number",
                "同步配置版本（不可删除）": "number",
            }
            self.titles[SETTINGS_DATABASE] = "配置"

        rows = self.query_all(SETTINGS_DATABASE)
        if not rows:
            page_id = self.create(
                SETTINGS_DATABASE,
                {
                    "配置": SETTINGS_TITLE,
                    "阅读完成进度强制改为100%": False,
                    "只同步我的书架书籍": True,
                    "同步划线和笔记": True,
                    "阅读统计起始年份": default_start_year,
                    "同步配置版本（不可删除）": 0,
                },
                SETTINGS_ICON,
            )
            self.request(
                f"blocks/{page_id}/children",
                "PATCH",
                {
                    "children": [
                        {
                            "object": "block",
                            "type": "callout",
                            "callout": {
                                "icon": {"type": "emoji", "emoji": "⚙️"},
                                "rich_text": text_value(
                                    "WeRead2Notion 每次同步前都会读取本页属性。"
                                    "删除本数据库或缺少字段时，将自动使用系统默认值。"
                                ),
                            },
                        },
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": text_value(
                                    "阅读完成进度强制改为100%：只改变 Notion 展示，不修改微信读书真实进度。"
                                )
                            },
                        },
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": text_value(
                                    "阅读统计起始年份：使用数字填写，例如 2023。"
                                )
                            },
                        },
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": text_value(
                                    "同步配置版本（不可删除）：由系统维护，请勿手动修改。"
                                )
                            },
                        },
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": text_value(
                                    "只同步我的书架书籍：移除不在当前书架中的书籍及自动同步内容。"
                                )
                            },
                        },
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": text_value(
                                    "同步划线和笔记：关闭后不再更新书籍正文中的自动同步内容。"
                                )
                            },
                        },
                    ]
                },
            )
            rows = self.query_all(SETTINGS_DATABASE)

        properties = (rows[0].get("properties") or {}) if rows else {}

        def value(name: str, default: Any) -> Any:
            parsed = self.plain_property(properties.get(name))
            return default if parsed is None else parsed

        def compatible_value(name: str, old_name: str, default: Any) -> Any:
            if name in properties:
                return value(name, default)
            return value(old_name, default)

        settings = {
            "completed_progress_100": bool(
                compatible_value(
                    "阅读完成进度强制改为100%", "已读进度显示为100%", False
                )
            ),
            "delete_removed": bool(
                compatible_value("只同步我的书架书籍", "移出书架时删除", True)
            ),
            "sync_notes": bool(value("同步划线和笔记", True)),
            "start_year": int(value("阅读统计起始年份", default_start_year)),
        }
        config_code = (
            1_000_000
            + settings["start_year"] * 8
            + int(settings["completed_progress_100"])
            + int(settings["delete_removed"]) * 2
            + int(settings["sync_notes"]) * 4
        )
        config_property = (
            "同步配置版本（不可删除）"
            if "同步配置版本（不可删除）" in properties
            else "已应用配置码"
        )
        settings["settings_changed"] = value(config_property, 0) != config_code
        settings["_config_code"] = config_code
        settings["_config_property"] = config_property
        settings["_page_id"] = rows[0].get("id") if rows else None
        return settings

    def mark_sync_settings_applied(
        self,
        page_id: str | None,
        config_code: int,
        config_property: str = "同步配置版本（不可删除）",
    ) -> None:
        if not page_id:
            return
        self.request(
            f"pages/{page_id}",
            "PATCH",
            {
                "properties": self.properties(
                    SETTINGS_DATABASE, {config_property: config_code}
                )
            },
        )

    def query_all(self, database_name: str, filter_: dict | None = None) -> list[dict]:
        rows, cursor = [], None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            if filter_:
                body["filter"] = filter_
            response = self.request(
                f"data_sources/{self.sources[database_name]}/query", "POST", body
            )
            rows.extend(response.get("results") or [])
            if not response.get("has_more"):
                return rows
            cursor = response.get("next_cursor")

    def property(self, database: str, name: str, value: Any) -> dict | None:
        kind = self.schemas[database].get(name)
        if not kind or value is None:
            return None
        if kind == "title":
            return {"title": text_value(value)}
        if kind == "rich_text":
            return {"rich_text": text_value(value)}
        if kind == "number":
            return {"number": float(value) if value != "" else None}
        if kind == "url":
            return {"url": str(value) or None}
        if kind == "date":
            if not value:
                return {"date": None}
            if isinstance(value, dict):
                return {"date": value}
            return {"date": {"start": value}}
        if kind == "relation":
            return {"relation": [{"id": item} for item in (value or [])]}
        if kind in {"select", "status"}:
            return {kind: {"name": str(value)}} if value else {kind: None}
        if kind == "multi_select":
            values = value if isinstance(value, (list, tuple, set)) else [value]
            return {"multi_select": [{"name": str(item)} for item in values if item]}
        if kind == "checkbox":
            return {"checkbox": bool(value)}
        return None

    def properties(self, database: str, raw: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for name, value in raw.items():
            prop = self.property(database, name, value)
            if prop is not None:
                result[name] = prop
        return result

    def find(self, database: str, property_name: str, value: Any) -> dict | None:
        kind = self.schemas[database].get(property_name)
        if kind not in {"title", "rich_text", "number", "url"}:
            return None
        query_kind = "rich_text" if kind == "url" else kind
        rows = self.query_all(
            database,
            {"property": property_name, query_kind: {"equals": value}},
        )
        return rows[0] if rows else None

    def upsert(
        self,
        database: str,
        key_name: str,
        key_value: Any,
        raw: dict[str, Any],
        icon: str | None = None,
        cover: str | None = None,
        existing_id: str | None = None,
    ) -> str:
        properties = self.properties(database, raw)
        existing = (
            {"id": existing_id}
            if existing_id
            else self.find(database, key_name, key_value)
        )
        if existing:
            body: dict[str, Any] = {"properties": properties}
            if icon:
                body["icon"] = {"type": "external", "external": {"url": icon}}
            if cover:
                body["cover"] = {"type": "external", "external": {"url": cover}}
            self.request(f"pages/{existing['id']}", "PATCH", body)
            return existing["id"]
        body = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": self.sources[database],
            },
            "properties": properties,
        }
        if icon:
            body["icon"] = {"type": "external", "external": {"url": icon}}
        if cover:
            body["cover"] = {"type": "external", "external": {"url": cover}}
        return self.request("pages", "POST", body)["id"]

    def row_index(self, database: str, key_name: str) -> dict[str, dict[str, Any]]:
        """Load a database once and index rows by a stable property value."""
        result = {}
        for row in self.query_all(database):
            properties = row.get("properties") or {}
            key = self.plain_property(properties.get(key_name))
            if key is None or key == "":
                continue
            if isinstance(key, float) and key.is_integer():
                key = int(key)
            result[str(key)] = {
                "page_id": row["id"],
                "properties": properties,
            }
        return result

    def create(
        self,
        database: str,
        raw: dict[str, Any],
        icon: str | None = None,
        cover: str | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": self.sources[database],
            },
            "properties": self.properties(database, raw),
        }
        if icon:
            body["icon"] = {"type": "external", "external": {"url": icon}}
        if cover:
            body["cover"] = {"type": "external", "external": {"url": cover}}
        return self.request("pages", "POST", body)["id"]

    def archive_rows(
        self, database: str, relation: tuple[str, str] | None = None
    ) -> int:
        filter_ = None
        if relation:
            filter_ = {"property": relation[0], "relation": {"contains": relation[1]}}
        rows = self.query_all(database, filter_)
        for row in rows:
            self.request(f"pages/{row['id']}", "PATCH", {"in_trash": True})
        return len(rows)

    def replace_generated_book_content(
        self, page_id: str, children: list[dict[str, Any]]
    ) -> None:
        """Replace only the generated synced block, preserving user blocks."""
        marker = "由 WeRead2Notion 自动同步"
        for block in self.list_children(page_id):
            if block.get("type") != "synced_block" or not block.get("has_children"):
                continue
            nested = self.list_children(block["id"])
            if not nested or nested[0].get("type") != "paragraph":
                continue
            rich_text = (nested[0].get("paragraph") or {}).get("rich_text") or []
            text = "".join(item.get("plain_text", "") for item in rich_text)
            if text == marker:
                self.request(f"blocks/{block['id']}", "DELETE")

        if not children:
            return
        response = self.request(
            f"blocks/{page_id}/children",
            "PATCH",
            {
                "children": [
                    {
                        "object": "block",
                        "type": "synced_block",
                        "synced_block": {"synced_from": None},
                    }
                ]
            },
        )
        container_id = response["results"][0]["id"]
        marker_block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": marker},
                        "annotations": {"color": "gray"},
                    }
                ]
            },
        }
        for batch in chunks([marker_block, *children], 100):
            self.request(
                f"blocks/{container_id}/children",
                "PATCH",
                {"children": batch},
            )

    @staticmethod
    def plain_property(prop: dict | None) -> Any:
        if not prop:
            return None
        kind = prop.get("type")
        value = prop.get(kind)
        if kind in {"title", "rich_text"}:
            return "".join(item.get("plain_text", "") for item in (value or []))
        if kind in {"number", "url", "checkbox"}:
            return value
        if kind in {"select", "status"}:
            return (value or {}).get("name")
        return value

    def book_index(self) -> dict[str, dict[str, Any]]:
        result = {}
        for row in self.query_all("书架"):
            properties = row.get("properties") or {}
            book_id = self.plain_property(properties.get("BookId"))
            if book_id:
                result[str(book_id)] = {
                    "page_id": row["id"],
                    "sort": self.plain_property(properties.get("Sort")) or 0,
                    "sync_version": self.plain_property(properties.get("同步版本"))
                    or 0,
                }
        return result

    def backup_and_archive(self, backup_dir: Path, databases: Iterable[str]) -> Path:
        backup_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now().astimezone().isoformat(),
            "notion_page_id": self.page_id,
            "databases": {},
        }
        rows_by_database = {}
        for name in databases:
            rows = self.query_all(name)
            rows_by_database[name] = rows
            payload["databases"][name] = rows
        target = backup_dir / f"weread2notion-{datetime.now():%Y%m%d-%H%M%S}.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for rows in rows_by_database.values():
            for row in rows:
                self.request(f"pages/{row['id']}", "PATCH", {"in_trash": True})
        return target
