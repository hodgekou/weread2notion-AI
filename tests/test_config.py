import pytest

from weread2notion.config import ConfigError, notion_id


def test_extract_notion_id_from_app_url():
    assert (
        notion_id("https://app.notion.com/p/wph/fd729affe5af83119383810f23b49175")
        == "fd729affe5af83119383810f23b49175"
    )


def test_invalid_notion_id():
    with pytest.raises(ConfigError):
        notion_id("not-a-notion-page")
