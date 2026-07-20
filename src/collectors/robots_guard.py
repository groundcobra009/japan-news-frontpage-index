"""robots.txtに基づくアクセス許可判定。

HTML収集を行う前に必ずこのモジュールを経由し、Disallowされたパスへは
アクセスしない。robots.txtの取得自体に失敗した場合もフェイルセーフとして
「Disallow」扱い(is_allowed=False)にする。
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser


class RobotsDisallowedError(Exception):
    """指定URL/UAがrobots.txtでDisallowされている場合に送出。"""


def _derive_robots_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


@lru_cache(maxsize=32)
def _fetch_robots_parser(robots_txt_url: str) -> RobotFileParser:
    """robots.txtを取得してパースする。プロセス内のみキャッシュし、実行をまたいだ
    永続キャッシュは行わない(cronの1実行ごとに使い捨てのプロセスなので、常に最新の
    robots.txtを見る)。"""
    parser = RobotFileParser()
    parser.set_url(robots_txt_url)
    parser.read()
    return parser


def is_allowed(url: str, user_agent: str, robots_txt_url: str | None = None) -> bool:
    """True: アクセス許可。False: Disallow、またはrobots.txt取得失敗(フェイルセーフ)。"""
    try:
        parser = _fetch_robots_parser(robots_txt_url or _derive_robots_url(url))
        return parser.can_fetch(user_agent, url)
    except Exception:
        return False


def assert_allowed(url: str, user_agent: str, robots_txt_url: str | None = None) -> None:
    """Disallow(または取得失敗)の場合 RobotsDisallowedError を送出する。"""
    if not is_allowed(url, user_agent, robots_txt_url):
        raise RobotsDisallowedError(
            f"robots.txtによりアクセスが許可されていません: {url} (UA={user_agent})"
        )
