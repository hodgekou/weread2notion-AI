from weread2notion.normalize import period_keys, progress_status, shelf_entries


def test_shelf_entries_include_albums_and_mp():
    shelf = {
        "books": [{"bookId": "1", "title": "电子书"}],
        "albums": [{"albumInfo": {"albumId": "2", "name": "有声书"}}],
        "mp": {"book": {"bookId": "mpbook", "title": "文章收藏"}},
    }
    assert [row["bookId"] for row in shelf_entries(shelf)] == ["1", "album:2", "mpbook"]


def test_progress_is_percentage_not_fraction():
    assert progress_status({"progress": 1}) == "在读"
    assert progress_status({"progress": 100}) == "已读"


def test_shelf_timestamp_does_not_mark_unread_book_as_reading():
    assert (
        progress_status({"progress": 0, "isStartReading": 0, "updateTime": 1}) == "想读"
    )
    assert progress_status({"progress": 0, "readingTime": 60}) == "在读"


def test_period_keys_use_monday_week():
    keys = period_keys(1691251200)
    assert keys["day"] == "2023-08-06"
    assert keys["week"] == "2023-07-31"
    assert keys["month"] == "2023-08"
    assert keys["year"] == "2023"
