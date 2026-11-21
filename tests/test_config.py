import pytest

from weread2notion.config import ConfigError, Settings, notion_id


def test_extract_notion_id_from_app_url():
    assert (
        notion_id("https://app.notion.com/p/wph/fd729affe5af83119383810f23b49175")
        == "fd729affe5af83119383810f23b49175"
    )


def test_invalid_notion_id():
    with pytest.raises(ConfigError):
        notion_id("not-a-notion-page")


def test_skill_version_defaults_to_current_gateway_version(monkeypatch):
    monkeypatch.setattr("weread2notion.config.load_dotenv", lambda: None)
    monkeypatch.setenv("WEREAD_API_KEY", "test-key")
    monkeypatch.setenv("NOTION_TOKEN", "test-token")
    monkeypatch.setenv("NOTION_PAGE", "https://www.notion.so/0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("WEREAD_SKILL_VERSION", raising=False)

    assert Settings.from_env().skill_version == "1.0.6"
    assert Settings("test-key", "test-token", "test-page").skill_version == "1.0.6"


def test_skill_version_can_be_overridden(monkeypatch):
    monkeypatch.setattr("weread2notion.config.load_dotenv", lambda: None)
    monkeypatch.setenv("WEREAD_API_KEY", "test-key")
    monkeypatch.setenv("NOTION_TOKEN", "test-token")
    monkeypatch.setenv("NOTION_PAGE", "https://www.notion.so/0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("WEREAD_SKILL_VERSION", "1.0.5")

    assert Settings.from_env().skill_version == "1.0.5"
