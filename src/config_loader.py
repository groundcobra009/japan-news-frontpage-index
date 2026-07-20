"""config/newspapers.yml の読み込み。"""

from __future__ import annotations

import yaml

DEFAULT_CONFIG_PATH = "config/newspapers.yml"

VALID_SOURCE_TYPES = {"rss", "html", "manual"}


class ConfigError(Exception):
    """設定ファイルの読み込み・検証に失敗した場合に送出。"""


def load_config(path: str = DEFAULT_CONFIG_PATH) -> list[dict]:
    """新聞社設定のリストを返す。enabled=falseの紙は除外する。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as exc:
        raise ConfigError(f"設定ファイルを読み込めません: {path} ({exc})") from exc

    if not data or "newspapers" not in data:
        raise ConfigError(f"設定ファイルに 'newspapers' キーがありません: {path}")

    newspapers = data["newspapers"]
    result = []
    for entry in newspapers:
        _validate_entry(entry)
        if entry.get("enabled", True):
            result.append(entry)
    return result


def _validate_entry(entry: dict) -> None:
    missing = [k for k in ("name", "key", "source_type") if k not in entry]
    if missing:
        raise ConfigError(f"設定エントリに必須キーがありません: {missing} ({entry})")
    if entry["source_type"] not in VALID_SOURCE_TYPES:
        raise ConfigError(
            f"不正なsource_type: {entry['source_type']} ({entry['name']})"
        )
