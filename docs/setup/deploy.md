# デプロイパイプライン（B-06）

`main` への push で App Service に自動デプロイする。認証は **シークレットレス（OIDC）**。
GitHub に保存する秘密は無い（置くのは ID だけ）。

- ワークフロー: [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
- OIDC 設定スクリプト: [`scripts/setup/setup-github-oidc.sh`](../../scripts/setup/setup-github-oidc.sh)
- 前提: [Azure リソースの用意（B-05）](./azure-resources.md) が済んでいること

---

## なぜ publish profile ではなく OIDC か

発行済みの publish profile をシークレットに貼る方式は、値が漏れればそのまま本番を
書き換えられる。OIDC は GitHub Actions が発行する**短命トークン**で `azure/login`
するため保存する秘密が無く、権限も**このリソースグループの Contributor に限定**できる。

## セットアップ（1 回だけ）

```bash
az login
AZ_RESOURCE_GROUP=rg-scrum-board AZ_WEBAPP_NAME=scrum-board-yoga \
  ./scripts/setup/setup-github-oidc.sh y-oga-819/scrum-board
```

スクリプトが作るもの:

- デプロイ専用のアプリ登録＋サービスプリンシパル
- フェデレーション資格情報（`repo:<owner>/<repo>:ref:refs/heads/main` に固定）
- リソースグループ限定の Contributor ロール割り当て

出力された値を GitHub の **Settings → Secrets and variables → Actions → Variables**
に **Repository variables** として登録する（Secrets ではなく Variables）:

| 変数 | 中身 |
|---|---|
| `AZURE_CLIENT_ID` | デプロイ用アプリの appId |
| `AZURE_TENANT_ID` | テナント ID |
| `AZURE_SUBSCRIPTION_ID` | サブスクリプション ID |
| `AZURE_WEBAPP_NAME` | App Service 名（例 `scrum-board-yoga`） |

## デプロイの流れ（ワークフロー）

1. **SPA をビルド** — `npm ci && npm run build`（Node は `.nvmrc` 準拠）
2. **依存を書き出す** — `uv export` で `uv.lock` → `requirements.txt`。本番サーバ
   `gunicorn` だけ追記（ローカルは uvicorn 直叩きなので不要）
3. **パッケージを組む** — wwwroot 直下に `app/`・`requirements.txt`・`spa/browser/`
4. **OIDC でログイン** → `azure/webapps-deploy` で zip デプロイ
5. **スモークテスト** — `/api/health` が 200 になるまでポーリング（F1 のスリープ復帰待ち）

デプロイ先のレイアウト（App Service `wwwroot`）:

```
wwwroot/
├── app/               アプリ本体（startup の app.main:app が指す）
├── requirements.txt   Oryx が依存をインストール
└── spa/browser/       SPA 成果物（SPA_DIST_DIR が指す）
```

起動コマンド（B-05 で設定済み）:

```
gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker \
  --workers 1 --bind 0.0.0.0:8000 --timeout 120
```

## 検証チェックリスト（B-06 完了条件）

- [ ] main への push で App Service に自動デプロイされる（Actions が緑）
- [ ] 公開 URL（`https://<webapp>.azurewebsites.net`）で 1 ページ表示できる
- [ ] 公開 URL でサインインが通る（本番リダイレクト URI の確認 — B-02 の実値が要る）

## トラブルシュート

- **サインインで `AADSTS9002326`**: Entra 側で本番 SPA を **SPA プラットフォーム**に
  登録できていない。`Web` に入れないこと（提案書 08 章 / B-02）。
- **`/api/health` が 503**: SPA 成果物が同梱できていない（`SPA_DIST_DIR` とパッケージの
  `spa/browser/` を突き合わせる）。API 自体は 503 の本文で理由を返す（`app/main.py`）。
- **起動しない**: App Service の [ログ ストリーム] を見る。F1 は初回起動が遅い。
