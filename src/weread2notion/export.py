from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .normalize import shelf_entries
from .weread import WeReadError


def export_weread(client, output_dir: str | Path, fmt: str = "json") -> dict[str, Any]:
    """Export current WeRead shelf data without writing to Notion."""
    if fmt not in {"json", "markdown"}:
        raise ValueError("export format must be json or markdown")
    root = Path(output_dir)
    if root.is_absolute() or ".." in root.parts:
        raise ValueError("output directory must be relative to the current directory")
    root.mkdir(parents=True, exist_ok=True)
    entries = shelf_entries(client.shelf())
    books = []
    failed = []
    for entry in entries:
        item: dict[str, Any] = {"entry": entry, "bundle": {}}
        # Only e-books have details, highlights and thoughts. Audiobooks and
        # the article collection are exported from their shelf entry alone.
        if entry.get("kind") == "book":
            try:
                item["bundle"] = client.book_bundle(entry["bookId"])
            except WeReadError as exc:
                # Keep exporting the rest of the shelf and report the book.
                item["error"] = str(exc)
                failed.append({"book_id": str(entry["bookId"]), "error": str(exc)})
        books.append(item)
    payload = {"books": books, "count": len(books)}
    (root / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if fmt == "markdown":
        books_dir = root / "books"
        books_dir.mkdir(exist_ok=True)
        used_names: set[str] = set()
        for item in books:
            entry, bundle = item["entry"], item["bundle"]
            title = str(entry.get("title") or entry.get("bookId") or "未命名")
            safe_title = "".join(c for c in title if c not in '\\/:*?"<>|')[:120]
            lines = [f"# {title}", "", str(bundle.get("info", {}).get("intro") or "")]
            for mark in bundle.get("highlights") or []:
                lines.extend(["", f"> {mark.get('markText') or mark.get('text') or ''}"])
            for note in bundle.get("reviews") or []:
                lines.extend(["", f"**笔记**：{note.get('content') or note.get('review') or ''}"])
            name = safe_title.strip() or "未命名"
            if name.casefold() in used_names:
                # Two shelf items share a title; do not overwrite the first.
                safe_id = "".join(
                    c for c in str(entry.get("bookId") or "") if c.isalnum()
                )
                name = f"{name}-{safe_id or len(used_names)}"
            used_names.add(name.casefold())
            (books_dir / f"{name}.md").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
    result: dict[str, Any] = {"output": str(root), "format": fmt, "books": len(books)}
    if failed:
        result["failed_books"] = failed
    return result
