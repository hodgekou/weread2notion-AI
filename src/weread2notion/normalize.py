from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


SHANGHAI = timezone(timedelta(hours=8))


def local_datetime(timestamp: int | float | None) -> datetime | None:
    return datetime.fromtimestamp(int(timestamp), SHANGHAI) if timestamp else None


def iso_date(timestamp: int | float | None) -> str | None:
    value = local_datetime(timestamp)
    return value.date().isoformat() if value else None


def iso_datetime(timestamp: int | float | None) -> str | None:
    value = local_datetime(timestamp)
    return value.isoformat(timespec="seconds") if value else None


def period_keys(timestamp: int | float) -> dict[str, str]:
    value = local_datetime(timestamp)
    assert value is not None
    monday = value.date() - timedelta(days=value.weekday())
    return {
        "day": value.date().isoformat(),
        "week": monday.isoformat(),
        "month": value.strftime("%Y-%m"),
        "year": value.strftime("%Y"),
    }


def progress_status(progress: dict[str, Any]) -> str:
    value = int(progress.get("progress") or 0)
    if value >= 100 or progress.get("finishTime"):
        return "已读"
    if value > 0 or progress.get("isStartReading") or progress.get("updateTime"):
        return "在读"
    return "想读"


def shelf_entries(shelf: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [{"kind": "book", **book} for book in (shelf.get("books") or [])]
    for item in shelf.get("albums") or []:
        info = item.get("albumInfo") or {}
        extra = item.get("albumInfoExtra") or {}
        entries.append(
            {
                "kind": "album",
                "bookId": f"album:{info.get('albumId')}",
                "title": info.get("name") or "未命名有声书",
                "author": info.get("authorName") or "",
                "cover": info.get("cover") or "",
                "intro": info.get("intro") or "",
                "readUpdateTime": extra.get("lectureReadUpdateTime")
                or info.get("updateTime"),
                "category": "有声书",
                "sort": extra.get("lectureReadUpdateTime")
                or info.get("updateTime")
                or 0,
            }
        )
    mp = shelf.get("mp")
    if mp:
        book = mp.get("book") or mp
        entries.append(
            {
                "kind": "mp",
                "bookId": book.get("bookId") or "mpbook",
                "title": book.get("title") or "文章收藏",
                "cover": book.get("cover") or "",
                "category": "文章收藏",
                "readUpdateTime": book.get("readUpdateTime") or book.get("updateTime"),
                "sort": book.get("readUpdateTime") or book.get("updateTime") or 0,
            }
        )
    return entries
