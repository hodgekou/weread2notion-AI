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

    def upsert(self, database, key_name, key_value, raw, icon, cover=None):
        self.rows.append((database, raw))
        return f"{database}:{key_value}"

    def request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        return {}

    def properties(self, database, raw):
        return raw

    def archive_rows(self, *args, **kwargs):
        return None

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
        {"book-1": {"title": "测试书籍"}},
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
        {"properties": {"同步版本": 7}},
    )


def test_periods_include_zero_duration_book_dates():
    notion = Notion()
    sync = Synchronizer(None, notion)
    maps = sync.sync_periods([], [1784563200])
    assert "2026" in maps["year"]
    assert "2026-07" in maps["month"]


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
