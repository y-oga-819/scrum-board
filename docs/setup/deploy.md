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
└── spa/browser/       SPA 成果物（app パッケージの隣。config.py が相対で探す）
```

> ⚠️ App Service（Linux / Python）は Oryx ビルドの成果物を `output.tar.zst` に圧縮し、
> **起動時に動的なテンポラリ領域へ展開**して実行する。そのため
> `/home/site/wwwroot/spa/browser` のような固定の絶対パスを `SPA_DIST_DIR` に入れると
> 的を外す（展開先に無い）。`app/config.py` は **app パッケージからの相対**で `spa/browser`
> を解決するので、`SPA_DIST_DIR` は設定しない（設定しても index.html が無ければ相対解決に
> フォールバックする）。

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
- **ルート（`/`）で 503 "SPA is not built yet"**: API は動いているが SPA が見つからない。
  多くは `SPA_DIST_DIR` に圧縮前の絶対パスが残っているケース。上記のとおり `config.py` が
  相対解決するので、`SPA_DIST_DIR` は**未設定**にする（`az webapp config appsettings delete
  --setting-names SPA_DIST_DIR`）。それでも出るなら、`output.tar.zst` に `spa/` が含まれているか
  （＝パッケージに `spa/browser/` が入っていたか）を確認する。
- **起動しない**: App Service の [ログ ストリーム] を見る。F1 は初回起動が遅い。
