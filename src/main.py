"""毎朝の新聞見出し収集パイプラインのオーケストレーション。"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from src.collectors.ceek_collector import build_newspaper_index, collect_ceek
from src.collectors.html_collector import collect_html
from src.collectors.robots_guard import RobotsDisallowedError
from src.collectors.rss_collector import collect_rss
from src.config_loader import ConfigError, load_aggregator_config, load_config
from src.models.article import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, Article
from src.outputs.csv_writer import (
    append_index_csv,
    build_daily_articles,
    write_archive_manifest,
    write_daily_csv,
    write_daily_summary,
    write_latest_csv,
    write_latest_summary,
)
from src.outputs.discord_sender import build_discord_payload, send_discord
from src.outputs.email_sender import render_email_html, send_email
from src.outputs.issue_notifier import (
    add_issue_comment,
    build_failure_issue,
    create_github_issue,
    find_open_issue_by_title,
    get_error_newspapers,
    should_notify,
)
from src.outputs.readme_writer import list_archive_dates, render_readme, write_readme
from src.processors.deduplicate import deduplicate
from src.processors.normalize import normalize_article
from src.processors.summarizer import SOURCE_UNAVAILABLE, build_summary

REQUIRED_EMAIL_ENV_VARS = (
    "MAIL_TO",
    "MAIL_FROM",
    "RESEND_API_KEY",
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


def collect_aggregators(
    aggregator_configs: list[dict],
    newspaper_configs: list[dict],
    collected_at: str,
    date: str,
) -> tuple[list[Article], list]:
    """アグリゲーターから記事を集め、(記事, 失敗一覧) を返す。

    **status=okのArticleしか返さない。** 失敗をArticleにしてしまうと、架空の新聞社名が
    紙別テーブルや取得失敗通知Issueへ混入するため(issue_notifierはnewspaper単位で集計する)。
    """
    index = build_newspaper_index(newspaper_configs)
    articles: list[Article] = []
    failures: list = []

    for config in aggregator_configs:
        name = config.get("name", "aggregator")
        try:
            if config["source_type"] == "ceek":
                result = collect_ceek(config, collected_at, date, newspaper_index=index)
            else:
                raise ValueError(f"未知のaggregatorのsource_typeです: {config['source_type']}")
        except Exception as exc:  # noqa: BLE001 - アグリゲーターの失敗を既存20紙に波及させない
            print(f"[ERROR] {name}: 収集に失敗しました: {exc}")
            continue

        articles.extend(result.articles)
        failures.extend(result.failures)

        for item in result.skipped:
            print(f"[SKIP] {name}: category={item.category_id} robots.txtにより取得しません ({item.reason})")
        for item in result.failures:
            print(f"[ERROR] {name}: category={item.category_id} 取得失敗 ({item.reason})")
        print(
            f"[SUMMARY] アグリゲータ {name}: 記事={len(result.articles)}件 "
            f"取得カテゴリ={','.join(result.fetched_categories) or '(なし)'} "
            f"失敗={len(result.failures)} スキップ={len(result.skipped)}"
        )

    return articles, failures


def _load_aggregator_configs_safely() -> list[dict]:
    try:
        return load_aggregator_config()
    except ConfigError as exc:
        # アグリゲーター設定の不備で既存20紙のパイプラインを止めない。
        print(f"[ERROR] アグリゲーター設定の読み込みに失敗しました(スキップします): {exc}")
        return []


def _build_summary_safely(articles: list[Article], date: str) -> tuple[str, str]:
    """build_summary自体が例外を握るが、想定外の例外にも備える二重防御。"""
    try:
        return build_summary(articles, date, api_key=os.environ.get("ANTHROPIC_API_KEY"))
    except Exception as exc:  # noqa: BLE001 - まとめ生成失敗を他チャネルに波及させない
        print(f"[ERROR] 本日のまとめの生成に失敗しました: {exc}")
        return "", SOURCE_UNAVAILABLE


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
    aggregator_configs = _load_aggregator_configs_safely()
    aggregator_articles, _aggregator_failures = collect_aggregators(
        aggregator_configs, configs, collected_at, resolved_date
    )
    # 各紙の自前フィードを先に置くことで、同じ記事がアグリゲーター経由でも来た場合に
    # 一次ソース側のsource_urlを持つ行が残る(deduplicateは先勝ち)。
    articles = deduplicate([normalize_article(a) for a in raw_articles + aggregator_articles])

    # 1日3回実行するため、その日の既存CSVとマージした集合を「本日の記事」として扱う。
    daily_articles = build_daily_articles(articles, resolved_date)

    try:
        write_daily_csv(daily_articles, resolved_date, merge_existing=False)
        write_latest_csv(daily_articles)
        ok, skipped, error = _count_by_status(daily_articles)
        append_index_csv(resolved_date, len(daily_articles), ok, skipped, error)
    except Exception as exc:  # noqa: BLE001 - CSV書き込み失敗時も後続チャネルの試行は続けたい
        print(f"[ERROR] CSV書き込みに失敗しました: {exc}")

    generated_at = now.strftime("%Y年%m月%d日 %H:%M")
    archive_dates = list_archive_dates()

    summary, summary_source = _build_summary_safely(daily_articles, resolved_date)

    try:
        write_daily_summary(summary, resolved_date, source=summary_source, generated_at=generated_at)
        write_latest_summary(summary, resolved_date, source=summary_source, generated_at=generated_at)
    except Exception as exc:  # noqa: BLE001 - まとめJSONの失敗が他チャネルを止めないようにする
        print(f"[ERROR] まとめJSONの書き込みに失敗しました: {exc}")

    try:
        write_archive_manifest(archive_dates)
    except Exception as exc:  # noqa: BLE001 - マニフェスト書き込み失敗が他チャネルを止めないようにする
        print(f"[ERROR] アーカイブ一覧(archive-index.json)の書き込みに失敗しました: {exc}")

    try:
        # 全てキーワード引数で渡す(位置引数だと引数追加時に静かにズレるため)。
        rendered_readme = render_readme(
            daily_articles,
            date=resolved_date,
            generated_at=generated_at,
            archive_dates=archive_dates,
            summary=summary,
        )
        write_readme(rendered_readme)
    except Exception as exc:  # noqa: BLE001 - README更新失敗が他チャネルを止めないようにする
        print(f"[ERROR] README更新に失敗しました: {exc}")

    time_label = now.strftime("%H:%M")
    _send_email_if_configured(daily_articles, resolved_date, generated_at, summary, time_label)
    _send_discord_if_configured(daily_articles, resolved_date, summary, time_label)
    _notify_failures_if_needed(articles, resolved_date)

    _print_summary(configs, daily_articles)


def _send_email_if_configured(
    articles: list[Article], date: str, generated_at: str, summary: str = "", time_label: str = ""
) -> None:
    missing = [key for key in REQUIRED_EMAIL_ENV_VARS if not os.environ.get(key)]
    if missing:
        print(f"[SKIP] メール配信をスキップしました(未設定の環境変数: {', '.join(missing)})")
        return

    try:
        html_body = render_email_html(articles, generated_at, summary=summary)
        # 1日3回配信するため件名に時刻を入れる。時刻がないと3通が同一件名になり、
        # Gmail等で1スレッドに畳まれて後の配信が埋もれる。
        subject = f"【ニュースインデックス】主要見出し｜{date}"
        if time_label:
            subject = f"{subject} {time_label}"
        send_email(
            subject=subject,
            html_body=html_body,
            mail_to=os.environ["MAIL_TO"],
            mail_from=os.environ["MAIL_FROM"],
            api_key=os.environ["RESEND_API_KEY"],
        )
        print("[OK] メールを送信しました")
    except Exception as exc:  # noqa: BLE001 - メール送信失敗が他チャネルを止めないようにする
        print(f"[ERROR] メール送信に失敗しました: {exc}")


def _send_discord_if_configured(
    articles: list[Article], date: str, summary: str = "", time_label: str = ""
) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[SKIP] Discord配信をスキップしました(DISCORD_WEBHOOK_URL未設定)")
        return

    try:
        payload = build_discord_payload(
            articles, date, REPO_README_URL, summary=summary, time_label=time_label
        )
        send_discord(payload, webhook_url)
        print("[OK] Discordへ投稿しました")
    except Exception as exc:  # noqa: BLE001 - Discord送信失敗が他チャネル/後続処理を止めないようにする
        print(f"[ERROR] Discord送信に失敗しました: {exc}")


def _notify_failures_if_needed(articles: list[Article], date: str) -> None:
    if not should_notify(articles):
        return

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    error_newspapers = get_error_newspapers(articles)

    if not token or not repo:
        print(
            "[SKIP] 取得失敗Issue登録をスキップしました"
            f"(GITHUB_TOKEN/GITHUB_REPOSITORY未設定、失敗紙: {', '.join(error_newspapers)})"
        )
        return

    try:
        title, body = build_failure_issue(articles, date)
        # 1日3回実行するため、同一原因で毎回起票しないよう既存のopen Issueを確認する。
        existing = find_open_issue_by_title(title, repo, token)
        if existing:
            add_issue_comment(existing["number"], body, repo, token)
            print(
                f"[OK] 既存の取得失敗Issue #{existing['number']} へコメントしました"
                f"(失敗紙: {', '.join(error_newspapers)})"
            )
            return
        create_github_issue(title, body, repo, token, labels=["bug", "auto-generated"])
        print(f"[OK] 取得失敗Issueを登録しました(失敗紙: {', '.join(error_newspapers)})")
    except Exception as exc:  # noqa: BLE001 - Issue登録失敗が他の後続処理を止めないようにする
        print(f"[ERROR] 取得失敗Issue登録に失敗しました: {exc}")


if __name__ == "__main__":
    run()
