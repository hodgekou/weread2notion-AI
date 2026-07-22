from weread2notion.sync import Synchronizer


class Notion:
    titles = {
        "书架": "书名",
        "日": "标题",
        "周": "标题",
        "月": "标题",
        "年": "标题",
    }

    def __init__(self):
        self.rows = []
        self.requests = []
        self.archived = []
        self.indexes = {}
        self.sources = {}
        self.schemas = {
            name: {"时长": "number", "时长（分钟）": "number"}
            for name in ("日", "周", "月", "年", "阅读记录")
        }

    def upsert(
        self,
        database,
        key_name,
        key_value,
        raw,
        icon,
        cover=None,
        existing_id=None,
    ):
        self.rows.append((database, raw))
        return existing_id or f"{database}:{key_value}"

    def request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        return {}

    def properties(self, database, raw):
        return raw

    def row_index(self, database, key_name):
        return self.indexes.get(database, {})

    @staticmethod
    def plain_property(prop):
        if not prop:
            return None
        value = prop.get(prop.get("type"))
        return value

    def archive_rows(self, *args, **kwargs):
        self.archived.append((args, kwargs))
        return 1

    def create(self, database, raw, icon):
        self.rows.append((database, raw))
        return f"{database}:created"

    def replace_generated_book_content(self, page_id, blocks):
        self.rows.append(("正文", {"page_id": page_id, "blocks": blocks}))


def test_period_rows_have_valid_date_ranges():
    notion = Notion()
    sync = Synchronizer(None, notion)
    sync.sync_periods([{"timestamp": 1691251200, "duration": 600}])
    ranges = {database: raw["日期"] for database, raw in notion.rows}
    assert ranges["日"] == {"start": "2023-08-06", "end": None}
    assert ranges["周"] == {"start": "2023-07-31", "end": "2023-08-06"}
    assert ranges["月"] == {"start": "2023-08-01", "end": "2023-08-31"}
    assert ranges["年"] == {"start": "2023-01-01", "end": "2023-12-31"}
    day = next(raw for database, raw in notion.rows if database == "日")
    assert day["时长（分钟）"] == 10


def test_book_sync_uses_accumulated_reading_time():
    notion = Notion()
    sync = Synchronizer(None, notion)
    sync.sync_books(
        {"book-1": {"title": "测试书籍"}},
        {
            "book-1": {
                "info": {"title": "测试书籍"},
                "progress": {
                    "progress": 50,
                    "readingTime": 3206,
                    "recordReadingTime": 0,
                },
            }
        },
        {},
        {},
        {"day": {}, "week": {}, "month": {}, "year": {}},
        {"book-1"},
        {},
    )
    book = next(raw for database, raw in notion.rows if database == "书架")
    assert book["阅读时长"] == 3206
    assert book["阅读时长（分钟）"] == 3206 / 60
    assert "同步版本" not in book


def test_book_period_relations_use_finish_time_not_last_read_time():
    notion = Notion()
    sync = Synchronizer(None, notion)
    finish_time = 1704067200  # 2024-01-01 Asia/Shanghai
    last_read_time = 1735689600  # 2025-01-01 Asia/Shanghai
    periods = {
        "day": {"2024-01-01": "day-2024"},
        "week": {"2024-01-01": "week-2024"},
        "month": {"2024-01": "month-2024"},
        "year": {"2024": "year-2024", "2025": "year-2025"},
    }
    sync.sync_books(
        {"book-1": {"title": "测试书籍", "finishReading": 1}},
        {
            "book-1": {
                "info": {"title": "测试书籍"},
                "progress": {
                    "progress": 100,
                    "finishTime": finish_time,
                    "updateTime": last_read_time,
                },
            }
        },
        {},
        {},
        periods,
        {"book-1"},
        {},
    )
    book = next(raw for database, raw in notion.rows if database == "书架")
    assert book["阅读完成时间"] == "2024-01-01"
    assert book["最后阅读时间"] == "2025-01-01"
    assert book["年"] == ["year-2024"]


def test_book_status_uses_explicit_shelf_finish_marker():
    notion = Notion()
    sync = Synchronizer(None, notion)
    sync.sync_books(
        {"book-1": {"title": "生死疲劳", "finishReading": 1}},
        {
            "book-1": {
                "info": {"title": "生死疲劳"},
                "progress": {"progress": 12, "readingTime": 600},
            }
        },
        {},
        {},
        {"day": {}, "week": {}, "month": {}, "year": {}},
        {"book-1"},
        {},
    )
    book = next(raw for database, raw in notion.rows if database == "书架")
    assert book["阅读状态"] == "已读"


def test_completed_progress_can_be_displayed_as_100_percent():
    notion = Notion()
    sync = Synchronizer(
        None, notion, preferences={"completed_progress_100": True}
    )
    sync.sync_books(
        {"book-1": {"title": "测试书籍", "finishReading": 1}},
        {
            "book-1": {
                "info": {"title": "测试书籍"},
                "progress": {"progress": 40},
            }
        },
        {},
        {},
        {"day": {}, "week": {}, "month": {}, "year": {}},
        {"book-1"},
        {},
    )
    book = next(raw for database, raw in notion.rows if database == "书架")
    assert book["阅读进度"] == 1


def test_sync_version_is_marked_only_after_book_content():
    notion = Notion()
    sync = Synchronizer(None, notion)
    sync.sync_book_content(
        {
            "book-1": {
                "chapters": [],
                "highlights": [],
                "reviews": [],
            }
        },
        {"book-1": "page-1"},
        {"day": {}, "week": {}, "month": {}, "year": {}},
    )
    assert notion.rows[-1] == ("正文", {"page_id": "page-1", "blocks": []})
    assert notion.requests[-1][0] == (
        "pages/page-1",
        "PATCH",
        {"properties": {"同步版本": 8}},
    )


