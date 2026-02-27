"""
Discord Slash Commands 登録スクリプト（初回1回だけ実行）
==========================================================
実行方法:
  DISCORD_BOT_TOKEN=xxx DISCORD_APP_ID=yyy python register_commands.py

登録するコマンド:
  /pause  - 在庫監視を一時停止
  /resume - 在庫監視を再開
  /status - 現在の監視状態を確認
"""

import os
import sys
import requests

TOKEN  = os.environ.get("DISCORD_BOT_TOKEN")
APP_ID = os.environ.get("DISCORD_APP_ID")

if not TOKEN or not APP_ID:
    print("❌ 環境変数 DISCORD_BOT_TOKEN と DISCORD_APP_ID を設定してください")
    sys.exit(1)

URL = f"https://discord.com/api/v10/applications/{APP_ID}/commands"

COMMANDS = [
    {
        "name": "pause",
        "description": "Apple 整備済製品の在庫監視を一時停止する",
        "default_member_permissions": None,  # 全員使用可
    },
    {
        "name": "resume",
        "description": "Apple 整備済製品の在庫監視を再開する",
        "default_member_permissions": None,
    },
    {
        "name": "status",
        "description": "現在の在庫監視の稼働状況を確認する",
        "default_member_permissions": None,
    },
]

headers = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json",
}

print(f"🔧 コマンドを登録します（Application ID: {APP_ID}）")

for cmd in COMMANDS:
    r = requests.post(URL, json=cmd, headers=headers)
    if r.status_code in (200, 201):
        print(f"  ✅ /{cmd['name']} 登録成功")
    else:
        print(f"  ❌ /{cmd['name']} 失敗: {r.status_code} {r.text}")

print("\n✔ 完了。Discord サーバーで /<コマンド名> が使えるようになります。")
print("  （反映まで最大1時間かかる場合があります）")
