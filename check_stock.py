"""
Apple 整備済製品 在庫チェッカー
================================
監視対象:
  - iPhone 16 Pro Max 256GB (SIMフリー) 整備済製品 4色
  - iPhone 16 Pro 128GB (SIMフリー) 整備済製品 4色
  - iPhone 16 Plus 128GB (SIMフリー) 整備済製品 4色
  - iPhone 16 128GB (SIMフリー) 整備済製品 4色
通知方法: Discord Webhook
チェック間隔: 毎1分・24時間（GitHub Actions）
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
    # ── iPhone 16 Pro Max 256GB ─────────────────────────────
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
    # ── iPhone 16 Pro 128GB ──────────────────────────────────
    {
        "id": "FYMW3J",
        "name": "iPhone 16 Pro 128GB - ホワイトチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYMW3J/A",
    },
    {
        "id": "FYMX3J",
        "name": "iPhone 16 Pro 128GB - デザートチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYMX3J/A",
    },
    {
        "id": "FYMY3J",
        "name": "iPhone 16 Pro 128GB - ナチュラルチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYMY3J/A",
    },
    {
        "id": "FYMV3J",
        "name": "iPhone 16 Pro 128GB - ブラックチタニウム（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYMV3J/A",
    },
    # ── iPhone 16 Plus 128GB ─────────────────────────────────
    {
        "id": "FXVF3J",
        "name": "iPhone 16 Plus 128GB - ティール（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FXVF3J/A",
    },
    {
        "id": "FXVE3J",
        "name": "iPhone 16 Plus 128GB - ウルトラマリン（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FXVE3J/A",
    },
    {
        "id": "FXVC3J",
        "name": "iPhone 16 Plus 128GB - ホワイト（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FXVC3J/A",
    },
    {
        "id": "FXVA3J",
        "name": "iPhone 16 Plus 128GB - ブラック（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FXVA3J/A",
    },
    # ── iPhone 16 128GB ──────────────────────────────────────
    {
        "id": "FYDV3J",
        "name": "iPhone 16 128GB - ティール（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYDV3J/A",
    },
    {
        "id": "FYDU3J",
        "name": "iPhone 16 128GB - ウルトラマリン（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYDU3J/A",
    },
    {
        "id": "FYDQ3J",
        "name": "iPhone 16 128GB - ブラック（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYDQ3J/A",
    },
    {
        "id": "FYDR3J",
        "name": "iPhone 16 128GB - ホワイト（SIMフリー）[整備済製品]",
        "url": "https://www.apple.com/jp/xc/product/FYDR3J/A",
    },
]

STATE_FILE = "stock_state.json"

# 連続N回判定不能でDiscordに警告通知
FAILURE_ALERT_THRESHOLD = 3

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
    "ショッピングバッグに入れる",
    "add-to-cart",
    '"availability":"InStock"',
    '"availability": "InStock"',
]

# 在庫なし判定キーワード
OUT_OF_STOCK_KEYWORDS = [
    "現在ご注文いただけません",
    "在庫がありません",
    "売り切れ",
    "このアイテムは現在ご利用いただけません",
    '"availability":"OutOfStock"',
    '"availability": "OutOfStock"',
]


def _parse_jsonld_availability(html: str) -> bool | None:
    """
    JSON-LD の offers.availability を全 script タグ・全 offers から確認する。
    True: 在庫あり / False: 在庫なし / None: 判定不能
    エラーは握り潰さずに呼び出し元でログ出力できるよう例外を伝搬する。
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except json.JSONDecodeError:
            continue

        # JSON-LD 自体がリスト形式の場合を処理
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers", {})
            # offers がリストの場合は全件チェック（先頭だけでなく）
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                avail = offer.get("availability", "")
                if "InStock" in avail:
                    return True
                if "OutOfStock" in avail:
                    return False
    return None


