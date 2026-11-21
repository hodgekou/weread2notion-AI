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


@pytest.fixture
def required_env(monkeypatch):
    monkeypatch.setattr("weread2notion.config.load_dotenv", lambda: None)
    monkeypatch.setenv("WEREAD_API_KEY", "test-key")
    monkeypatch.setenv("NOTION_TOKEN", "test-token")
    monkeypatch.setenv("NOTION_PAGE", "0123456789abcdef0123456789abcdef")
    for name in (
        "NOTION_VERSION",
        "WEREAD_SKILL_VERSION",
        "START_YEAR",
        "BACKUP_DIR",
        "NOTION_REQUEST_INTERVAL",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_blank_optional_variables_use_defaults(required_env):
    # GitHub Actions passes an unset secret or variable as an empty string.
    for name in (
        "NOTION_VERSION",
        "WEREAD_SKILL_VERSION",
        "START_YEAR",
        "BACKUP_DIR",
        "NOTION_REQUEST_INTERVAL",
    ):
        required_env.setenv(name, "  ")

    assert Settings.from_env() == Settings(
        "test-key", "test-token", "0123456789abcdef0123456789abcdef"
    )


def test_optional_variables_can_be_overridden(required_env):
    required_env.setenv("START_YEAR", "2020")
    required_env.setenv("NOTION_REQUEST_INTERVAL", "0.5")
    required_env.setenv("NOTION_VERSION", "2025-09-03")

    settings = Settings.from_env()

    assert settings.start_year == 2020
    assert settings.request_interval == 0.5
    assert settings.notion_version == "2025-09-03"


@pytest.mark.parametrize("name", ["START_YEAR", "NOTION_REQUEST_INTERVAL"])
def test_non_numeric_variable_is_a_config_error(required_env, name):
    required_env.setenv(name, "abc")
    with pytest.raises(ConfigError, match=name):
        Settings.from_env()


@pytest.mark.parametrize("name", ["WEREAD_API_KEY", "NOTION_TOKEN", "NOTION_PAGE"])
def test_missing_required_variable_is_a_config_error(required_env, name):
    required_env.setenv(name, " ")
    with pytest.raises(ConfigError, match=name):
        Settings.from_env()
