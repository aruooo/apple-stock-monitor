# Apple 整備済製品 在庫チェッカー

iPhone 16 Pro Max 256GB (SIMフリー) 整備済製品 4色の入荷を自動監視し、
入荷した瞬間に **Discord** で通知します。

> **PCオフでも常時稼働** — GitHub Actions（無料）がクラウドで動くため、
> 自分のPCは一切不要です。

---

## 監視対象

| カラー | SKU | URL |
|--------|-----|-----|
| ホワイトチタニウム | FYWH3J | https://www.apple.com/jp/xc/product/FYWH3J/A |
| デザートチタニウム | FYWJ3J | https://www.apple.com/jp/xc/product/FYWJ3J/A |
| ナチュラルチタニウム | FYWK3J | https://www.apple.com/jp/xc/product/FYWK3J/A |
| ブラックチタニウム | FYWG3J | https://www.apple.com/jp/xc/product/FYWG3J/A |

---

## チェック間隔

| UTC時間帯 | JST時間帯 | 間隔 |
|-----------|-----------|------|
| 05:00 〜 09:55 | 14:00 〜 18:55 | **5分** |
| 12:00 〜 14:00 | 21:00 〜 23:00 | **15分** |
| 15:00 〜 18:00 | 00:00 〜 03:00 | **10分** |

※ 上記以外の時間帯はチェックなし

---

## 費用

| サービス | 費用 |
|---------|------|
| GitHub (Actions 含む) | **無料** (Public リポジトリ) |
| Discord Webhook | **無料** |
| 合計 | **¥0** |

---

## セットアップ手順

### Step 1 — GitHub リポジトリを作成

1. [github.com](https://github.com) にログイン（アカウントがなければ無料で作成）
2. 右上「**+**」→「**New repository**」
3. リポジトリ名: `apple-stock-checker`（任意）
4. **Public** を選択（Privateでも動くが、Public の方が Actions 無制限）
5. 「**Create repository**」

---

### Step 2 — ファイルをアップロード

以下のファイル構成でアップロード：

```
apple-stock-checker/
├── check_stock.py
├── requirements.txt
├── stock_state.json        ← 空ファイルでOK（後述）
└── .github/
    └── workflows/
        ├── check_5min.yml
        ├── check_10min.yml
        ├── check_15min.yml
        └── pause_control.yml
```

**stock_state.json** は最初は空の `{}` を作成：
```json
{}
```

GitHub の画面から「Add file」→「Create new file」で各ファイルを貼り付けてもOKです。

---

### Step 3 — Discord Webhook URL を取得

1. 通知を受け取りたい Discord サーバーのチャンネルを開く
2. チャンネル名を右クリック →「**チャンネルの編集**」
3. 「**連携サービス**」→「**ウェブフック**」→「**新しいウェブフック**」
4. 名前を入力（例: `Apple 在庫モニター`）し、「**ウェブフック URLをコピー**」

---

### Step 4 — GitHub Secrets に登録

1. GitHub リポジトリ → **Settings** → **Secrets and variables** → **Actions**
2. 「**New repository secret**」で以下を追加：

| Name | Value |
|------|-------|
| `DISCORD_WEBHOOK_URL` | Discord でコピーした Webhook URL |

---

### Step 5 — Actions を有効化

1. リポジトリの「**Actions**」タブを開く
2. 初回は「ワークフローを有効にする」ボタンが表示されたらクリック
3. 動作確認したい場合は、各ワークフローを選んで「**Run workflow**」で手動実行できる

---

## ディレクトリ構成

```
apple-stock-checker/
├── check_stock.py           # メインスクリプト
├── requirements.txt         # 依存ライブラリ
├── stock_state.json         # 在庫状態の記録（自動更新）
└── .github/
    └── workflows/
        ├── check_5min.yml      # UTC 05-09 / JST 14-18 (5分)
        ├── check_10min.yml     # UTC 15-18 / JST 00-03 (10分)
        ├── check_15min.yml     # UTC 12-14 / JST 21-23 (15分)
        └── pause_control.yml   # 監視の一時停止 / 再開
```

---

## 在庫判定の仕組み

1. **日本語キーワード検索** — `カートに入れる` 等が HTML に含まれるか確認
2. **JSON-LD 解析** — `<script type="application/ld+json">` の `offers.availability` を確認
   - `InStock` → 在庫あり
   - `OutOfStock` → 在庫なし
3. どちらでも判定できない場合は「判定不能」としてログに記録（通知なし）

> JSON-LD はサーバーサイドで出力されるため、JavaScript 実行に依存しない確実な判定源です。

---

## 通知の仕組み

- 在庫なし → 在庫あり に変化したときだけ Discord に通知（連続通知しない）
- 売り切れになっても通知なし（入荷通知のみ）
- 状態は `stock_state.json` に保存し、Git にコミットして次回実行に引き継ぐ

---

## 監視の一時停止 / 再開

Actions タブから「**監視 一時停止 / 再開**」ワークフローを手動実行：

- チェックボックスをオンにして実行 → **一時停止**
- チェックボックスをオフにして実行 → **再開**

内部的には GitHub Actions のリポジトリ変数 `STOCK_CHECK_PAUSED` を更新します。

---

## トラブルシューティング

**Actions が動かない**
→ Settings → Actions → General → 「Allow all actions」になっているか確認

**通知が来ない**
→ Actions のログを確認。`DISCORD_WEBHOOK_URL` の設定ミスが多い。
→ `workflow_dispatch` で手動実行してログを確認

**在庫判定が「判定不能」になる**
→ Apple がページ構造を変更した可能性あり。
→ `check_stock.py` の `IN_STOCK_KEYWORDS` / `OUT_OF_STOCK_KEYWORDS` を最新のページを見て更新してください。

---

## ⚠️ 注意事項

- GitHub Actions の cron は**数分程度の遅延**が発生することがあります（保証なし）
- Apple がBot検知（Cloudflare 等）を強化した場合、HTTPリクエストがブロックされることがあります
- 不正アクセス・過剰アクセスとならないよう、最短5分間隔にしています
