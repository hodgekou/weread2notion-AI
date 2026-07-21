from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from .normalize import (
    iso_date,
    iso_datetime,
    period_keys,
    progress_status,
    shelf_entries,
)
from .blocks import get_callout, get_heading, get_table_of_contents


BOOK_ICON = "https://www.notion.so/icons/book_gray.svg"
TAG_ICON = "https://www.notion.so/icons/tag_gray.svg"
USER_ICON = "https://www.notion.so/icons/user-circle-filled_gray.svg"
TARGET_ICON = "https://www.notion.so/icons/target_red.svg"
SYNC_VERSION = 5


class Synchronizer:
    def __init__(self, weread, notion, start_year: int = 2023, dry_run: bool = False):
        self.weread = weread
        self.notion = notion
        self.start_year = start_year
        self.dry_run = dry_run
        self.counts = defaultdict(int)

    def plan(self) -> dict[str, Any]:
        shelf = self.weread.shelf()
        notebooks, totals = self.weread.notebooks()
        entries = shelf_entries(shelf)
        ids = {item.get("bookId") for item in entries if item.get("kind") == "book"}
        ids.update(item.get("bookId") for item in notebooks)
        return {
            "shelf": shelf,
            "notebooks": notebooks,
            "entries": entries,
            "book_ids": sorted(item for item in ids if item),
            "note_totals": totals,
        }

    def run(self, full: bool = False, backup_dir=None) -> dict[str, Any]:
        plan = self.plan()
        if self.dry_run:
            return {
                "mode": "dry-run",
                "shelf_entries": len(plan["entries"]),
                "related_books": len(plan["book_ids"]),
                "notebook_totals": plan["note_totals"],
            }
        entry_by_id = {entry["bookId"]: entry for entry in plan["entries"]}
        for notebook in plan["notebooks"]:
            book = notebook.get("book") or notebook
            book_id = notebook.get("bookId") or book.get("bookId")
            if book_id and book_id not in entry_by_id:
                entry_by_id[book_id] = {
                    "kind": "book",
                    **book,
                    "sort": notebook.get("sort", 0),
                }
            elif book_id:
                entry_by_id[book_id]["sort"] = max(
                    int(entry_by_id[book_id].get("sort") or 0),
                    int(notebook.get("sort") or 0),
                )

        existing = {} if full else self.notion.book_index()
        changed_ids = {
            book_id
            for book_id, entry in entry_by_id.items()
            if full
            or book_id not in existing
            or int(existing[book_id].get("sync_version") or 0) < SYNC_VERSION
            or int(entry.get("sort") or entry.get("readUpdateTime") or 0)
            > int(existing[book_id].get("sort") or 0)
        }

        days, stats = self.weread.reading_days(self.start_year)
        bundles = {}
        electronic_ids = [
            book_id
            for book_id in sorted(changed_ids)
            if entry_by_id[book_id].get("kind") == "book"
        ]
        for index, book_id in enumerate(electronic_ids, 1):
            print(f"读取书籍 {index}/{len(electronic_ids)}: {book_id}")
            bundles[book_id] = self.weread.book_bundle(book_id)

        # Only start destructive work after every WeRead request has succeeded.
        if full:
            data_databases = [
                name
                for name in (
                    "书架",
                    "笔记",
                    "划线",
                    "日",
                    "周",
                    "月",
                    "年",
                    "分类",
                    "作者",
                    "章节",
                    "阅读记录",
                    "阅读记录1",
                    "阅读记录2",
                )
                if name in self.notion.sources
            ]
            old_count = sum(len(self.notion.query_all(name)) for name in data_databases)
            self.counts["backup"] = str(
                self.notion.backup_and_archive(backup_dir, data_databases)
            )
            self.counts["archived"] = old_count
            existing = {}

        related_timestamps = []
        for book_id, entry in entry_by_id.items():
            bundle = bundles.get(book_id, {})
            progress = bundle.get("progress") or {}
            timestamp = (
                progress.get("updateTime")
                or entry.get("readUpdateTime")
                or entry.get("sort")
            )
            if timestamp:
                related_timestamps.append(int(timestamp))
            for item in [
                *(bundle.get("highlights") or []),
                *(bundle.get("reviews") or []),
            ]:
                if item.get("createTime"):
                    related_timestamps.append(int(item["createTime"]))

        periods = self.sync_periods(days, related_timestamps)

        authors, categories = self.sync_people_and_categories(
            entry_by_id.values(), bundles
        )
        books = self.sync_books(
            entry_by_id,
            bundles,
            authors,
            categories,
            periods,
            changed_ids,
            existing,
        )
        self.sync_book_content(bundles, books, periods)
        self.sync_reading_records(days, periods)
        self.counts["reading_seconds"] = int(
            (stats.get("overall") or {}).get("totalReadTime") or 0
        )
        return dict(self.counts)

    def sync_periods(
        self,
        days: list[dict[str, Any]],
        related_timestamps: list[int] | None = None,
    ) -> dict[str, dict[str, str]]:
        maps = {"day": {}, "week": {}, "month": {}, "year": {}}
        durations = defaultdict(int)
        rows_by_timestamp = {
            int(row["timestamp"]): int(row.get("duration") or 0) for row in days
        }
        for timestamp in related_timestamps or []:
            rows_by_timestamp.setdefault(int(timestamp), 0)
        period_rows = [
            {"timestamp": timestamp, "duration": duration}
            for timestamp, duration in sorted(rows_by_timestamp.items())
        ]
        for row in period_rows:
            keys = period_keys(row["timestamp"])
            for kind in maps:
                durations[(kind, keys[kind])] += int(row["duration"])
        db_names = {"day": "日", "week": "周", "month": "月", "year": "年"}
        for (kind, key), duration in sorted(durations.items()):
            if kind == "year":
                start = date(int(key), 1, 1)
            elif kind == "month":
                year, month = map(int, key.split("-"))
                start = date(year, month, 1)
            else:
                start = date.fromisoformat(key)
            if kind == "week":
                end = start + timedelta(days=6)
            elif kind == "month":
                next_month = date(
                    start.year + (start.month == 12),
                    1 if start.month == 12 else start.month + 1,
                    1,
                )
                end = next_month - timedelta(days=1)
            elif kind == "year":
                end = date(start.year, 12, 31)
            else:
                end = start
            raw = {
                self.notion.titles[db_names[kind]]: key,
                "日期": {
                    "start": start.isoformat(),
                    "end": end.isoformat() if end != start else None,
                },
                "时长": duration,
            }
            if kind == "day":
                timestamp = next(
                    row["timestamp"]
                    for row in period_rows
                    if period_keys(row["timestamp"])["day"] == key
                )
                raw["时间戳"] = timestamp
            page_id = self.notion.upsert(
                db_names[kind],
                self.notion.titles[db_names[kind]],
                key,
                raw,
                TARGET_ICON,
            )
            maps[kind][key] = page_id
            self.counts[db_names[kind]] += 1
        for row in period_rows:
            keys = period_keys(row["timestamp"])
            day_id = maps["day"][keys["day"]]
            raw = {
                "年": [maps["year"][keys["year"]]],
                "月": [maps["month"][keys["month"]]],
                "周": [maps["week"][keys["week"]]],
            }
            self.notion.request(
                f"pages/{day_id}",
                "PATCH",
                {"properties": self.notion.properties("日", raw)},
            )
        return maps

    def sync_people_and_categories(self, entries, bundles):
        author_names, category_names = set(), set()
        for entry in entries:
            author_names.update(filter(None, [str(entry.get("author") or "").strip()]))
            category_names.update(filter(None, [entry.get("category")]))
        for bundle in bundles.values():
            info = bundle["info"]
            author_names.update(filter(None, [str(info.get("author") or "").strip()]))
            categories = info.get("categories") or []
            category_names.update(
                (item.get("title") if isinstance(item, dict) else item)
                for item in categories
            )
            category_names.update(filter(None, [info.get("category")]))
        authors = {
            name: self.notion.upsert(
                "作者",
                self.notion.titles["作者"],
                name,
                {self.notion.titles["作者"]: name},
                USER_ICON,
            )
            for name in sorted(filter(None, author_names))
        }
        categories = {
            name: self.notion.upsert(
                "分类",
                self.notion.titles["分类"],
                name,
                {self.notion.titles["分类"]: name},
                TAG_ICON,
            )
            for name in sorted(filter(None, category_names))
        }
        self.counts["作者"], self.counts["分类"] = len(authors), len(categories)
        return authors, categories

    def sync_books(
        self, entries, bundles, authors, categories, periods, changed_ids, existing
    ):
        result = {}
        for book_id, entry in entries.items():
            if book_id not in changed_ids and book_id in existing:
                result[book_id] = existing[book_id]["page_id"]
                continue
            bundle = bundles.get(book_id, {})
            info, progress = bundle.get("info", {}), bundle.get("progress", {})
            author = info.get("author") or entry.get("author") or ""
            cats = info.get("categories") or []
            cat_names = [(x.get("title") if isinstance(x, dict) else x) for x in cats]
            cat_names += [info.get("category") or entry.get("category")]
            timestamp = (
                progress.get("updateTime")
                or entry.get("readUpdateTime")
                or entry.get("sort")
            )
            relations = period_keys(timestamp) if timestamp else {}
            chapter_uid = str(progress.get("chapterUid") or "")
            current_chapter = next(
                (
                    chapter.get("title")
                    for chapter in (bundle.get("chapters") or [])
                    if str(chapter.get("chapterUid") or "") == chapter_uid
                ),
                "",
            )
            content_type = {
                "book": "电子书",
                "album": "有声书",
                "mp": "文章收藏",
            }.get(entry.get("kind"), "电子书")
            publish_time = info.get("publishTime")
            publish_date = str(publish_time)[:10] if publish_time else None
            raw = {
                self.notion.titles["书架"]: info.get("title")
                or entry.get("title")
                or book_id,
                "BookId": book_id,
                "ISBN": info.get("isbn") or "",
                "Sort": entry.get("sort") or timestamp or 0,
                "评分": info.get("newRating") or 0,
                "评分人数": info.get("newRatingCount") or 0,
                "链接": info.get("deepLink") or entry.get("deepLink"),
                "简介": info.get("intro") or entry.get("intro") or "",
                "出版社": info.get("publisher") or "",
                "出版日期": publish_date,
                "字数": info.get("wordCount") or 0,
                "译者": info.get("translator") or "",
                "内容类型": content_type,
                "当前章节": current_chapter,
                "听书时长": progress.get("ttsTime") or 0,
                "私密阅读": bool(entry.get("secret")),
                "置顶": bool(entry.get("isTop")),
                "有声书集数": entry.get("trackCount") or 0,
                "完结状态": entry.get("finishStatus") or "",
                "同步版本": SYNC_VERSION,
                "作者": [authors[author]] if author in authors else [],
                "分类": [categories[name] for name in cat_names if name in categories],
                # Shelf/update timestamps only prove that an item was added or
                # changed. They do not prove that the user actually read it.
                # Apply the same progress-based rule to books, albums and
                # article collections so untouched items appear under 想读.
                "阅读状态": progress_status(progress),
                # /book/getprogress exposes the accumulated text-reading duration
                # as readingTime (seconds). recordReadingTime is a different metric
                # and is commonly zero even for books with substantial progress.
                "阅读时长": progress.get("readingTime")
                or progress.get("recordReadingTime")
                or 0,
                "阅读进度": int(progress.get("progress") or 0) / 100,
                "开始阅读时间": iso_date(
                    progress.get("startReadingTime") or progress.get("beginReadingDate")
                ),
                "最后阅读时间": iso_date(timestamp),
                "时间": iso_date(progress.get("finishTime") or timestamp),
            }
            for kind, prop in (
                ("day", "日"),
                ("week", "周"),
                ("month", "月"),
                ("year", "年"),
            ):
                if relations.get(kind) in periods[kind]:
                    raw[prop] = [periods[kind][relations[kind]]]
            cover = info.get("cover") or entry.get("cover")
            result[book_id] = self.notion.upsert(
                "书架", "BookId", book_id, raw, cover or BOOK_ICON, cover
            )
            self.counts["书架"] += 1
        return result

    def dated_relations(self, timestamp, book_id, books, periods):
        raw = {"书籍": [books[book_id]]} if book_id in books else {}
        if timestamp:
            keys = period_keys(timestamp)
            for kind, prop in (
                ("day", "日"),
                ("week", "周"),
                ("month", "月"),
                ("year", "年"),
            ):
                if keys[kind] in periods[kind]:
                    raw[prop] = [periods[kind][keys[kind]]]
        return raw

    def sync_book_content(self, bundles, books, periods):
        for book_id, bundle in bundles.items():
            page_id = books.get(book_id)
            if not page_id:
                continue
            for database in ("章节", "划线", "笔记"):
                self.notion.archive_rows(database, ("书籍", page_id))
            for chapter in bundle["chapters"]:
                raw = {
                    self.notion.titles["章节"]: chapter.get("title")
                    or f"章节 {chapter.get('chapterIdx', '')}",
                    "chapterUid": chapter.get("chapterUid"),
                    "chapterIdx": chapter.get("chapterIdx"),
                    "level": chapter.get("level"),
                    "readAhead": chapter.get("readAhead"),
                    "updateTime": chapter.get("updateTime"),
                    "blockId": chapter.get("blockId"),
                    "书籍": [page_id],
                }
                self.notion.create("章节", raw, TAG_ICON)
                self.counts["章节"] += 1
            for mark in bundle["highlights"]:
                timestamp = mark.get("createTime")
                raw = {
                    self.notion.titles["划线"]: mark.get("markText") or "划线",
                    "bookId": book_id,
                    "bookmarkId": mark.get("bookmarkId"),
                    "blockId": mark.get("blockId"),
                    "range": mark.get("range"),
                    "chapterUid": mark.get("chapterUid"),
                    "bookVersion": mark.get("bookVersion"),
                    "colorStyle": mark.get("colorStyle"),
                    "type": mark.get("type"),
                    "style": mark.get("style"),
                    "Date": iso_datetime(timestamp),
                    **self.dated_relations(timestamp, book_id, books, periods),
                }
                self.notion.upsert(
                    "划线", "bookmarkId", mark.get("bookmarkId"), raw, BOOK_ICON
                )
                self.counts["划线"] += 1
            for review in bundle["reviews"]:
                timestamp = review.get("createTime")
                raw = {
                    self.notion.titles["笔记"]: review.get("content")
                    or review.get("abstract")
                    or "想法",
                    "bookId": book_id,
                    "reviewId": review.get("reviewId"),
                    "blockId": review.get("blockId"),
                    "range": review.get("range"),
                    "abstract": review.get("abstract"),
                    "chapterUid": review.get("chapterUid"),
                    "bookVersion": review.get("bookVersion"),
                    "type": review.get("type"),
                    "star": review.get("star"),
                    "Date": iso_datetime(timestamp),
                    **self.dated_relations(timestamp, book_id, books, periods),
                }
                self.notion.upsert(
                    "笔记", "reviewId", review.get("reviewId"), raw, TAG_ICON
                )
                self.counts["笔记"] += 1
            self.notion.replace_generated_book_content(
                page_id, self.book_content_blocks(bundle)
            )

    @staticmethod
    def book_content_blocks(bundle: dict[str, Any]) -> list[dict[str, Any]]:
        chapters = {
            str(chapter.get("chapterUid")): chapter
            for chapter in (bundle.get("chapters") or [])
        }
        grouped: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
        for mark in bundle.get("highlights") or []:
            grouped[str(mark.get("chapterUid") or "")].append((0, mark))
        for review in bundle.get("reviews") or []:
            grouped[str(review.get("chapterUid") or "")].append((1, review))
        if not grouped:
            return []

        def chapter_sort(uid: str) -> tuple[int, str]:
            chapter = chapters.get(uid) or {}
            return (int(chapter.get("chapterIdx") or 10**9), uid)

        blocks: list[dict[str, Any]] = [get_table_of_contents()]
        for uid in sorted(grouped, key=chapter_sort):
            chapter = chapters.get(uid) or {}
            title = chapter.get("title") or "其他笔记"
            blocks.append(get_heading(2, title))
            for kind, item in sorted(
                grouped[uid], key=lambda pair: int(pair[1].get("createTime") or 0)
            ):
                if kind == 0:
                    text = item.get("markText") or "划线"
                    blocks.append(get_callout(text, "〰️"))
                else:
                    abstract = item.get("abstract") or ""
                    content = item.get("content") or ""
                    text = "\n\n".join(part for part in (abstract, content) if part) or "想法"
                    blocks.append(get_callout(text, "💭"))
        return blocks

    def sync_reading_records(self, days, periods):
        database = next(
            (
                name
                for name in ("阅读记录2", "阅读记录", "阅读记录1")
                if name in self.notion.sources
            ),
            None,
        )
        if not database:
            return
        for row in days:
            keys = period_keys(row["timestamp"])
            raw = {
                self.notion.titles[database]: keys["day"],
                "日期": keys["day"],
                "Date": keys["day"],
                "时长": row["duration"],
                "时间戳": row["timestamp"],
            }
            self.notion.upsert(database, "时间戳", row["timestamp"], raw, TARGET_ICON)
            self.counts[database] += 1
