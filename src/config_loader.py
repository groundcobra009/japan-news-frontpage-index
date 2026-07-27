"""config/newspapers.yml と config/aggregators.yml の読み込み。"""

from __future__ import annotations

import os

import yaml

DEFAULT_CONFIG_PATH = "config/newspapers.yml"
DEFAULT_AGGREGATOR_CONFIG_PATH = "config/aggregators.yml"

VALID_SOURCE_TYPES = {"rss", "html", "manual"}
VALID_AGGREGATOR_SOURCE_TYPES = {"ceek"}


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


def load_aggregator_config(path: str = DEFAULT_AGGREGATOR_CONFIG_PATH) -> list[dict]:
    """アグリゲーター設定のリストを返す。enabled=falseは除外する。

    ファイルが存在しない場合は空リストを返す(機能OFF扱い)。ConfigErrorにしないのは、
    main.run()がConfigErrorでsys.exit(1)するため、アグリゲーター設定の不在が
    既存20紙のパイプラインを止めてしまわないようにするため。
    """
    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as exc:
        raise ConfigError(f"設定ファイルを読み込めません: {path} ({exc})") from exc

    if not data or "aggregators" not in data:
        raise ConfigError(f"設定ファイルに 'aggregators' キーがありません: {path}")

    result = []
    for entry in data["aggregators"]:
        _validate_aggregator_entry(entry)
        if entry.get("enabled", True):
            result.append(entry)
    return result


def _validate_aggregator_entry(entry: dict) -> None:
    missing = [k for k in ("name", "key", "source_type") if k not in entry]
    if missing:
        raise ConfigError(f"アグリゲーター設定に必須キーがありません: {missing} ({entry})")
    if entry["source_type"] not in VALID_AGGREGATOR_SOURCE_TYPES:
        raise ConfigError(f"不正なaggregatorのsource_type: {entry['source_type']} ({entry['name']})")
    if not entry.get("feed_url_template"):
        raise ConfigError(f"feed_url_templateが必要です: {entry['name']}")
    if not entry.get("categories"):
        raise ConfigError(f"categoriesが1件以上必要です: {entry['name']}")
    if float(entry.get("crawl_delay_seconds", 0)) < 0:
        raise ConfigError(f"crawl_delay_secondsは0以上である必要があります: {entry['name']}")


def _validate_entry(entry: dict) -> None:
    missing = [k for k in ("name", "key", "source_type") if k not in entry]
    if missing:
        raise ConfigError(f"設定エントリに必須キーがありません: {missing} ({entry})")
    if entry["source_type"] not in VALID_SOURCE_TYPES:
        raise ConfigError(
            f"不正なsource_type: {entry['source_type']} ({entry['name']})"
        )
