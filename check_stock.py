"""
Apple 整備済製品 在庫チェッカー
================================
監視対象: iPhone 16 Pro Max 256GB (SIMフリー) 整備済製品 4色
通知方法: Discord Webhook

時間帯別チェック間隔（GitHub Actions cron）:
  UTC 05:00-09:55  →  JST 14:00-18:55  :  5分間隔
  UTC 12:00-14:00  →  JST 21:00-23:00  : 15分間隔
  UTC 15:00-18:00  →  JST 00:00-03:00  : 10分間隔
"""

import concurrent.futures
import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# ============================================================
# 設定
# ============================================================

JST = timezone(timedelta(hours=9))

PRODUCTS = [
    {
        "id": "FYWH3J",
        "name": "iPhone 16 Pro Max 256GB - ホワイトチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYWH3J/A",
    },
    {
        "id": "FYWJ3J",
        "name": "iPhone 16 Pro Max 256GB - デザートチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYWJ3J/A",
    },
    {
        "id": "FYWK3J",
        "name": "iPhone 16 Pro Max 256GB - ナチュラルチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYWK3J/A",
    },
    {
        "id": "FYWG3J",
        "name": "iPhone 16 Pro Max 256GB - ブラックチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYWG3J/A",
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

# ============================================================
# 時刻ユーティリティ
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def now_jst() -> datetime:
    return datetime.now(JST)

def time_label() -> str:
    """ログ表示用タイムスタンプ（UTC / JST 両記載）"""
    u = now_utc()
    j = now_jst()
    return (
        f"UTC {u.strftime('%Y-%m-%d %H:%M:%S')} "
        f"/ JST {j.strftime('%Y-%m-%d %H:%M:%S')}"
    )

# ============================================================
# 在庫チェック
# ============================================================

# 在庫あり判定キーワード（日本語 Apple ページ）
IN_STOCK_KEYWORDS = [
    "カートに入れる",
    "今すぐ購入",
    '"availability":"InStock"',
    '"availability": "InStock"',
]

# 在庫なし判定キーワード
OUT_OF_STOCK_KEYWORDS = [
    "現在ご注文いただけません",
    "在庫がありません",
    "売り切れ",
    '"availability":"OutOfStock"',
    '"availability": "OutOfStock"',
]


def check_stock(product: dict) -> tuple[bool | None, str]:
    """
    Returns:
        (True, reason)  : 在庫あり
        (False, reason) : 在庫なし
        (None, reason)  : 判定不能 / エラー
    """
    try:
        resp = requests.get(product["url"], headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        return None, f"接続エラー: {e}"

    # 404 → 商品ページ自体が存在しない（在庫なし扱い）
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
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            avail = offers.get("availability", "")
            if "InStock" in avail:
                return True, f"在庫あり（JSON-LD: {avail}）"
            if "OutOfStock" in avail:
                return False, f"在庫なし（JSON-LD: {avail}）"
    except Exception:
        pass

    return None, "判定不能（ページ構造が変更された可能性あり）"


# ============================================================
# Discord Webhook 通知
# ============================================================

def send_discord_webhook(embeds: list) -> bool:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print("⚠️  DISCORD_WEBHOOK_URL が未設定です")
        return False

    payload = {
        "username": "Apple 在庫モニター",
        "embeds": embeds,
    }
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.ok:
            print("✅ Discord 通知送信成功")
            return True
        else:
            print(f"❌ Discord エラー: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"❌ Discord 送信例外: {e}")
        return False


# ============================================================
# 状態管理（在庫変化検知用）
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
# メイン処理
# ============================================================

def main():
    print("=" * 60)
    print(f"🔍 在庫チェック開始: {time_label()}")
    print("=" * 60)

    state = load_state()
    notify_embeds = []
    changed = False

    # 4製品のHTTPリクエストを並列実行（I/Oバウンドのためスレッドで効果的）
    with concurrent.futures.ThreadPoolExecutor() as executor:
        stock_results = list(executor.map(check_stock, PRODUCTS))

    for product, (in_stock, reason) in zip(PRODUCTS, stock_results):
        key = product["id"]
        prev = state.get(key)  # True / False / None

        u = now_utc()
        j = now_jst()
        ts = f"UTC {u.strftime('%H:%M:%S')} / JST {j.strftime('%H:%M:%S')}"
        symbol = "✅" if in_stock else ("❌" if in_stock is False else "⚠️")
        print(f"  {symbol} [{ts}] {product['name']}")
        print(f"      → {reason}")

        # 在庫あり かつ 前回は在庫なし/不明 → 新規入荷！
        if in_stock is True and prev is not True:
            notify_embeds.append({
                "title": "🛒 入荷しました！",
                "url": product["url"],
                "description": (
                    f"**{product['name']}**\n"
                    f"[今すぐ購入する]({product['url']})"
                ),
                "color": 0x00C853,  # 緑
                "footer": {
                    "text": (
                        f"UTC {u.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"/ JST {j.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                },
            })
            state[key] = True
            changed = True

        # 在庫なし かつ 前回は在庫あり → 売り切れに変化
        elif in_stock is False and prev is True:
            state[key] = False
            changed = True
            print(f"      ℹ️ 在庫なしに変化（通知なし）")

        elif in_stock is True:
            state[key] = True  # 継続在庫（通知不要）

    if notify_embeds:
        send_discord_webhook(notify_embeds)
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
