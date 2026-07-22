import pytest

from src.config_loader import ConfigError, load_config

VALID_YAML = """
newspapers:
  - name: "朝日新聞"
    key: "asahi"
    source_type: "rss"
    rss_url: "https://www.asahi.com/rss/asahi/newsheadlines.rdf"
    enabled: true
  - name: "読売新聞"
    key: "yomiuri"
    source_type: "manual"
    enabled: true
  - name: "無効紙"
    key: "disabled"
    source_type: "html"
    enabled: false
"""


def test_load_config_filters_disabled_entries(tmp_path):
    config_path = tmp_path / "newspapers.yml"
    config_path.write_text(VALID_YAML, encoding="utf-8")

    result = load_config(str(config_path))

    keys = [entry["key"] for entry in result]
    assert keys == ["asahi", "yomiuri"]


def test_load_config_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "does_not_exist.yml"))


def test_load_config_missing_newspapers_key_raises(tmp_path):
    config_path = tmp_path / "bad.yml"
    config_path.write_text("something_else: []", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(config_path))


def test_load_config_invalid_source_type_raises(tmp_path):
    config_path = tmp_path / "bad.yml"
    config_path.write_text(
        """
newspapers:
  - name: "テスト"
    key: "test"
    source_type: "invalid"
    enabled: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(str(config_path))


def test_real_config_file_loads_national_and_local_newspapers():
    result = load_config("config/newspapers.yml")
    assert len(result) == 20

    national_keys = {entry["key"] for entry in result if entry["category"] == "全国紙"}
    assert national_keys == {
        "yomiuri",
        "asahi",
        "mainichi",
        "nikkei",
        "sankei",
        "tokyo",
        "chunichi",
    }

    local_keys = {entry["key"] for entry in result if entry["category"] == "地方紙"}
    assert local_keys == {
        "hokkaido",
        "kahoku",
        "niigata",
        "shinmai",
        "shizuoka",
        "kyoto",
        "kobe",
        "chugoku",
        "nishinippon",
        "kumanichi",
        "minaminippon",
        "ryukyushimpo",
        "okinawatimes",
    }
