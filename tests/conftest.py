"""テスト全体の共通設定。

tests/test_main_integration.py は main.run() を実際に呼ぶため、開発者の環境に
RESEND_API_KEY / DISCORD_WEBHOOK_URL / ANTHROPIC_API_KEY 等が設定されていると
pytest が本物のメール送信やWebhook投稿を行ってしまう。外部送信系の環境変数を
必ず未設定にしてからテストを走らせる。

個別に設定したいテスト(取得失敗Issue起票のテスト等)は、テスト本体で
monkeypatch.setenv すればそちらが優先される(fixtureはテスト本体より先に走るため)。
"""

from __future__ import annotations

import pytest

_OUTBOUND_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "RESEND_API_KEY",
    "MAIL_TO",
    "MAIL_FROM",
    "DISCORD_WEBHOOK_URL",
    "GITHUB_TOKEN",
    "GITHUB_REPOSITORY",
)


@pytest.fixture(autouse=True)
def isolate_outbound_env(monkeypatch):
    """テストが実ネットワークへ出ないよう、外部送信系の環境変数を必ず未設定にする。"""
    for key in _OUTBOUND_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
