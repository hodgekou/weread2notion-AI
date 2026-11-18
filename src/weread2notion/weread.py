from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import requests

from .config import DEFAULT_WEREAD_SKILL_VERSION

logger = logging.getLogger(__name__)
GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"


class WeReadError(RuntimeError):
    pass


class WeReadClient:
    def __init__(
        self, api_key: str, skill_version: str = DEFAULT_WEREAD_SKILL_VERSION, session=None
    ):
        self.skill_version = skill_version
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def call(self, api_name: str, **params: Any) -> dict[str, Any]:
        payload = {"api_name": api_name, "skill_version": self.skill_version, **params}
        last_error = None
        for attempt in range(3):
            try:
                response = self.session.post(GATEWAY_URL, json=payload, timeout=45)
                response.raise_for_status()
                data = response.json()
                if data.get("errcode", 0) != 0:
                    raise WeReadError(
                        f"{api_name} 返回 errcode={data.get('errcode')}: {data.get('errmsg', '')}"
                    )
                upgrade_info = data.get("upgrade_info")
                if upgrade_info is not None:
                    message = (
                        upgrade_info.get("message")
                        if isinstance(upgrade_info, dict)
                        else upgrade_info
                    )
                    logger.warning(
                        "微信读书技能升级提示：%s", message or "请查看微信读书 Skill 文档"
                    )
                return data
            except WeReadError:
                raise
            except Exception as exc:  # requests and transient JSON failures
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise WeReadError(f"{api_name} 请求失败：{last_error}")

    def shelf(self) -> dict[str, Any]:
        data = self.call("/shelf/sync")
        # Missing collections cannot be treated as an empty shelf for sync.
        books = data.get("books")
        albums = data.get("albums")
        if not isinstance(books, list) or not isinstance(albums, list):
            raise WeReadError("/shelf/sync 回包必须包含 books 和 albums 数组")

        for book in books:
            book_id = book.get("bookId") if isinstance(book, dict) else None
            if not isinstance(book_id, str) or not book_id.strip():
                raise WeReadError("/shelf/sync 回包中的书籍条目缺少有效的 bookId")
        for album in albums:
            info = album.get("albumInfo") if isinstance(album, dict) else None
            album_id = info.get("albumId") if isinstance(info, dict) else None
            if not (
                (isinstance(album_id, str) and album_id.strip())
                or (type(album_id) is int and album_id > 0)
            ):
                raise WeReadError(
                    "/shelf/sync 回包中的专辑条目缺少有效的 albumInfo.albumId"
                )

        mp = data.get("mp")
        if mp is not None and not isinstance(mp, dict):
            raise WeReadError("/shelf/sync 回包中的 mp 必须为对象或 null")
        return data

    def notebooks(self) -> tuple[list[dict[str, Any]], dict[str, int]]:
        rows: list[dict[str, Any]] = []
        last_sort = None
        totals = {"books": 0, "notes": 0}
        while True:
            params: dict[str, Any] = {"count": 100}
            if last_sort is not None:
                params["lastSort"] = last_sort
            data = self.call("/user/notebooks", **params)
            batch = data.get("books") or []
            rows.extend(batch)
            totals = {
                "books": int(data.get("totalBookCount") or len(rows)),
                "notes": int(data.get("totalNoteCount") or 0),
            }
            if not data.get("hasMore") or not batch:
                break
            last_sort = batch[-1].get("sort")
        return rows, totals

    def book_bundle(self, book_id: str) -> dict[str, Any]:
        def fetch(stage: str, api_name: str, **params: Any) -> dict[str, Any]:
            try:
                return self.call(api_name, **params)
            except WeReadError as exc:
                raise WeReadError(
                    f"阶段={stage}; 接口={api_name}; {exc}"
                ) from exc

        info = fetch("基本信息", "/book/info", bookId=book_id)
        progress = fetch("阅读进度", "/book/getprogress", bookId=book_id).get("book") or {}
        chapter_data = fetch("章节目录", "/book/chapterinfo", bookId=book_id)
        bookmark_data = fetch("划线", "/book/bookmarklist", bookId=book_id)
        reviews: list[dict[str, Any]] = []
        synckey = 0
        while True:
            page = fetch(
                "笔记", "/review/list/mine", bookid=book_id, synckey=synckey, count=100
            )
            reviews.extend(
                (item.get("review") or item) for item in (page.get("reviews") or [])
            )
            if not page.get("hasMore"):
                break
            next_key = page.get("synckey")
            if next_key == synckey:
                break
            synckey = next_key
        return {
            "info": info,
            "progress": progress,
            "chapters": chapter_data.get("chapters") or [],
            "highlights": bookmark_data.get("updated") or [],
            "reviews": reviews,
        }

    def reading_days(
        self, start_year: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        overall = self.call("/readdata/detail", mode="overall")
        current_year = datetime.now().year
        days: dict[int, int] = {}
        annual: dict[int, dict[str, Any]] = {}
        for year in range(start_year, current_year + 1):
            base_time = int(datetime(year, 1, 15).timestamp())
            data = self.call("/readdata/detail", mode="annually", baseTime=base_time)
            annual[year] = data
            daily = data.get("dailyReadTimes") or {}
            # The current gateway commonly omits dailyReadTimes in annual mode.
            # annual.readTimes is monthly, so query only the non-empty months to
            # obtain their day buckets from monthly.readTimes.
            if not daily:
                for month_timestamp, month_seconds in (data.get("readTimes") or {}).items():
                    if not int(month_seconds or 0):
                        continue
                    monthly = self.call(
                        "/readdata/detail",
                        mode="monthly",
                        baseTime=int(month_timestamp),
                    )
                    month_days = monthly.get("dailyReadTimes") or monthly.get("readTimes") or {}
                    daily.update(month_days)
            for timestamp, seconds in daily.items():
                days[int(timestamp)] = int(seconds or 0)
        return [
            {"timestamp": timestamp, "duration": duration}
            for timestamp, duration in sorted(days.items())
            if duration > 0
        ], {"overall": overall, "annual": annual}
