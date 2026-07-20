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

    def upsert(self, database, key_name, key_value, raw, icon, cover=None):
        self.rows.append((database, raw))
        return f"{database}:{key_value}"

    def request(self, *args, **kwargs):
        return {}

    def properties(self, database, raw):
        return raw


def test_period_rows_have_valid_date_ranges():
    notion = Notion()
    sync = Synchronizer(None, notion)
    sync.sync_periods([{"timestamp": 1691251200, "duration": 600}])
    ranges = {database: raw["日期"] for database, raw in notion.rows}
    assert ranges["日"] == {"start": "2023-08-06", "end": None}
    assert ranges["周"] == {"start": "2023-07-31", "end": "2023-08-06"}
    assert ranges["月"] == {"start": "2023-08-01", "end": "2023-08-31"}
    assert ranges["年"] == {"start": "2023-01-01", "end": "2023-12-31"}


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
    assert book["同步版本"] == 4
