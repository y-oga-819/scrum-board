# コントリビューションガイド

このリポジトリでの開発の進め方をまとめる。**設計の正**は
[`docs/proposal.html`](./docs/proposal.html)（設計提案書）にあり、**実装の進捗**は
[`docs/progress.md`](./docs/progress.md) の PBI（`B-NN`）で管理する。**設計判断**は
[`docs/decisions/`](./docs/decisions/)（`D-NN`）に残す。

> AI エージェント（Claude Code）向けの作業指針は [`CLAUDE.md`](./CLAUDE.md) にある。
> コミット規約・ブランチ戦略は本ドキュメントと CLAUDE.md で一致させている。

## 開発環境のセットアップ

必要なもの（バージョンの根拠は [`README.md`](./README.md)）:

- Node.js 22（`.nvmrc` に固定）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（Python 依存管理）

```bash
make install     # フロント（npm）+ バックエンド（uv）の依存を導入
make dev         # フロント :4200 + バックエンド :8000 をライブリロードで起動
make run         # 本番相当（SPA をビルドして FastAPI が :8000 で配信）
make test        # 全テスト（pytest + Vitest）
```

`make help` で全ターゲットを一覧できる。

## 開発の流れ（ブランチ戦略）

`main` を唯一の長命ブランチとし、そこから短命な作業ブランチを切って PR で戻す。

- **`main` は保護ブランチ**。直接 push しない。`main` への push は
  [`deploy.yml`](./.github/workflows/deploy.yml) で **本番へ自動デプロイ**される
  ため、`main` は常にデプロイ可能な状態を保つ（＝リリースブランチを兼ねる）。
- **作業は必ずブランチを切る。** 命名は種別プレフィックスを付ける
  （例: `feat/backlog-crud`, `fix/etag-412`, `docs/contributing`）。
  対応する PBI があればブランチ名や PR に ID（例: `B-13`）を含めると辿りやすい。
- **PR を出してマージする。** CI が緑になり、必須チェックを満たしてからマージする
  （必須チェックの設定は [`docs/setup/ci-branch-protection.md`](./docs/setup/ci-branch-protection.md)）。
- **base を最新に保つ。** `main` が進んだら取り込んでから（rebase / merge）マージする。

## コミットメッセージ規約

**1 PR = 1 コミットにしない。** レビュアーが上から順に読める「物語」になるよう、
1 コミット = 1 つの完結した論理的変更に分ける（詳しい分け方は
[`CLAUDE.md`](./CLAUDE.md) の「コミットの粒度」）。

- そのコミット単体でビルド・テストが通り、`git revert` が意味を持つ単位にする。
- **種類を混ぜない。** 機能追加・リファクタ・フォーマット・依存更新は別コミット。
- **1 行目は要約、本文に Why を書く。** 何を変えたかは差分でわかる。

書式は Conventional Commits 風の日本語プレフィックスを使う。PBI 対応作業なら
本文（または要約）に ID を含める。

```
feat: B-15 PBI の CRUD API（作成・取得・更新・論理削除）
fix: MSAL protectedResourceMap を /api/* にする
refactor: Cosmos クライアントをシングルトン化する器を用意
docs: B-13 リポジトリ規約の整備
```

プレフィックスの目安: `feat` / `fix` / `refactor` / `docs` / `test` / `ci` /
`chore` / `style`。

## コード品質のゲート

PR を出す前に、ローカルで次を通しておく（CI でも同じものが走る）:

```bash
make lint        # ruff / ESLint
make typecheck   # mypy / tsc
make test        # pytest / Vitest
```

- **サーバーを信頼境界とする。** フロントのバリデーションは UX 補助であり、正は
  API（D-20）。
- **API の型はハンドラで手書きしない。** OpenAPI を単一の真実とし
  `make gen-types` で生成する。生成物（`frontend/src/app/api/schema.d.ts`）はコミット
  し、CI が差分を検出する（生成し忘れを弾く）。

## プルリクエスト

PR の説明は [`.github/PULL_REQUEST_TEMPLATE.md`](./.github/PULL_REQUEST_TEMPLATE.md)
に従う。差分でわかる「何を変えたか」ではなく、**なぜ・考え方がどう変わったか・
リリースで気をつけること**を書く。

- 進捗に影響する変更は [`docs/progress.md`](./docs/progress.md) の PBI 完了条件を
  更新する。
- 設計判断が変わった／新たに決めたときは [`docs/decisions/`](./docs/decisions/) に
  `D-NN` を残す（番号空間は 1 つ）。
