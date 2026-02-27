"""
Apple 整備済製品 在庫チェッカー
================================
監視対象: iPhone 16 Pro Max 256GB (SIMフリー) 整備済製品 4色
通知方法: Telegram Bot → iPhone

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
    "add-to-cart",          # HTML class/id
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
            avail = data.get("offers", {}).get("availability", "")
            if "InStock" in avail:
                return True, f"在庫あり（JSON-LD: {avail}）"
            if "OutOfStock" in avail:
                return False, f"在庫なし（JSON-LD: {avail}）"
    except Exception:
        pass

    return None, "判定不能（ページ構造が変更された可能性あり）"


# ============================================================
# Telegram 通知
# ============================================================

def send_telegram(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️  TELEGRAM_BOT_TOKEN または TELEGRAM_CHAT_ID が未設定です")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.ok:
            print("✅ Telegram 通知送信成功")
            return True
        else:
            print(f"❌ Telegram エラー: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram 送信例外: {e}")
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
    notify_messages = []
    changed = False

    for product in PRODUCTS:
        key = product["id"]
        in_stock, reason = check_stock(product)
        prev = state.get(key)  # True / False / None

        u = now_utc()
        j = now_jst()
        ts = f"UTC {u.strftime('%H:%M:%S')} / JST {j.strftime('%H:%M:%S')}"
        symbol = "✅" if in_stock else ("❌" if in_stock is False else "⚠️")
        print(f"  {symbol} [{ts}] {product['name']}")
        print(f"      → {reason}")

        # 在庫あり かつ 前回は在庫なし/不明 → 新規入荷！
        if in_stock is True and prev is not True:
            notify_messages.append(
                f"🛒 <b>入荷しました！</b>\n"
                f"{product['name']}\n"
                f"<a href=\"{product['url']}\">今すぐ購入する</a>\n"
                f"⏰ UTC: {u.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⏰ JST: {j.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            state[key] = True
            changed = True

        # 在庫なし かつ 前回は在庫あり → 売り切れに変化
        elif in_stock is False and prev is True:
            state[key] = False
            changed = True
            print(f"      ℹ️ 在庫なしに変化（通知なし）")

        elif in_stock is True:
            state[key] = True  # 継続在庫（通知不要）

    if notify_messages:
        header = (
            f"🍎 <b>Apple 整備済製品 入荷アラート</b>\n"
            f"({len(notify_messages)}件)\n\n"
        )
        full_msg = header + "\n\n".join(notify_messages)
        send_telegram(full_msg)
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
