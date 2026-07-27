"""取得失敗(status=error)が一定紙数を超えた場合のGitHub Issue自動登録。

manual紙やrobots.txt Disallowによるskippedは想定内の挙動のため通知対象にせず、
実際の取得エラー(ネットワーク障害・パース失敗等)のみを対象とする。
"""

from __future__ import annotations

import requests

from src.models.article import STATUS_ERROR, Article

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_ERROR_THRESHOLD = 1
REQUEST_TIMEOUT_SECONDS = 10


def _group_by_newspaper(articles: list[Article]) -> dict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.newspaper, []).append(article)
    return grouped


def get_error_newspapers(articles: list[Article]) -> list[str]:
    """status=errorの記事を持つ新聞社名のリストを、出現順で返す。"""
    grouped = _group_by_newspaper(articles)
    return [name for name, rows in grouped.items() if any(a.status == STATUS_ERROR for a in rows)]


def should_notify(articles: list[Article], threshold: int = DEFAULT_ERROR_THRESHOLD) -> bool:
    return len(get_error_newspapers(articles)) >= threshold


def build_failure_issue(articles: list[Article], date: str) -> tuple[str, str]:
    """Issueのtitleとbodyを組み立てる(純粋関数)。"""
    grouped = _group_by_newspaper(articles)
    error_newspapers = get_error_newspapers(articles)

    title = f"【japan-news-frontpage-index】取得失敗通知: {date}"
    lines = [f"{date}の収集で以下の新聞社が取得エラーになりました。", ""]
    for name in error_newspapers:
        error_rows = [a for a in grouped[name] if a.status == STATUS_ERROR]
        message = error_rows[0].error_message if error_rows else "(詳細不明)"
        lines.append(f"- {name}: {message}")
    lines.append("")
    lines.append("data/latest.csv やActionsのログで詳細を確認してください。")
    body = "\n".join(lines)
    return title, body


def find_open_issue_by_title(title: str, repo: str, token: str) -> dict | None:
    """同じタイトルのopen Issueがあれば返す。無ければNone。

    1日3回実行するため、同一原因(例: 静岡新聞の405)で毎回起票すると
    Issueが際限なく溜まる。起票前に既存のopen Issueを確認する。
    """
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    response = requests.get(
        url,
        headers=headers,
        params={"state": "open", "per_page": 100},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    for issue in response.json():
        # pull_request キーを持つものはPRなので除外する。
        if "pull_request" in issue:
            continue
        if issue.get("title") == title:
            return issue
    return None


def add_issue_comment(issue_number: int, body: str, repo: str, token: str) -> dict:
    """既存Issueへコメントを追加する(重複起票の代わりに経過を残す)。"""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}/comments"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    response = requests.post(url, json={"body": body}, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def create_github_issue(title: str, body: str, repo: str, token: str, labels: list[str] | None = None) -> dict:
    """GitHub REST APIでIssueを作成する。呼び出し元main.pyでtry/exceptし、失敗しても他処理をブロックしない。"""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()
