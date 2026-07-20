from __future__ import annotations

import argparse
import json

from .config import ConfigError, Settings
from .notion import NotionWorkspace
from .sync import Synchronizer
from .weread import WeReadClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weread2notion")
    sub = parser.add_subparsers(dest="command")
    sync = sub.add_parser("sync", help="同步微信读书数据，保留 Notion 页面结构")
    sync.add_argument("--full", action="store_true", help="备份并重建全部数据库行")
    sync.add_argument(
        "--dry-run", action="store_true", help="只读取微信数据并显示同步计划"
    )
    sub.add_parser("check", help="检查模板数据库与属性")
    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    command = args.command or "sync"
    try:
        settings = Settings.from_env()
        weread = WeReadClient(settings.weread_api_key, settings.skill_version)
        if command == "sync" and getattr(args, "dry_run", False):
            result = Synchronizer(weread, None, settings.start_year, dry_run=True).run()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        notion = NotionWorkspace(
            settings.notion_token,
            settings.notion_page_id,
            settings.notion_version,
            settings.request_interval,
        ).discover()
        if command == "check":
            print(
                json.dumps(
                    {"databases": notion.databases, "schemas": notion.schemas},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        result = Synchronizer(
            weread,
            notion,
            settings.start_year,
            dry_run=False,
        ).run(
            full=getattr(args, "full", False),
            backup_dir=settings.backup_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except ConfigError as exc:
        raise SystemExit(f"配置错误：{exc}") from exc


if __name__ == "__main__":
    main()
