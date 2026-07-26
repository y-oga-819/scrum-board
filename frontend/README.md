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

[Playwright](https://playwright.dev) を使う（B-11・D-19 の層4）。フローは
`e2e/` に置き、設定は `playwright.config.ts`。

```bash
npm run e2e          # ルートからは `make test-e2e`
```

主要フロー5本の受け皿はあるが、**対象画面（M4/M5）が実装されるまで各フローは
`test.fixme` で skip される**。画面ができた PBI で `test.fixme` を外して本体を
埋める。CI では分単位のコストを避けるため **main マージ時だけ**回す。

## 参考

- [Angular CLI コマンドリファレンス](https://angular.dev/tools/cli)
