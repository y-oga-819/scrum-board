# Azure リソースの用意（B-05）

App Service（F1）・Cosmos DB（無料レベル）・予算アラートを **再実行可能な形**で
作る手順。設計の根拠は提案書 09 章「環境構築の再現性」にある。ポータルのクリック
手順は UI 変更で静かに陳腐化するため、**az CLI スクリプトを手順の中心**に置き、
GUI でしか操作できない部分だけをこの文章で補う。

正となるスクリプト: [`scripts/setup/provision-azure.sh`](../../scripts/setup/provision-azure.sh)

---

## 前提

- Azure サブスクリプション（無料枠を使う）
- [az CLI](https://aka.ms/azcli) がインストール済み
- Cosmos DB **無料レベルはサブスクリプションに 1 アカウントだけ**。既に別の無料枠
  アカウントがあると新規作成は失敗する（その場合は既存を流用する）。

## 実行

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID or NAME>"

# App Service 名はグローバルに一意。自分用の値を決めて控える。
# 予算通知先メールは必ず渡す（未設定だと通知が届かない）。
AZ_WEBAPP_NAME=scrum-board-yoga \
AZ_BUDGET_CONTACT=you@example.com \
  ./scripts/setup/provision-azure.sh
```

冪等に書いてあるので **何度実行しても同じ状態に収束する**。無料枠の作り直し・
検証環境の追加でそのまま再実行できる。

### 上書きできる主な値（環境変数）

| 変数 | 既定 | 意味 |
|---|---|---|
| `AZ_LOCATION` | `japaneast` | リージョン |
| `AZ_RESOURCE_GROUP` | `rg-scrum-board` | リソースグループ |
| `AZ_WEBAPP_NAME` | `scrum-board` | **グローバル一意**な App Service 名 |
| `AZ_COSMOS_ACCOUNT` | `cosmos-scrum-board` | Cosmos アカウント名 |
| `AZ_BUDGET_AMOUNT` | `1000` | 予算額（サブスクリプション既定通貨） |
| `AZ_BUDGET_CONTACT` | （空） | 予算通知先メール（カンマ区切り可） |
| `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` | （空） | B-02 の実値。App Service に流し込む |

## スクリプトが作るもの

| リソース | 要点 |
|---|---|
| リソースグループ | 以降すべてここに入る |
| App Service プラン | **F1（無料）・Linux**。`--sku F1` を明示（既定では選ばれない） |
| Web App | **Python 3.11**。起動は `gunicorn`＋`uvicorn` ワーカー 1 本（F1 は RAM 1GB） |
| Cosmos DB | **無料レベルを明示**（`--enable-free-tier true`）＋ データベース 1 つ |
| 予算アラート | 50 / 80 / 100 % で通知。**Azure に自動の支出上限は無い**ため初日に必須 |

App Service には次のアプリ設定が入る:

- `SCM_DO_BUILD_DURING_DEPLOYMENT=true` — Oryx が `requirements.txt` から依存を入れる
- `SPA_DIST_DIR=/home/site/wwwroot/spa/browser` — 同梱した SPA 成果物の場所（`app/config.py` が読む）
- `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` — B-02 の実値（`app/auth/settings.py`）

> コンテナ（PK `/productId`・インデックス除外パス）は **B-07** でアプリ側から作る。
> ここではデータベースまで。

## CLI で完結しない手動ステップ

1. **Entra リダイレクト URI の登録**（B-02 側）
   公開 URL が確定したら、Entra のアプリ登録（SPA プラットフォーム）に
   `https://<webapp>.azurewebsites.net/` を追加する。スクリプト末尾に URL が出る。
2. **予算通知の受信確認**
   初回はテスト通知が届くか、[コスト管理] → [予算] で設定を確認する。

## 検証チェックリスト（B-05 完了条件）

- [ ] App Service F1 が作成されている（`az appservice plan show ... --query sku`）
- [ ] Cosmos DB が**無料レベル**で作成されている（`az cosmosdb show ... --query enableFreeTier` が `true`）
- [ ] 予算アラートが設定されている（[コスト管理] → [予算]）
- [ ] スクリプトが再実行でき、2 回目もエラーにならない

## 次のステップ

- **B-06**: [デプロイ手順](./deploy.md) — GitHub Actions で main push → 自動デプロイ
