import requests
import time
import os
from datetime import datetime

# Discord Webhook URL (GitHub Secretsから取得)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 監視対象
TARGETS = {
    "デザートチタニウム": "https://www.apple.com/jp/shop/product/FYWJ3J/A/",
    "ナチュラルチタニウム": "https://www.apple.com/jp/shop/product/FYWK3J/A/",
    "ホワイトチタニウム": "https://www.apple.com/jp/shop/product/FYWH3J/A/",
    "ブラックチタニウム": "https://www.apple.com/jp/shop/product/FYWG3J/A/"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def send_discord_notification(color, url):
    if not DISCORD_WEBHOOK_URL:
        print(f"[{datetime.now()}] Discord Webhook URL is not set.")
        return

    data = {
        "content": f"【在庫あり】出品中\nカラー: {color}\nURL: {url}"
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
        print(f"[{datetime.now()}] Notification sent for {color}")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send notification: {e}")

def check_stock():
    print(f"[{datetime.now()}] Checking stock...")
    
    # 1番目のカラーを読み込む（デザートチタニウム）
    first_color = list(TARGETS.keys())[0]
    first_url = TARGETS[first_color]
    
    try:
        # 最初のページ読み込み
        requests.get(first_url, headers=HEADERS, timeout=10)
        
        # 3秒待機
        time.sleep(3)
        
        # 全カラーのチェック開始
        for color, url in TARGETS.items():
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                # 「在庫切れ」という文字列が含まれていないかチェック
                if "在庫切れ" not in response.text and "現在ご利用いただけません" not in response.text:
                    print(f"[{datetime.now()}] {color}: 在庫あり！")
                    send_discord_notification(color, url)
                else:
                    print(f"[{datetime.now()}] {color}: 在庫切れ")
            else:
                print(f"[{datetime.now()}] Failed to fetch {color} (Status: {response.status_code})")
                
    except Exception as e:
        print(f"[{datetime.now()}] Error during check: {e}")

if __name__ == "__main__":
    check_stock()
