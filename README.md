# Scrum Board

スクラムバックログ管理アプリ。設計の正は
[`docs/proposal.html`](./docs/proposal.html)（設計提案書）にあり、実装の進捗は
[`docs/progress.md`](./docs/progress.md) で管理する。

> 本プロジェクトの主題は「Easy Auth を使わない Entra ID の認証・認可」の PoC
> であり、スクラムアプリはそれを実地で回すための題材を兼ねている（`docs/decisions/D-21`）。

## 構成

フロントエンド（Angular）と API（FastAPI）を **同一の App Service に同居**させる。
App Service が 1 つで済み、CORS 設定も不要になる（提案書 09 章）。

```
scrum-board/
├── frontend/   Angular 20 SPA（ビルド成果物を FastAPI が配信）
├── backend/    FastAPI（/api のみ担当し、それ以外は SPA を返す）
└── Makefile    開発用エントリポイント
```

- 本番相当: FastAPI が `frontend/dist` のビルド成果物を配信し、単一オリジンで動く。
- 開発時: Angular dev server（`:4200`）が `/api` を FastAPI（`:8000`）へプロキシする。

## 必要なもの

- Node.js 22（`.nvmrc` に固定。実行環境の事前インストール版に合わせている）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（Python 依存管理）

> **Angular は 20 系を採用している（最新の 22 ではない）。** 最新 Angular 22 は
> Node `^22.22.3 || ^24.15.0 || >=26` を要求するが、実行環境の事前インストール版が
> Node 22.22.2 でパッチ1つ届かないため。20 系は現行世代で 2026 年までサポート内であり、
> 実害はない。最新へ上げる場合は Node を 24 LTS 以上にし、セッション開始時に Node を
> 用意する導線（SessionStart フック等）をあわせて整備すること。

## セットアップ

```bash
make install
```

## 起動

```bash
# 本番相当（1 コマンド）: SPA をビルドし、FastAPI が :8000 で配信
make run
# → http://localhost:8000 で 1 ページ表示される

# 開発（ライブリロード）: Angular :4200 + FastAPI :8000
make dev
# → http://localhost:4200
```

## テスト

```bash
make test            # 全て
make test-backend    # pytest
make test-frontend   # Karma/Jasmine（ヘッドレス）
```

`make help` で全ターゲットを一覧できる。
