"""毎朝の新聞見出し収集パイプラインのオーケストレーション。"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from src.collectors.html_collector import collect_html
from src.collectors.robots_guard import RobotsDisallowedError
from src.collectors.rss_collector import collect_rss
from src.config_loader import ConfigError, load_config
from src.models.article import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, Article
from src.outputs.csv_writer import append_index_csv, write_daily_csv, write_latest_csv
from src.outputs.discord_sender import build_discord_payload, send_discord
from src.outputs.email_sender import render_email_html, send_email
from src.outputs.readme_writer import list_archive_dates, render_readme, write_readme
from src.processors.deduplicate import deduplicate
from src.processors.normalize import normalize_article

REQUIRED_EMAIL_ENV_VARS = (
    "MAIL_TO",
    "MAIL_FROM",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
)
REPO_README_URL = "https://github.com/groundcobra009/japan-news-frontpage-index"

JST = timezone(timedelta(hours=9))


def _make_skipped_article(newspaper_config: dict, collected_at: str, date: str, reason: str) -> Article:
    return Article(
        date=date,
        collected_at=collected_at,
        category=newspaper_config.get("category", ""),
        region=newspaper_config.get("region", ""),
        newspaper=newspaper_config["name"],
        headline="",
        url="",
        source_url=newspaper_config.get("top_page_url") or newspaper_config.get("rss_url", ""),
        status=STATUS_SKIPPED,
        error_message=reason,
    )


def _make_error_article(newspaper_config: dict, collected_at: str, date: str, error_message: str) -> Article:
    return Article(
        date=date,
        collected_at=collected_at,
        category=newspaper_config.get("category", ""),
        region=newspaper_config.get("region", ""),
        newspaper=newspaper_config["name"],
        headline="",
        url="",
        source_url=newspaper_config.get("top_page_url") or newspaper_config.get("rss_url", ""),
        status=STATUS_ERROR,
        error_message=error_message,
    )


def collect_all(newspaper_configs: list[dict], collected_at: str, date: str) -> list[Article]:
    """新聞社ごとに個別にtry/exceptし、1紙の失敗が他紙に波及しないようにする。"""
    articles: list[Article] = []
    for config in newspaper_configs:
        source_type = config["source_type"]
        try:
            if source_type == "manual":
                articles.append(
                    _make_skipped_article(
                        config, collected_at, date, reason=config.get("reason", "manual source, not scraped")
                    )
                )
            elif source_type == "rss":
                articles.extend(collect_rss(config, collected_at, date))
            elif source_type == "html":
                try:
                    articles.extend(collect_html(config, collected_at, date))
                except RobotsDisallowedError as exc:
                    articles.append(_make_skipped_article(config, collected_at, date, reason=str(exc)))
            else:
                raise ValueError(f"未知のsource_typeです: {source_type}")
        except Exception as exc:  # noqa: BLE001 - 1紙の失敗を他紙に波及させないため意図的に広くcatchする
            articles.append(_make_error_article(config, collected_at, date, error_message=str(exc)))
    return articles


def _count_by_status(articles: list[Article]) -> tuple[int, int, int]:
    ok = sum(1 for a in articles if a.status == STATUS_OK)
    skipped = sum(1 for a in articles if a.status == STATUS_SKIPPED)
    error = sum(1 for a in articles if a.status == STATUS_ERROR)
    return ok, skipped, error


def _print_summary(newspaper_configs: list[dict], articles: list[Article]) -> None:
    ok, skipped, error = _count_by_status(articles)
    print(f"[SUMMARY] 記事数={len(articles)} ok={ok} skipped={skipped} error={error}")
    by_newspaper: dict[str, list[Article]] = {}
    for a in articles:
        by_newspaper.setdefault(a.newspaper, []).append(a)
    for config in newspaper_configs:
        name = config["name"]
        rows = by_newspaper.get(name, [])
        statuses = ",".join(sorted({r.status for r in rows})) or "(no data)"
        print(f"  - {name}: {len(rows)}件 status={statuses}")


def run(date: str | None = None) -> None:
    now = datetime.now(JST)
    collected_at = now.isoformat()
    resolved_date = date or now.strftime("%Y-%m-%d")

    try:
        configs = load_config()
    except ConfigError as exc:
        print(f"[FATAL] 設定ファイルの読み込みに失敗しました: {exc}")
        sys.exit(1)

    raw_articles = collect_all(configs, collected_at, resolved_date)
    articles = deduplicate([normalize_article(a) for a in raw_articles])

    try:
        write_daily_csv(articles, resolved_date)
        write_latest_csv(articles)
        ok, skipped, error = _count_by_status(articles)
        append_index_csv(resolved_date, len(articles), ok, skipped, error)
    except Exception as exc:  # noqa: BLE001 - CSV書き込み失敗時も後続チャネルの試行は続けたい
        print(f"[ERROR] CSV書き込みに失敗しました: {exc}")

    generated_at = now.strftime("%Y年%m月%d日 %H:%M")

    try:
        archive_dates = list_archive_dates()
        rendered_readme = render_readme(articles, resolved_date, generated_at, archive_dates)
        write_readme(rendered_readme)
    except Exception as exc:  # noqa: BLE001 - README更新失敗が他チャネルを止めないようにする
        print(f"[ERROR] README更新に失敗しました: {exc}")

    _send_email_if_configured(articles, resolved_date, generated_at)
    _send_discord_if_configured(articles, resolved_date)

    _print_summary(configs, articles)


def _send_email_if_configured(articles: list[Article], date: str, generated_at: str) -> None:
    missing = [key for key in REQUIRED_EMAIL_ENV_VARS if not os.environ.get(key)]
    if missing:
        print(f"[SKIP] メール配信をスキップしました(未設定の環境変数: {', '.join(missing)})")
        return

    try:
        html_body = render_email_html(articles, generated_at)
        subject = f"【朝刊インデックス】全国紙の主要見出し｜{date}"
        send_email(
            subject=subject,
            html_body=html_body,
            mail_to=os.environ["MAIL_TO"],
            mail_from=os.environ["MAIL_FROM"],
            smtp_host=os.environ["SMTP_HOST"],
            smtp_port=int(os.environ["SMTP_PORT"]),
            smtp_username=os.environ["SMTP_USERNAME"],
            smtp_password=os.environ["SMTP_PASSWORD"],
        )
        print("[OK] メールを送信しました")
    except Exception as exc:  # noqa: BLE001 - メール送信失敗が他チャネルを止めないようにする
        print(f"[ERROR] メール送信に失敗しました: {exc}")


def _send_discord_if_configured(articles: list[Article], date: str) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[SKIP] Discord配信をスキップしました(DISCORD_WEBHOOK_URL未設定)")
        return

    try:
        payload = build_discord_payload(articles, date, REPO_README_URL)
        send_discord(payload, webhook_url)
        print("[OK] Discordへ投稿しました")
    except Exception as exc:  # noqa: BLE001 - Discord送信失敗が他チャネル/後続処理を止めないようにする
        print(f"[ERROR] Discord送信に失敗しました: {exc}")


if __name__ == "__main__":
    run()
