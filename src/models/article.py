"""Article: 収集した1記事分の情報を表す共通データ型。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"

CSV_FIELDNAMES = [
    "date",
    "collected_at",
    "category",
    "region",
    "newspaper",
    "headline",
    "url",
    "source_url",
    "status",
    "error_message",
    "topic",
]


@dataclass
class Article:
    date: str
    collected_at: str
    category: str
    region: str
    newspaper: str
    headline: str
    url: str
    source_url: str
    status: str
    error_message: str = field(default="")
    topic: str = field(default="")

    def dedup_key(self) -> str:
        """同一新聞社内での重複判定キー。正規化済みURLを優先し、無ければ正規化済み見出しを使う。"""
        normalized_url = _normalize_url_for_key(self.url)
        if normalized_url:
            return f"{self.newspaper}::url::{normalized_url}"
        normalized_headline = _normalize_headline_for_key(self.headline)
        return f"{self.newspaper}::headline::{normalized_headline}"

    def to_csv_row(self) -> dict:
        return asdict(self)


def _normalize_url_for_key(raw_url: str) -> str:
    if not raw_url:
        return ""
    parts = urlsplit(raw_url)
    if not parts.netloc:
        return ""
    path = parts.path.rstrip("/")
    return f"{parts.netloc}{path}"


def _normalize_headline_for_key(raw_headline: str) -> str:
    if not raw_headline:
        return ""
    collapsed = re.sub(r"\s+", "", raw_headline)
    return collapsed.lower()
