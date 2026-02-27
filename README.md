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

**24時間・毎5分**（時間帯制限なし）

パブリックリポジトリのため GitHub Actions の使用時間は無制限です。

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
└── .github/
    └── workflows/
        ├── check_stock.yml
        └── pause_control.yml
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
└── .github/
    └── workflows/
        ├── check_stock.yml     # 毎5分・24時間チェック
        └── pause_control.yml   # 監視の一時停止 / 再開
```

> `stock_state.json`（在庫状態の記録）はリポジトリには含まれません。
> GitHub Actions Cache で実行間引き継がれます。

---

## 在庫判定の仕組み

1. **日本語キーワード検索** — `カートに入れる` 等が HTML に含まれるか確認
2. **JSON-LD 解析** — `<script type="application/ld+json">` の `offers.availability` を確認
   - `InStock` → 在庫あり
   - `OutOfStock` → 在庫なし
3. どちらでも判定できない場合は「判定不能」としてログに記録（3回連続で Discord に警告通知）

> JSON-LD はサーバーサイドで出力されるため、JavaScript 実行に依存しない確実な判定源です。

---

## 通知の仕組み

- 在庫なし → 在庫あり に変化したときだけ Discord に通知（連続通知しない）
- 売り切れになっても通知なし（入荷通知のみ）
- 状態は `stock_state.json` に保存し、GitHub Actions Cache で次回実行に引き継ぐ
- 判定不能が **3回連続** 続いた場合、⚠️ 警告を Discord に通知（ページ構造変更・Bot検知の早期発見）

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

**判定不能の Discord 通知が来た**
→ Apple がページ構造を変更した可能性あり。
→ `check_stock.py` の `IN_STOCK_KEYWORDS` / `OUT_OF_STOCK_KEYWORDS` を最新のページを見て更新してください。
→ 3回連続で判定不能になると自動で通知されます（`FAILURE_ALERT_THRESHOLD` で変更可）。

---

## ⚠️ 注意事項

- GitHub Actions の cron は**数分程度の遅延**が発生することがあります（保証なし）
- Apple がBot検知（Cloudflare 等）を強化した場合、HTTPリクエストがブロックされることがあります
- 不正アクセス・過剰アクセスとならないよう、最短5分間隔にしています
