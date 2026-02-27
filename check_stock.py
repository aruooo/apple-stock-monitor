"""
Apple 整備済製品 在庫チェッカー
================================
監視対象: iPhone 16 Pro Max 256GB (SIMフリー) 整備済製品 4色
通知方法: Discord Webhook → スマホ（Discord アプリ）
一時停止: Discord で /pause / /resume コマンド → GitHub Variable 経由で制御

時間帯別チェック間隔（GitHub Actions cron）:
  UTC 05:00-09:55  →  JST 14:00-18:55  :  5分間隔
  UTC 12:00-14:00  →  JST 21:00-23:00  : 15分間隔
  UTC 15:00-18:00  →  JST 00:00-03:00  : 10分間隔
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# ============================================================
# 定数 / 設定
# ============================================================

JST = timezone(timedelta(hours=9))

PRODUCTS = [
    {
        "id": "FYWH3J",
        "name": "iPhone 16 Pro Max 256GB ホワイトチタニウム（SIMフリー）[整備済]",
        "url": "https://www.apple.com/jp/xc/product/FYWH3J/A",
        "emoji": "⬜",
    },
    {
        "id": "FYWJ3J",
        "name": "iPhone 16 Pro Max 256GB デザートチタニウム（SIMフリー）[整備済]",
        "url": "https://www.apple.com/jp/xc/product/FYWJ3J/A",
        "emoji": "🟨",
    },
    {
        "id": "FYWK3J",
        "name": "iPhone 16 Pro Max 256GB ナチュラルチタニウム（SIMフリー）[整備済]",
        "url": "https://www.apple.com/jp/xc/product/FYWK3J/A",
        "emoji": "🟫",
    },
    {
        "id": "FYWG3J",
        "name": "iPhone 16 Pro Max 256GB ブラックチタニウム（SIMフリー）[整備済]",
        "url": "https://www.apple.com/jp/xc/product/FYWG3J/A",
        "emoji": "⬛",
    },
]

STATE_FILE = "stock_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

IN_STOCK_KEYWORDS = [
    "カートに入れる",
    "今すぐ購入",
    "add-to-cart",
    '"availability":"InStock"',
    '"availability": "InStock"',
]

OUT_OF_STOCK_KEYWORDS = [
    "現在ご注文いただけません",
    "在庫がありません",
    "売り切れ",
    '"availability":"OutOfStock"',
    '"availability": "OutOfStock"',
]

# ============================================================
# 時刻ユーティリティ
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def now_jst() -> datetime:
    return datetime.now(JST)

def time_label() -> str:
    """ログ表示用（UTC / JST 両記載）"""
    u = now_utc()
    j = now_jst()
    return (
        f"UTC {u.strftime('%Y-%m-%d %H:%M:%S')} "
        f"/ JST {j.strftime('%Y-%m-%d %H:%M:%S')}"
    )

# ============================================================
# 一時停止チェック
# ============================================================

def is_paused() -> bool:
    """
    GitHub Repository Variable STOCK_CHECK_PAUSED が "true" のとき一時停止。
    Workflow の env: PAUSED: ${{ vars.STOCK_CHECK_PAUSED }} 経由で受け取る。
    """
    value = os.environ.get("PAUSED", "false").strip().lower()
    return value == "true"

# ============================================================
# 在庫チェック
# ============================================================

def check_stock(product: dict) -> tuple[bool | None, str]:
    """
    Returns:
        (True,  reason) : 在庫あり
        (False, reason) : 在庫なし
        (None,  reason) : 判定不能 / エラー
    """
    try:
        resp = requests.get(product["url"], headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        return None, f"接続エラー: {e}"

    if resp.status_code == 404:
        return False, "404 Not Found（ページ非公開）"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"

    html = resp.text

    for kw in IN_STOCK_KEYWORDS:
        if kw in html:
            return True, f"在庫あり（キーワード: {kw}）"

    for kw in OUT_OF_STOCK_KEYWORDS:
        if kw in html:
            return False, f"在庫なし（キーワード: {kw}）"

    # JSON-LD の availability を解析
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", {"type": "application/ld+json"}):
            data = json.loads(tag.string or "{}")
            avail = data.get("offers", {}).get("availability", "")
            if "InStock" in avail:
                return True, f"在庫あり（JSON-LD: {avail}）"
            if "OutOfStock" in avail:
                return False, f"在庫なし（JSON-LD: {avail}）"
    except Exception:
        pass

    return None, "判定不能（ページ構造変更の可能性あり）"

# ============================================================
# Discord Webhook 通知
# ============================================================

def send_discord(embeds: list[dict]) -> bool:
    """Discord Webhook で Embed 通知を送信する"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️  DISCORD_WEBHOOK_URL が未設定です")
        return False

    payload = {"embeds": embeds}
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code in (200, 204):
            print("✅ Discord 通知送信成功")
            return True
        else:
            print(f"❌ Discord エラー: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"❌ Discord 送信例外: {e}")
        return False


def build_stock_embed(product: dict, u: datetime, j: datetime) -> dict:
    """入荷通知用 Discord Embed を生成する"""
    return {
        "title": f"🛒 入荷しました！",
        "description": (
            f"{product['emoji']} **{product['name']}**\n\n"
            f"[今すぐ購入する]({product['url']})"
        ),
        "color": 0x00C853,  # 緑
        "fields": [
            {
                "name": "⏰ 検知時刻",
                "value": (
                    f"UTC: `{u.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    f"JST: `{j.strftime('%Y-%m-%d %H:%M:%S')}`"
                ),
                "inline": False,
            }
        ],
        "footer": {"text": "Apple 整備済製品 在庫チェッカー"},
    }

# ============================================================
# 状態管理
# ============================================================

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ============================================================
# メイン
# ============================================================

def main():
    print("=" * 60)
    print(f"🔍 在庫チェック開始: {time_label()}")
    print("=" * 60)

    # ── 一時停止チェック ──────────────────────────────────
    if is_paused():
        print("⏸️  監視は一時停止中です（Discord で /resume を実行してください）")
        print("=" * 60)
        return

    state = load_state()
    embeds_to_send = []
    changed = False

    for product in PRODUCTS:
        key = product["id"]
        in_stock, reason = check_stock(product)
        prev = state.get(key)

        u = now_utc()
        j = now_jst()
        ts_short = f"UTC {u.strftime('%H:%M:%S')} / JST {j.strftime('%H:%M:%S')}"
        symbol = "✅" if in_stock else ("❌" if in_stock is False else "⚠️")

        print(f"  {symbol} [{ts_short}] {product['name']}")
        print(f"      → {reason}")

        # 在庫あり かつ 前回は在庫なし/不明 → 新規入荷！
        if in_stock is True and prev is not True:
            embeds_to_send.append(build_stock_embed(product, u, j))
            state[key] = True
            changed = True

        # 在庫なし かつ 前回は在庫あり → 売り切れに変化
        elif in_stock is False and prev is True:
            print("      ℹ️ 在庫なしに変化（通知なし）")
            state[key] = False
            changed = True

        elif in_stock is True:
            state[key] = True

    # ── Discord 通知 ──────────────────────────────────────
    if embeds_to_send:
        print(f"\n  📣 {len(embeds_to_send)}件の入荷を Discord に通知します")
        # Discord は一度に最大10件の Embed を送れる
        for i in range(0, len(embeds_to_send), 10):
            send_discord(embeds_to_send[i : i + 10])
    else:
        print("\n  📭 新規入荷なし（通知なし）")

    if changed:
        save_state(state)
        print(f"\n  💾 状態ファイル更新: {STATE_FILE}")

    print("=" * 60)
    print(f"✔ チェック完了: {time_label()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