def test_periods_include_zero_duration_book_dates():
    notion = Notion()
    sync = Synchronizer(None, notion)
    maps = sync.sync_periods([], [1784563200])
    assert "2026" in maps["year"]
    assert "2026-07" in maps["month"]


def test_unchanged_periods_do_not_write_pages():
    notion = Notion()
    timestamp = 1691251200
    notion.indexes = {
        "日": {
            "2023-08-06": {
                "page_id": "day-page",
                "properties": {
                    "时长": {"type": "number", "number": 600},
                    "时长（分钟）": {"type": "number", "number": 10},
                },
            }
        },
        "周": {
            "2023-07-31": {
                "page_id": "week-page",
                "properties": {
                    "时长": {"type": "number", "number": 600},
                    "时长（分钟）": {"type": "number", "number": 10},
                },
            }
        },
        "月": {
            "2023-08": {
                "page_id": "month-page",
                "properties": {
                    "时长": {"type": "number", "number": 600},
                    "时长（分钟）": {"type": "number", "number": 10},
                },
            }
        },
        "年": {
            "2023": {
                "page_id": "year-page",
                "properties": {
                    "时长": {"type": "number", "number": 600},
                    "时长（分钟）": {"type": "number", "number": 10},
                },
            }
        },
    }
    sync = Synchronizer(None, notion)
    maps = sync.sync_periods([{"timestamp": timestamp, "duration": 600}])
    assert maps["day"]["2023-08-06"] == "day-page"
    assert notion.rows == []
    assert notion.requests == []


def test_rollup_period_metrics_are_not_patched():
    notion = Notion()
    notion.schemas["月"] = {"时长": "rollup"}
    notion.indexes = {
        "月": {
            "2023-08": {
                "page_id": "month-page",
                "properties": {"时长": {"type": "rollup", "rollup": {}}},
            }
        }
    }
    sync = Synchronizer(None, notion)
    sync.sync_periods([{"timestamp": 1691251200, "duration": 600}], full=False)
    month_updates = [
        request for request in notion.requests if request[0][0] == "pages/month-page"
    ]
    assert month_updates == []


def test_existing_people_and_categories_are_reused_without_writes():
    notion = Notion()
    notion.titles.update({"作者": "姓名", "分类": "名称"})
    notion.indexes = {
        "作者": {"作者甲": {"page_id": "author-page", "properties": {}}},
        "分类": {"分类甲": {"page_id": "category-page", "properties": {}}},
    }
    sync = Synchronizer(None, notion)
    authors, categories = sync.sync_people_and_categories(
        [{"author": "作者甲", "category": "分类甲"}], {}
    )
    assert authors == {"作者甲": "author-page"}
    assert categories == {"分类甲": "category-page"}
    assert notion.rows == []


def test_unchanged_reading_records_do_not_write_pages():
    notion = Notion()
    notion.titles["阅读记录"] = "标题"
    notion.sources = {"阅读记录": "source"}
    notion.indexes = {
        "阅读记录": {
            "1691251200": {
                "page_id": "record-page",
                "properties": {
                    "时长": {"type": "number", "number": 600},
                    "时长（分钟）": {"type": "number", "number": 10},
                },
            }
        }
    }
    sync = Synchronizer(None, notion)
    sync.sync_reading_records(
        [{"timestamp": 1691251200, "duration": 600}],
        {"day": {}, "week": {}, "month": {}, "year": {}},
    )
    assert notion.rows == []
    assert notion.requests == []


def test_book_content_is_grouped_by_chapter():
    blocks = Synchronizer.book_content_blocks(
        {
            "chapters": [{"chapterUid": 1, "chapterIdx": 1, "title": "第一章"}],
            "highlights": [{"chapterUid": 1, "markText": "一条划线"}],
            "reviews": [],
        }
    )
    assert blocks[0]["type"] == "table_of_contents"
    assert blocks[1]["heading_2"]["rich_text"][0]["text"]["content"] == "第一章"
    assert blocks[2]["callout"]["rich_text"][0]["text"]["content"] == "一条划线"


def test_plan_uses_shelf_as_authoritative_source():
    class Weread:
        def shelf(self):
            return {"books": [{"bookId": "on-shelf", "title": "书架中的书"}]}

        def notebooks(self):
            return (
                [
                    {"bookId": "on-shelf", "sort": 2},
                    {"bookId": "removed", "sort": 3},
                ],
                {"books": 2, "notes": 1},
            )

    plan = Synchronizer(Weread(), Notion()).plan()
    assert plan["book_ids"] == ["on-shelf"]
    assert [entry["bookId"] for entry in plan["entries"]] == ["on-shelf"]


def test_removed_book_and_related_rows_are_moved_to_trash():
    notion = Notion()
    notion.sources = {"笔记": "notes", "划线": "marks"}
    notion.schemas.update(
        {
            "笔记": {"书籍": "relation"},
            "划线": {"书籍": "relation"},
        }
    )
    sync = Synchronizer(None, notion)
    sync.delete_removed_books(
        {"removed"}, {"removed": {"page_id": "book-page"}}
    )

    assert [call[0] for call in notion.archived] == [
        ("笔记", ("书籍", "book-page")),
        ("划线", ("书籍", "book-page")),
    ]
    assert notion.requests[-1][0] == (
        "pages/book-page",
        "PATCH",
        {"in_trash": True},
    )
    assert sync.counts["删除书架"] == 1