def _fetch_html(product: dict) -> tuple[str | None, str]:
    """HTTP GET して HTML を返す。失敗時は (None, エラー理由)。"""
    try:
        resp = requests.get(product["url"], headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        return None, f"接続エラー: {e}"

    if resp.status_code == 404:
        return None, "404 Not Found（ページ非公開）"
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"

    return resp.text, ""


def _judge_html(html: str) -> tuple[bool | None, str]:
    """HTML から在庫を判定する。"""
    for kw in IN_STOCK_KEYWORDS:
        if kw in html:
            return True, f"在庫あり（キーワード: {kw}）"

    for kw in OUT_OF_STOCK_KEYWORDS:
        if kw in html:
            return False, f"在庫なし（キーワード: {kw}）"

    try:
        result = _parse_jsonld_availability(html)
        if result is True:
            return True, "在庫あり（JSON-LD）"
        if result is False:
            return False, "在庫なし（JSON-LD）"
    except Exception as e:
        return None, f"JSON-LD 解析エラー: {e}"

    return None, "判定不能（ページ構造が変更された可能性あり）"


def check_stock(product: dict) -> tuple[bool | None, str]:
    """
    Returns:
        (True, reason)  : 在庫あり
        (False, reason) : 在庫なし
        (None, reason)  : 判定不能 / エラー

    判定不能の場合は 5 秒後に 1 回リトライする。
    """
    import time

    # 404 は在庫なし（リトライ不要）
    html, err = _fetch_html(product)
    if html is None:
        if "404" in err:
            return False, err
        # 接続エラー / 非200 → リトライ
        time.sleep(5)
        html, err = _fetch_html(product)
        if html is None:
            return None, f"{err}（リトライ後も失敗）"

    result, reason = _judge_html(html)

    # 判定不能 → 5 秒後に再取得してリトライ
    if result is None:
        time.sleep(5)
        html2, err2 = _fetch_html(product)
        if html2 is not None:
            result2, reason2 = _judge_html(html2)
            if result2 is not None:
                return result2, f"{reason2}（リトライで判定）"
        return None, reason

    return result, reason


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
    failure_counts = state.get("_failure_counts", {})

    # 全製品のHTTPリクエストを並列実行（I/Oバウンドのためスレッドで効果的）
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

        # 在庫あり → 毎回通知
        if in_stock is True:
            label = "🛒 入荷しました！" if prev is not True else "🛒 引き続き在庫あり"
            notify_embeds.append({
                "title": label,
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
            failure_counts[key] = 0
            changed = True

        # 在庫なし かつ 前回は在庫あり → 売り切れに変化
        elif in_stock is False and prev is True:
            state[key] = False
            failure_counts[key] = 0
            changed = True
            print(f"      ℹ️ 在庫なしに変化（通知なし）")

        # 判定不能 → 連続失敗カウント + state の詰まり防止
        elif in_stock is None:
            count = failure_counts.get(key, 0) + 1
            failure_counts[key] = count
            # True のまま放置すると「在庫あり→判定不能→在庫あり」時に
            # prev=True になり通知が届かなくなるためリセット
            if prev is True:
                state[key] = None
            changed = True
            if count == FAILURE_ALERT_THRESHOLD:
                print(f"      🚨 連続{count}回判定不能 → Discord に警告通知")
                notify_embeds.append({
                    "title": "⚠️ 在庫チェック失敗",
                    "url": product["url"],
                    "description": (
                        f"**{product['name']}**\n"
                        f"連続 {count} 回判定不能です。\n"
                        f"Apple のページ構造変更や Bot 検知の可能性があります。\n"
                        f"最新エラー: `{reason}`"
                    ),
                    "color": 0xFF6D00,  # オレンジ
                    "footer": {
                        "text": (
                            f"UTC {u.strftime('%Y-%m-%d %H:%M:%S')} "
                            f"/ JST {j.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    },
                })

    if notify_embeds:
        send_discord_webhook(notify_embeds)
    else:
        print("\n  📭 新規入荷なし（通知なし）")

    if changed:
        state["_failure_counts"] = failure_counts
        save_state(state)
        print(f"\n  💾 状態ファイル更新: {STATE_FILE}")

    print("=" * 60)
    print(f"✔ チェック完了: {time_label()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
