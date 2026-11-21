from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ID_RE = re.compile(
    r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE,
)
DEFAULT_WEREAD_SKILL_VERSION = "1.0.6"


class ConfigError(RuntimeError):
    pass


def notion_id(value: str) -> str:
    match = ID_RE.search(value or "")
    if not match:
        raise ConfigError("NOTION_PAGE 必须是 Notion 页面链接或页面 ID")
    return match.group(1)


def env_value(name: str, default: str) -> str:
    # CI passes an unset secret or variable as an empty string. Treat that the
    # same as "not configured" instead of sending Notion an empty version or
    # failing to parse a number.
    return (os.getenv(name) or "").strip() or default


def env_number(name: str, default: str, kind: type):
    raw = env_value(name, default)
    try:
        return kind(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数字，当前值：{raw}") from exc


@dataclass(frozen=True)
class Settings:
    weread_api_key: str
    notion_token: str
    notion_page_id: str
    notion_version: str = "2026-03-11"
    skill_version: str = DEFAULT_WEREAD_SKILL_VERSION
    start_year: int = 2023
    backup_dir: Path = Path("backups")
    request_interval: float = 0.34

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        api_key = (os.getenv("WEREAD_API_KEY") or "").strip()
        token = (os.getenv("NOTION_TOKEN") or "").strip()
        page = (os.getenv("NOTION_PAGE") or "").strip()
        if not api_key:
            raise ConfigError("缺少 WEREAD_API_KEY")
        if not token:
            raise ConfigError("缺少 NOTION_TOKEN")
        if not page:
            raise ConfigError("缺少 NOTION_PAGE")
        return cls(
            weread_api_key=api_key,
            notion_token=token,
            notion_page_id=notion_id(page),
            notion_version=env_value("NOTION_VERSION", "2026-03-11"),
            skill_version=env_value(
                "WEREAD_SKILL_VERSION", DEFAULT_WEREAD_SKILL_VERSION
            ),
            start_year=env_number("START_YEAR", "2023", int),
            backup_dir=Path(env_value("BACKUP_DIR", "backups")),
            request_interval=env_number("NOTION_REQUEST_INTERVAL", "0.34", float),
        )
