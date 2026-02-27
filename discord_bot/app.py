"""
Discord Slash Command Bot — 在庫監視 一時停止 / 再開
=====================================================
コマンド:
  /pause  → GitHub Repository Variable STOCK_CHECK_PAUSED を "true" にセット
  /resume → GitHub Repository Variable STOCK_CHECK_PAUSED を "false" にセット
  /status → 現在の監視状態を表示

動作方式:
  Discord Interactions HTTP endpoint（WebSocket 不要）
  → Render.com の Free プランで無料ホスト可能

環境変数（Render で設定）:
  DISCORD_PUBLIC_KEY   : Discord アプリの Public Key
  DISCORD_BOT_TOKEN    : Discord Bot Token（不要な場合もあるが念のため）
  GITHUB_TOKEN         : GitHub Personal Access Token（repo, workflow スコープ）
  GITHUB_REPO          : "ユーザー名/apple-stock-checker" 形式
"""

import os
import json
import requests
from flask import Flask, request, jsonify, abort
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# ============================================================
# 設定
# ============================================================

app = Flask(__name__)

DISCORD_PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPO"]  # "user/apple-stock-checker"

# 起動時に一度だけ計算（リクエストごとの再生成を避ける）
DISCORD_VERIFY_KEY = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))

GITHUB_VARIABLE_NAME = "STOCK_CHECK_PAUSED"
GITHUB_API_BASE      = f"https://api.github.com/repos/{GITHUB_REPO}"

GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ============================================================
# Discord リクエスト検証
# ============================================================

def verify_discord_signature():
    """署名検証に失敗した場合は 401 を返す"""
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp  = request.headers.get("X-Signature-Timestamp", "")
    body       = request.data.decode("utf-8")

    try:
        DISCORD_VERIFY_KEY.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except (BadSignatureError, Exception):
        abort(401)

# ============================================================
# GitHub Repository Variable 操作
# ============================================================

def get_paused_value() -> str | None:
    url = f"{GITHUB_API_BASE}/actions/variables/{GITHUB_VARIABLE_NAME}"
    r = requests.get(url, headers=GH_HEADERS, timeout=10)
    if r.status_code == 200:
        return r.json().get("value", "false")
    return None


def set_paused_value(value: str) -> bool:
    """STOCK_CHECK_PAUSED を value に設定（変数が無ければ作成）"""
    url_var  = f"{GITHUB_API_BASE}/actions/variables/{GITHUB_VARIABLE_NAME}"
    url_list = f"{GITHUB_API_BASE}/actions/variables"
    payload  = {"name": GITHUB_VARIABLE_NAME, "value": value}

    # PATCH（更新）
    r = requests.patch(url_var, json=payload, headers=GH_HEADERS, timeout=10)
    if r.status_code == 204:
        return True

    # 変数が存在しない → POST（作成）
    if r.status_code == 404:
        r2 = requests.post(url_list, json=payload, headers=GH_HEADERS, timeout=10)
        return r2.status_code == 201

    return False

# ============================================================
# Discord Embed ヘルパー
# ============================================================

def ephemeral_message(content: str, color: int = 0x5865F2) -> dict:
    """スラッシュコマンドへの返答（送信者にのみ見える）"""
    return {
        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "embeds": [
                {
                    "description": content,
                    "color": color,
                }
            ],
            "flags": 64,  # EPHEMERAL（自分にだけ見える）
        },
    }

# ============================================================
# メインエンドポイント
# ============================================================

@app.route("/discord", methods=["POST"])
def discord_interactions():
    verify_discord_signature()

    body = request.json
    interaction_type = body.get("type")

    # ── PING（Discord からの疎通確認）──────────────────────
    if interaction_type == 1:
        return jsonify({"type": 1})

    # ── Slash Command ──────────────────────────────────────
    if interaction_type == 2:
        command = body["data"]["name"]

        if command == "pause":
            ok = set_paused_value("true")
            if ok:
                return jsonify(ephemeral_message(
                    "⏸️ **在庫監視を一時停止しました**\n"
                    "再開するには `/resume` を実行してください。",
                    color=0xFFA500,
                ))
            else:
                return jsonify(ephemeral_message(
                    "❌ 一時停止に失敗しました（GitHub API エラー）",
                    color=0xFF0000,
                ))

        elif command == "resume":
            ok = set_paused_value("false")
            if ok:
                return jsonify(ephemeral_message(
                    "▶️ **在庫監視を再開しました**\n"
                    "次のスケジュール実行からチェックが再開されます。",
                    color=0x00C853,
                ))
            else:
                return jsonify(ephemeral_message(
                    "❌ 再開に失敗しました（GitHub API エラー）",
                    color=0xFF0000,
                ))

        elif command == "status":
            value = get_paused_value()
            if value is None:
                return jsonify(ephemeral_message(
                    "⚠️ 状態の取得に失敗しました（GitHub API エラー）",
                    color=0xFFA500,
                ))
            if value == "true":
                return jsonify(ephemeral_message(
                    "⏸️ **現在：一時停止中**\n`/resume` で再開できます。",
                    color=0xFFA500,
                ))
            else:
                return jsonify(ephemeral_message(
                    "✅ **現在：監視稼働中**\n`/pause` で一時停止できます。",
                    color=0x00C853,
                ))

    return jsonify({"type": 1})


# ============================================================
# ヘルスチェック（Render の死活監視用）
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
