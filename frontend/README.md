# フロントエンド（Angular）

Scrum Board の SPA。[Angular CLI](https://github.com/angular/angular-cli) 20 系で生成。
ビルド成果物（`dist/`）は同一 App Service 上の FastAPI が配信する（提案書 09 章）。

> セットアップ・起動・テストは基本的に**リポジトリのルートから `make` 経由**で行う。
> 全体像はルートの [`README`](../README.md) を参照。ここは frontend 固有の補足のみ。

## 開発サーバー

```bash
ng serve   # ルートからは `make dev`（frontend :4200 + backend :8000 を同時起動）
```

`http://localhost:4200/` を開く。ソースを変更すると自動でリロードされる。
`/api` へのリクエストは `proxy.conf.json` により FastAPI（`:8000`）へプロキシされる
（本番と同じく単一オリジンで動かすため）。

## コード生成

```bash
ng generate component <名前>   # コンポーネント生成
ng generate --help             # 生成できるもの一覧（component / directive / pipe など）
```

## ビルド

```bash
ng build   # ルートからは `make build-frontend`
```

成果物は `dist/frontend/browser/` に出力される（本番向けに最適化される）。
FastAPI はこのディレクトリを配信する。

## ユニットテスト

[Vitest](https://vitest.dev) で実行する（Angular の `@angular/build:unit-test`
ビルダー経由・D-19）。既定は **jsdom** 上で走り実ブラウザを起動しないため、CI が
安定し `--no-sandbox` のような回避策も要らない。

```bash
ng test              # ルートからは `make test-frontend`
ng test --code-coverage   # ルートからは `make coverage-frontend`
```

## E2E テスト

Angular CLI は E2E フレームワークを同梱しない。本プロジェクトでは **B-11（テスト基盤）**
で Playwright を導入する予定（`docs/decisions/D-19`）。

## 参考

- [Angular CLI コマンドリファレンス](https://angular.dev/tools/cli)
