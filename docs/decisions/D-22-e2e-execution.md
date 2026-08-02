# D-22 E2E をヘッドレス CI で緑にする実行方式

- **対応PBI**: [EX-1](../progress.md)（E2E 実行整備・横断/番号外）
- **関連**: [D-19](./D-19-test-strategy.md)（テスト戦略・層4）、[D-21](./D-21-bootstrap-and-migration.md)（ユーザー解決ポート・E2E データ計画）、[B-14](../progress.md)（ゲスト経路・任意）
- **決定日**: 2026-08-02

---

## 背景

E2E（D-19 の層4）は受け皿（`frontend/e2e/*.spec.ts`・`playwright.config.ts`・`e2e.yml`）が
既にあるが、**中身が空で緑にならない**。全フローが `test.fixme`、`webServer` はコメントアウト、
そして最大の障壁は **ヘッドレスのサインイン経路が無い**ことにある。

E2E は層1〜3 と違い **「実サーバ（uvicorn）＋ 実ブラウザ（Chromium）」** で回る。層2 の
`app.dependency_overrides` は**同一プロセス内でしか効かない**ため、別プロセスで起動した実サーバには
使えない。しかもフロントは全ルートを `MsalGuard` で守り、`MsalInterceptor` が `/api/*` に Bearer を
付ける。つまり認証バイパスは **フロントとバックエンドの両方**に効かせる必要がある。

---

## 決定

| 項目 | 決定 |
|:---|:---|
| サインイン（バック） | `get_current_user_resolver` を **env フラグ `E2E_AUTH_BYPASS` でゲート**し、固定テストユーザーを返すリゾルバに差し替える。**既定 OFF（未設定＝Entra）** |
| サインイン（フロント） | **e2e ビルド構成**（`fileReplacements` で `environment.e2e.ts`）で `MsalGuard`・`MsalInterceptor`・`initialize()` を**登録しない**。本番バンドルには入らない |
| データ基盤 | **Cosmos エミュレータ**（D-21 準拠）。app 起動時のマイグレーション全適用 + fixtures 投入 |
| 隔離 | `prd_test_<runId>` パーティション。**`prd_test_` 以外の productId への投入は拒否**（D-21 のガードレール） |
| teardown | **物理削除**（D-21）。既存の論理削除 `soft_delete` はアプリの復旧価値のための別機構なので使わない |
| プロダクト選択の決定性 | E2E ユーザーは `prd_test_<runId>` の member **のみ**にする。`/api/me` の**サンドボックス自動参加を E2E モードでスキップ**し、`products` が 1 件だけ返るようにして `ProductService.selected` が確実にそれを選ぶ |

---

## なぜこの方式か（テスト用トークン注入・B-14 ゲストではなく）

D-21 は「**E2E は層2と同じくユーザー解決ポートを差し替えて回す。ゲスト経路を採用するなら
使ってもよいが、テスト用実装があれば足りる**」と定めている。本決定はこれに素直に従う。

- **テスト用トークン注入は採らない。** テスト鍵で JWT を発行し静的 JWKS を立てて実
  `EntraCurrentUserResolver` に検証させる案は本番コードを触らずに済むが、ブラウザ側で MSAL の
  SessionStorage にアカウント/トークンを注入する必要があり、MSAL キャッシュ表現に依存して**壊れやすい**。
- **B-14 ゲストの本実装は採らない（今は）。** B-14 は env 制御の製品機能だが D-21 で**サンドボックス限定**。
  E2E は `prd_test_<runId>` を使うため整合に追加設計が要る。E2E を緑にするのに製品機能の実装を先行させる
  理由がない。B-14 は任意 PBI として別に残す。
- 選んだ方式は **fail-closed**（env を設定しなければ本番挙動）で、本番バンドル・本番入口に
  バイパス経路が焼き込まれない（フロントは `fileReplacements`、バックは env 分岐で既定 Entra）。

---

## スコープ

- 本決定と EX-1 が緑にするのは **フロー①（`signin-pbi-task.spec.ts`）**。共通基盤（サインイン経路・
  `webServer`・seeding）はここで用意し、フロー②〜⑤は対象画面が揃い次第、各担当 PBI で `test.fixme`
  を外して同じ基盤に乗せる。
- ブランチ保護の必須チェック登録自体は管理者が GitHub 設定で行う（手順は
  `docs/setup/ci-branch-protection.md`）。
