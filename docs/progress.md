# スクラムバックログ管理アプリ — 開発進捗管理

> このアプリ自身でPBI管理ができるようになる（マイルストーン **M5** 到達）までの間、
> AI開発の進捗をこのファイルで管理する。設計の正はあくまで
> [`docs/proposal.html`](./proposal.html)（設計提案書）にあり、本ファイルはその
> 実装進捗のトラッカーである。

- **設計原則**（迷ったらここに戻る／提案書 01章）
  - **P-1** ルールで縛らず、事実を見せる
  - **P-2** 管理コストを下げる
  - **P-3** 後から復元できない情報だけを先に持つ
- **完了条件の考え方**（提案書 12章）: 「機能が動くか」ではなく
  **設計判断が実装に落ちたか**を確認できる形で書く。

---

## このファイルの使い方

- 各PBIは `未着手` → `進行中` → `完了` の3状態で管理する（アプリの `todo/doing/done` に対応）。
- 進捗の実体は各PBIの**完了条件チェックリスト**にある。チェックが全部埋まって初めて `完了`。
- **IDは着手順に採番してある。** `B-01` から順に上から消化していき、
  そのマイルストーンの最後のPBIが `完了` になった時点でマイルストーンが終わる。
- 依存は原則として**自分より小さい番号**を指す。番号順に進めれば依存は自然に解ける。
- 提案書初版に無いPBI（レビューと方針検討で追加したもの）は末尾に一覧がある。

### ステータス凡例

| 記号 | 状態 | 意味 |
|:---:|:---|:---|
| ⬜ | 未着手 | 未着手。依存が解けていれば着手可能 |
| 🟨 | 進行中 | 着手済み。完了条件の一部が未達 |
| ✅ | 完了 | 完了条件をすべて満たした |
| 🔒 | ブロック | 依存または未決事項で着手できない |

---

## サマリ

| マイルストーン | 到達点 | PBI | 進捗 |
|:---:|:---|:---|:---:|
| **M1** | ★**1ページがEntra IDで保護される**（Easy Authなし） | B-01 〜 B-06 | ✅ **6 / 6** |
| **M2** | ★**認可まで通る**（非メンバーは403・初回サインインで自動参加） | B-07 〜 B-10 | ✅ **4 / 4** |
| **M3** | 開発の土台（テスト/CI/API規約/リポジトリ規約） | B-11 〜 B-14 | 🟨 3 / 4（B-11・B-12・B-13 完了・B-14 は🔸任意/未着手） |
| **M4** | プロダクトバックログが運用できる | B-15 〜 B-20 | ✅ **6 / 6** |
| **M5** | ★**スプリントが1周回る**（ここからドッグフーディング） | B-21 〜 B-26 | ✅ **6 / 6** |
| **M6** | デイリースクラムがこの画面だけで完結する | B-27 〜 B-29 | 🟨 1 / 3（B-27 完了・B-28・B-29 未着手） |
| **M7** | 実運用に耐える | B-30 〜 B-31 | 0 / 2 |
| **M8** | *（将来）* プロジェクトを自分たちで管理できる | B-32 〜 B-33 | 0 / 2 |
| **EX** | 横断（着手順の外）— E2E 実行整備・カバレッジ可視化 等 | EX-1, EX-2 | ✅ 2 / 2 |
| | | **合計** | **26 / 33（＋EX 2 / 2）** |

> ★ **本プロジェクトの主題は「Easy Authを使わないEntra IDの認証・認可」のPoC**であり、
> スクラムアプリはそれを実地で回すための題材を兼ねている（D-21）。
> **M1・M2 が主題**であり、**M2 完了時点でPoCは完成する。**
>
> ★ **M5 を終えた時点で、このバックログ自体をこのアプリで管理できる状態になる。**
> そこから先はドッグフーディングで進める。

### 進め方（D-21）

順序の要点は**認証と認可をデータ層の要否で分けている**こと。認証はDBを必要とせず、
ローカルだけで検証できる。**PoCの核心に最短で到達できる。**

```
M1 認証PoC   B-01 骨格(1ページ) → B-02 Entra登録 → B-03/B-04 認証
                                → B-05/B-06 でデプロイして公開URLでも確認
M2 認可PoC   B-07 データ層 → B-08 マイグレーション → B-09 認可 → B-10 ブートストラップ
M3 土台      テスト基盤・API規約（スクラム機能を作り込む前に）
M4〜 アプリ本体
```

PoC自体を無検証で進めないため、**V-1〜V-4 のテストは B-04 の完了条件に含め**、
テスト基盤の全体構築（B-11）を待たない。

---

## 着手前に必ず方針を決める（Open Questions）

| # | 論点 | 対応PBI | いつまでに |
|:---:|:---|:---:|:---|
| ~~Q-A~~ | ~~テスト戦略~~ → **決定済み** [`D-19`](./decisions/D-19-test-strategy.md) | B-11 | ✅ 2026-07-25 |
| ~~Q-B~~ | ~~`productId` の発生源とseeding~~ → **決定済み** [`D-21`](./decisions/D-21-bootstrap-and-migration.md) | B-08 | ✅ 2026-07-25 |
| ~~Q-C~~ | ~~認可ブートストラップ~~ → **決定済み** [`D-21`](./decisions/D-21-bootstrap-and-migration.md) | B-10 | ✅ 2026-07-25 |
| ~~Q-D~~ | ~~API共通規約~~ → **決定済み** [`D-20`](./decisions/D-20-api-conventions.md) | B-12 | ✅ 2026-07-25 |
| ~~Q-E~~ | ~~Cosmos の `ORDER BY` が辞書順と一致するか（提案書 Q-1）~~ → **検証済み**（実サービスで `ORDER BY rank, id` が序数順と一致することを確認。方式切替は不要） | B-16 | ✅ 2026-08-01 |
| ~~Q-F~~ | ~~楽観排他 412 発生後のUX（再取得マージ／再操作促し）~~ → **決定済み** [`D-24`](./decisions/D-24-optimistic-concurrency-ux.md)（再操作を促す＋即時再取得。自動マージは採らない・412 本文に最新値を含めない） | B-26 | ✅ 2026-08-06 |

**🔴 Blocker はすべて解消済み。** Q-E・Q-F とも解消済みで、**B-23 に着手できる。**

### 決定の記録

方針が固まったものは `docs/decisions/` に残す。提案書10章の **D-シリーズを継続**しており、
番号空間は1つ（提案書が「仕様を変更したくなったら、まずこの表を引く」と定めているため）。

| # | 決定 | 対応PBI |
|:---:|:---|:---:|
| [D-19](./decisions/D-19-test-strategy.md) | テスト戦略とCI基盤（4層構成・エミュレータ・カバレッジ方針） | B-11 |
| [D-20](./decisions/D-20-api-conventions.md) | API共通規約（読み書き非対称・RFC 9457・`If-Match`必須・型生成） | B-12 |
| [D-21](./decisions/D-21-bootstrap-and-migration.md) | マイグレーション・ユーザー登録・**認証の実装順序** | B-08, B-10, B-14 |
| [D-22](./decisions/D-22-e2e-execution.md) | E2E をヘッドレス CI で緑にする実行方式（env ゲートのテスト用リゾルバ＋e2e ビルド＋エミュレータ隔離） | EX-1 |
| [D-23](./decisions/D-23-coverage-comment.md) | カバレッジ PR コメントを「事実」に刷新（数値ゲートなし・base 差分 Δ・未カバーの変更行を名指し。D-19 順守） | EX-2 |
| [D-24](./decisions/D-24-optimistic-concurrency-ux.md) | 楽観排他 412 発生後の UX（再操作を促す＋即時再取得・自動マージ却下・412 本文に最新値を含めない。P-1 順守） | B-26, B-23 |
| [D-25](./decisions/D-25-business-days-and-timezone.md) | 進捗マーカーの営業日の定義とタイムゾーン（土日＋**日本の祝日**を除外・`jpholiday` 委譲・「今日」は **Asia/Tokyo** の暦日・注入可能。P-1/P-2 順守） | B-24 |
| [D-26](./decisions/D-26-sprint-close.md) | スプリント終了処理（未完了だけを**指定した次スプリント**へ持ち越し・完了は凍結 I-5・`close/preview` と `close` を分ける・締められるのは active だけ・`If-Match` を取らないサーバー所有操作。P-1/D-20 順守） | B-25 |
| [D-27](./decisions/D-27-daily-note.md) | デイリーノートのキーと取得（**1日1件**を決定的 ID `dly_<sprintId>_<date>` で構造的に担保・`GET` は **get-or-create**・編集は `PATCH`＋`If-Match`・日付は期間で縛らない。P-1/D-20/D-21 順守） | B-27 |

---

## M1 — 1ページがEntra IDで保護される ★PoCの核心　✅ 達成（2026-07-26）

> 🎉 **M1 達成。** 公開URL `https://scrum-board-yoga.azurewebsites.net` で、Easy Auth を使わず
> Entra ID のサインイン → MSAL がアクセストークンを付与 → API が検証（V-1〜V-4）→ 画面に `oid` 表示、
> まで**端から端まで疎通**した。**認証 PoC は点灯済み。** 次は M2（認可）で PoC を完成させる。
>
> ★**本プロジェクトの主題。** 認証はデータ層を必要としないため、ここまでCosmosもマイグレーションも要らない。
> ローカル（`localhost:4200`）で検証してから、B-05/B-06 でデプロイし公開URLでも確認する。

### ✅ B-01 プロジェクトの骨格を作る　`依存: —`
- [x] Angular のビルド成果物を FastAPI が配信する（`backend/app/main.py` が `frontend/dist` を配信）
- [x] フロントとAPIが同一 App Service に同居する構成（単一オリジン・CORS不要。`/api` はバックエンド、それ以外はSPA）
- [x] ローカルで1コマンド起動できる（`make run` = ビルド＋配信 / `make dev` = ライブリロード）
- [x] **画面が1ページ表示される**（`/` にランディングページ。`/api/health` の疎通も表示）

### ✅ B-02 Entra IDにアプリを登録する　`依存: —`
> **実テナントで登録完了（2026-07-26）。** 公開URLでのサインインが端から端まで通り
> （B-03/B-04）、下の各項目は実疎通で裏取りできた。`accessTokenVersion: 2`・
> `access_as_user` スコープ・`api://<clientId>` は `az ad app show` でも確認済み。
> 手順書 [`docs/setup/entra-app-registration.md`](./setup/entra-app-registration.md)＋
> [`scripts/setup/register-entra-app.sh`](../scripts/setup/register-entra-app.sh) で再実行可能。

- [x] 提案書 08章のチェックリスト全項目が完了
- [x] プラットフォーム = **シングルページアプリケーション**（`AADSTS9002326` は出ていない）
- [x] スコープ `api://<clientId>/access_as_user` を公開
- [x] マニフェスト `requestedAccessTokenVersion: 2`
- [x] リダイレクトURI を登録（本番SPA `https://scrum-board-yoga.azurewebsites.net` / `localhost:4200`）
- [x] テナントID・クライアントIDを控えた
- [x] **手順が再実行可能な形（az CLI中心）で残っている**

### ✅ B-03 フロントエンドのサインイン　`依存: B-02, B-01`
> **完了（2026-07-26）。公開URLで実際にサインインが通ることを確認済み。**
> `environment.ts` に B-02 の実値を設定し、`protectedResourceMap` を `/api/*` に修正して
> （MSAL v5 の strict matching 対策）API へトークンが載ることを実機で確認した。
- [x] MSAL でサインインできる（`@azure/msal-angular` を配線。リダイレクト方式・PKCE）　※公開URLで実疎通確認済み
- [x] **未認証ユーザーはルートガードで弾かれる**（`MsalGuard` を唯一のルート `''` に適用）
- [x] ローカルでも本番と同じ経路で動く（**Easy Auth に依存しない** — D-10。`redirectUri` を `window.location.origin` から導出）
- [x] `/api/*` への発信に Bearer アクセストークンを付与（`MsalInterceptor`。→ B-04 と対になる）
- [x] サインイン状態を `AuthService` の1か所に集約（画面は MSAL を直接触らない・テスト差し替え可能）
- [x] タブを開き直したときのサインイン状態の**無音復元**（`ssoSilent`）。トークンは `sessionStorage` 限定のまま、復元は Entra 側のブラウザセッションに委ねる（有効期間は組織の Entra ポリシー次第）

### ✅ B-04 APIのトークン検証　`依存: B-02, B-01`
> **完了（2026-07-26）。実 Entra トークンで端から端まで疎通確認済み**
> （公開URLでサインイン → `GET /api/me` が検証した `oid` を画面に表示）。
> トークン検証（V-1〜V-4）・ユーザー解決ポート・`GET /api/me` を配線し、テスト鍵ペア＋
> JWKSスタブでも検証済み（`make test-backend` / `make test-frontend`）。
> 所属プロダクト一覧を含む完全な `/api/me`（D-21）はデータ層が要るため B-10 で足す。
- [x] V-1 署名検証（JWKSの公開鍵でRS256・鍵はキャッシュ）　`app/auth/jwks.py`・`token.py`
- [x] V-2 `aud` がクライアントIDと一致　`app/auth/token.py`（`jwt.decode(audience=…)`）
- [x] V-3 `iss` が `https://login.microsoftonline.com/<tenantId>/v2.0`　`app/auth/settings.py`
- [x] V-4 `scp` に `access_as_user` が含まれる　`app/auth/token.py`
- [x] 改ざんトークンで 401 を返す（`InvalidTokenError → 401` + `WWW-Authenticate: Bearer`）
- [x] **V-1〜V-4 のテストが書かれている**（`tests/auth/`。実テナントに繋がずテスト鍵で検証。B-11 を待たない）
- [x] **ユーザー解決がポートとして切り出されている**（`CurrentUserResolver`。テストは `dependency_overrides` で差し替え — D-21）
- [x] サインイン後、**APIが検証した `oid` が画面に表示される**（`GET /api/me` → home の「API が検証した oid」）　※公開URLで実疎通確認済み

### ✅ B-05 Azureリソースを用意する　`依存: —`
> **実リソース作成まで完了（2026-07-26）。** 再実行可能な az CLI スクリプト
> （[`scripts/setup/provision-azure.sh`](../scripts/setup/provision-azure.sh)）と
> 手順書（[`docs/setup/azure-resources.md`](./setup/azure-resources.md)）で、App Service F1・
> Cosmos DB 無料レベル・予算アラートを冪等に構築した。
> 実構成: **App Service `scrum-board-yoga`（japanwest）/ Cosmos `cosmos-scrum-board`（japaneast）**。
> 公開URL `https://scrum-board-yoga.azurewebsites.net`。
> （japaneast は F1 の VM 枠 0、japanwest は Cosmos が容量不足だったため、リージョンを分けて回避。
> スクリプトは `AZ_LOCATION` / `AZ_COSMOS_LOCATION` で個別指定できる。）
- [x] App Service F1 を作成
- [x] Cosmos DB **無料レベル**を明示的に選択して作成（`--enable-free-tier true`）
- [x] **予算アラートを設定した**（Azureは自動の支出上限がない。50/80/100% 通知）
- [x] 手順が再実行可能な形で残っている（az CLI 中心・冪等。GUI 限定部分だけ手順書で補足）

### ✅ B-06 デプロイパイプラインを通す　`依存: B-05, B-01`
> **完了（2026-07-26）。公開URLで動作確認済み。** main への push で SPA ビルド → 依存書き出し
> → 単一パッケージで App Service へ zip デプロイ（[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)）。
> 認証は**シークレットレス（OIDC）**（[`scripts/setup/setup-github-oidc.sh`](../scripts/setup/setup-github-oidc.sh)）。
> 手順は [`docs/setup/deploy.md`](./setup/deploy.md)。
>
> 立ち上げ時に潰した実地の壁（記録）: OIDC の subject が ID 入り形式（FIC を実 subject に合わせて追加）／
> Oryx が成果物を `output.tar.zst` に圧縮するため SPA は app からの相対解決に変更／
> フロントの Entra 実値をビルド時に埋め込む／`protectedResourceMap` を `/api/*`（MSAL v5 strict matching）。
>
> ⚠️ **現在プランは B1**（Basic）。当初 F1 で日次クォータ超過（`QuotaExceeded`）になり、検証を通すため
> スケールアップした（$100 クレジット内。1週間 B1 ≈ $3）。日次クォータがリセットされた後に
> `az appservice plan update --sku F1` で F1 へ戻せる（B-31 の実測時に判断）。
- [x] main への push で App Service に自動デプロイされる
- [x] 公開URLで表示できる（`/api/health` スモークテストも緑）
- [x] **公開URLでもサインインが通る**（本番リダイレクトURI確認・oid 表示まで到達）

---

## M2 — 認可まで通る ★PoC完成　✅ 達成（2026-07-26）

> 🎉 **M2 達成。★本プロジェクトの主題（Easy Auth を使わない Entra ID の認証・認可 PoC）が
> ここで完成した。** データ層（B-07）→ マイグレーション（B-08）→ 認可（B-09）→
> ブートストラップ（B-10）まで積み上がり、**サインイン → 初回サインインで user と
> サンドボックス member を自動作成 → 所属プロダクト一覧を `/api/me` が返す → 非メンバーは
> 403** が端から端まで通った。**403 で詰まる経路は無い**（サインインできた人には必ず
> サンドボックスという居場所がある）。本番プロジェクトへは権限を緩めず、`scripts/add_member.py`
> で明示登録する。**次は M3（開発の土台）からアプリ本体の作り込みに移る。**

### ✅ B-07 データアクセス基盤　`依存: B-05`
> **完了（2026-07-26）。** `backend/app/data/` にデータアクセス基盤を実装。
> **Repository をポート**（`repository.py`）として切り出し、層1・2用の
> `InMemoryRepository`（`fake.py`）と本番 `CosmosRepository`（`cosmos.py`）を
> 同一契約で差し替えられる（D-19）。共通フィールド付与（`documents.py` の
> `stamp_new` / `stamp_update`）・論理削除の除外・`_etag` 楽観排他を**両実装が
> 同じ関数／同じ SQL 生成を通して**一元化し、実装ごとにずれない。ポートは
> `get`/`query` に削除済みを読む経路を提供せず、`replace`/`soft_delete` は
> `if_match` を**必須引数**にして無条件更新を型で塞ぐ（D-20）。
> コンテナ作成は `provisioning.ensure_container`（冪等）で PK `/productId` ＋
> 除外パスを設定する。契約テスト（フェイク）・ULID・stamping・除外パスを
> `tests/data/` で検証（`make test-backend` 緑・56件）。実 Cosmos に依存する
> 412／バッチ原子性／RU 実測は層3（B-11）と実サービス（B-31）に回す。
> `CosmosClient` は **アプリのライフタイムで1個だけ**生成して使い回す（コネクション
> プールはクライアントが内部で共有・シングルトン）。`main.py` の lifespan がクライアントを
> 所有し shutdown で `close()` する器を先に用意（未構成なら DB 無しで起動）。実配線は B-09 以降。
- [x] 単一コンテナを作成（PK `/productId`）　`app/data/provisioning.py`（`create_container_if_not_exists`）
- [x] インデックス除外パス（`description` `memo` `minutes`）を設定　`container_indexing_policy()`
- [x] 共通フィールド付与（id=ULID / type / createdAt 等）が共通処理として動く　`documents.stamp_new`・`ids.new_id`
- [x] 論理削除（`isDeleted`）と、**全クエリでの `NOT isDeleted` 除外**を共通化した（`get`/`query` が構造的に除外・`soft_delete` は物理削除しない）
- [x] `_etag` による楽観排他（`If-Match` / 412再取得）が共通処理として動く（`replace`/`soft_delete` の `if_match` 必須・不一致は `PreconditionFailedError`=412）
- [x] **Repositoryがポートとして抽象化され、テスト用フェイクに差し替えられる**（D-19）　`repository.Repository` / `fake.InMemoryRepository` / `cosmos.CosmosRepository`

### ✅ B-08 マイグレーション機構と初期データ　`依存: B-07`
> **完了（2026-07-26）。** `backend/app/data/migrations/` にマイグレーション機構を実装。
> 適用済みバージョンを `_system` に `mig_<version>`（`version` / `appliedAt`）として
> 記録し、未適用のものだけを **version 昇順**に適用する（`runner.run_migrations`）。
> 冪等性は「`ensure` を毎起動」ではなく**バージョン記録で担保**し、再デプロイでは何も
> 起きない（実データを設定値で上書きしない — D-21）。各マイグレーションは `mNNN_*.py`
> に分け、`MIGRATIONS` タプルで束ねる（`001` サンドボックス・`002` 本番）。**`member` と
> `user` は作らない**（権限はスクリプトで明示的に、`user` は初回サインインで）。
> `_system` の予約語チェックは `products.create_product` に一元化し、マイグレーションと
> 将来の B-32 が同じ関門を通る（払い出そうとすると `ReservedProductIdError`=422）。
> `main.py` の lifespan がコンテナ用意（B-07）の直後に適用する。フェイク Repository で
> 契約を検証（`make test-backend` 緑・69件）。実 Cosmos への適用は B-31 / E2E（B-11）で。
- [x] 未適用のマイグレーションだけが順に適用される　`migrations/runner.py`（`applied_versions` で既適用を除外・`version` 昇順）
- [x] 適用後に `_system` パーティションへ `mig_<version>` が記録される（`version` / `appliedAt`。適用**後**に記録）
- [x] サンドボックス（`prd_sandbox`）と本番（`prd_scrum_board`）の `product` が作成される　`m001` / `m002`
- [x] マイグレーションは **`member` と `user` を作らない**（権限は明示的に、userは初回サインインで）
- [x] **`_system` が productId として払い出されない**（予約語チェック）　`products.is_reserved_product_id` / `create_product`

### ✅ B-09 メンバー管理と認可　`依存: B-04, B-07`
> **完了（2026-07-26）。** `member` を認可の土台として切り出した。データ層に
> `app/data/members.py`（`Role`＝admin/member の2種・`member_id(oid)`＝`mbr_<oid>`・
> `get_member`/`is_member`/`create_member`）を置き、認可の判断は `app/authz.py` の
> **`require_member` 依存**に一元化した。product スコープのエンドポイント
> （`/api/products/{product_id}/…`・D-20）はこれに依存するだけで、認証済みだが
> member でないユーザーを **403** で弾ける（`if not member:` を各ハンドラに撒かない）。
> `current_user` が 401 を先に処理し、ここは 403 に振り分ける。判定は
> **`mbr_<oid>` のポイントリード1件**（約1 RU・クロスパーティションクエリなし — D-21）。
> `Membership` に `role` を載せ、管理操作だけを絞る将来のチェック（B-33）を member の
> 再取得なしに書けるようにした。本番の product エンドポイント配線は B-15 以降のため、
> テスト専用 probe ルートで 非メンバー403・パーティション境界・401優先・DB未構成503 を
> 端から端まで検証（`make test-backend` 緑・82件）。自動作成（初回サインイン）と
> 本番登録スクリプトは B-10。
- [x] プロダクトのメンバーでないユーザーは 403　`app/authz.py`（`require_member` → 403）
- [x] ユーザー識別子に `oid` を使っている（メールアドレスをキーにしない）　`member.userId == oid` / `id=mbr_<oid>`
- [x] **`id=mbr_<oid>` によりポイントリード1件で判定する**（D-21）　`members.member_id` / `get_member`（`repo.get` 1件）

### ✅ B-10 ユーザー登録と認可ブートストラップ　`依存: B-09, B-08`
> **完了（2026-07-26）。** サンドボックスを一枚挟み、権限を緩めずに鶏卵問題を解いた（D-21）。
> `user` を `app/data/users.py`（`_system` の `usr_<oid>`・ポイントリード）に、初回サインインの
> ブートストラップを `app/onboarding.py` の **`ensure_bootstrapped`** に切り出した。`GET /api/me`
> はこれを毎回呼び（冪等・409 は握りつぶす）、user とサンドボックス member を無ければ作る。
> これで **「サインインできた人には必ず居場所がある」＝ 403 で詰まる経路が無い**。所属一覧は
> `member` を横断で集める **`query_across_partitions`**（ポートに追加。RU が高いので用途を
> 「セッション開始時に一度きり・小件数」に限る — 認可の点判定は従来どおりポイントリード）で
> 集め、表示名を解決して productId 昇順で返す。`/api/me` は DB を触るため `def` で書き
> スレッドプールに逃がす（最初の DB 依存エンドポイント）。DB 未構成でも認証だけは成立させたい
> ため（M1 の認証 PoC は Cosmos 不要）、リポジトリが無ければ 503 にせず所属を空一覧にする。
> 本番登録は `scripts/add_member.py`（**再実行可能**・`upsert_member` で作成 or role 更新・
> productId の存在チェック）。フロントは `ProductService`（純粋な状態ホルダー）＋セレクタで
> 切り替え、productId をハードコードしない（2画面原則は維持）。`make test`（pytest 110 件・
> Karma 25 件）緑。実 Cosmos でのクロスパーティション RU 実測は B-31／E2E（B-11）へ。

- [x] 初回サインインで `user`（`_system` の `usr_<oid>`）が作られる　`app/onboarding.py`（`ensure_bootstrapped`）／`app/data/users.py`
- [x] 同時に **サンドボックスへ `member`（role=member）が作られる**　`_ensure_sandbox_membership`（`SANDBOX_PRODUCT_ID`）
- [x] **403で詰まる経路が存在しない**（サインインできた人には必ず居場所がある）　`/api/me` が毎回ブートストラップ
- [x] 同時サインインの競合（id重複の409）が握りつぶされる　`ConflictError` を捕捉（create-if-absent）
- [x] 本番プロジェクトへの登録が**再実行可能なスクリプト**で行える（既存なら role 更新）　`scripts/add_member.py`／`members.upsert_member`
- [x] `GET /api/me` が所属プロダクト一覧を返し、フロントが `productId` をハードコードしない　`onboarding.list_products`／`ProductService`
- [x] プロダクトセレクタで切り替えられる（**2画面原則は維持される**）　`frontend/src/app/products/product.service.ts` ＋ home のセレクタ

---

---

## M3 — 開発の土台

> スクラム機能を作り込む前に固める。**PoC（M1・M2）は先に済んでいる**ため、
> ここでのテスト基盤はアプリ本体の退行検知に向けたものになる。

### ✅ B-11 テスト戦略とCI基盤の確立　`依存: B-01`
> **方針決定済み** → [`D-19`](./decisions/D-19-test-strategy.md)
> pytest / Vitest / Playwright。Cosmos契約テストはエミュレータ、
> **照合順序の検証だけは実サービス**（B-16）。カバレッジは数値目標を置かない。
>
> **完了（2026-08-01）。テスト戦略とハーネスを確立した。** フロントを Karma→**Vitest**（jsdom）へ
> 移行し、I-1〜I-7 のテーブル駆動雛形・Cosmos 契約（層3）ハーネス＋**ready ポーリング**CI・
> Playwright 主要5フローの受け皿・ブランチ保護手順書を整えた。振る舞い検査は B-20 で有効化済み。
> このPBIの範囲は**戦略とハーネス（受け皿）の確立**であり、それは満たした。**E2E を CI で実際に
> 緑にする実行面の整備**（5本共通のサインイン経路・`webServer`・seeding）は、どの機能PBIにも
> 属さない横断課題のため、独立した横断PBI **EX-1** に切り出して集約した
> （マージブロックは B-13 で回収済み）。宙に浮かせず帰属を明確にしたうえでここを閉じる。

- [x] pytest（層1・2）と Vitest（フロント単体）が導入され、1コマンドで走る　`make test`
- [x] **層1・2が Cosmos なしで走る**（Repositoryフェイクを使用 → B-07 と対で実施）
- [x] 不変条件 I-1〜I-7 の**テーブル駆動**テスト雛形がある　`backend/tests/invariants/`（表の自己検査は稼働・振る舞い検査は B-20 で有効化）
- [x] V-1〜V-4 をテスト用鍵ペア＋JWKSスタブで検証している（実テナントに接続しない）　`backend/tests/auth/`（B-04 で実施済み）
- [x] Cosmos契約テスト（412／バッチ原子性／RU）が**エミュレータ上で走る導線がある**　`backend/tests/contract/`＋CI `cosmos-contract`（412・除外パスは実装済み／バッチは雛形。初回CIで実緑を確認）
- [x] エミュレータの起動待ちが**固定sleepではなくreadyポーリング**である　`ci.yml`（証明書エンドポイントを poll）
- [x] Playwright で主要フロー5本の**受け皿（ハーネス）を用意する**　→ 受け皿5本は `frontend/e2e/`（`test.fixme`）。各フローの本体は担当PBIで書く（①B-17/B-20 ②B-22 ③B-23 ④B-25 ⑤B-29）。**CI で実際に緑にする実行面の整備（共通サインイン経路・`webServer`・seeding）は横断PBI EX-1 に集約**（機能PBIに属さないため）
- [x] GitHub Actions で毎PR実行される　→ 毎PR実行は稼働。**マージブロック（ブランチ保護・管理者操作）は B-13 の完了条件に載せ直し、そこで有効化済み** [`docs/setup/ci-branch-protection.md`](./setup/ci-branch-protection.md)
- [x] 必須4領域（I-1〜I-7／V-1〜V-4／rank／認可）の合意が文書化されている　[`D-19`](./decisions/D-19-test-strategy.md#カバレッジ方針)

> **B-11 の範囲は「戦略とハーネスの確立」で、それは満たした。** 単独では閉じられない性質の
> 作業は**宙に浮かせず帰属を移した**: (1) E2E を CI で緑にする実行面の整備（5本共通のサインイン
> 経路・`webServer`・seeding）→ 横断PBI **EX-1**、(2) マージブロック
> （ブランチ保護）→ **B-13**（有効化済み）、(3) 不変条件の振る舞い検査 → **B-20**（有効化済み）。
> 各フローの本体は対象画面が揃う各PBI（①B-17/B-20 ②B-22 ③B-23 ④B-25 ⑤B-29）が書き、
> `test.fixme` 解除は EX-1 の共通サインイン経路の上で行う。

### ✅ B-12 API共通規約の策定　`依存: B-04`
> **完了（2026-07-26）。** HTTP 境界の約束事を `backend/app/http/` に一手に集約した。
> 個々の CRUD（B-15 以降）は、規約を書き散らさずここの部品に依存するだけで済む
> （認可を各ハンドラの `if` ではなく依存で表したのと同じ発想）。
> エラー翻訳は**唯一の翻訳点** `app/http/handlers.py` に集約し、`ProblemException`・
> データ層 `DataError`（`http_status` で振り分け）・`RequestValidationError`・既存の
> `HTTPException` の 4 系統を RFC 9457 problem+json に揃える（素の `{"detail": ...}` と
> 混在しない）。`violations`（`app/http/problems.py` の `Violation`）で**どの不変条件で
> 弾いたか**を機械可読にし、D-19 のテーブル駆動テストが偽陽性（`I-4` を意図した入力が
> `I-3` で弾かれて通る）を防げる。`If-Match` は `require_if_match` 依存で必須にし、欠落は
> 既存 `PreconditionRequiredError` を再利用して **428**（不一致 412 はデータ層が投げる）。
> OpenAPI を単一の真実とし、`app.openapi` を差し替えて `Problem`/`Violation` を必ず
> components に載せ、`openapi-typescript` で `frontend/src/app/api/schema.d.ts` を生成
> （`make gen-types`）・コミットし、**CI の独立ジョブ `types` が再生成して差分を検出**する
> （生成し忘れを弾く）。テストは problem+json の形／ステータス割当／violations／428・ETag
> 往復／OpenAPI 注入を probe ルートで端から端まで検証（`make test-backend` 緑・125 件）。
> 本番の product エンドポイントへの適用は B-15 以降（`problem_responses()` を `responses`
> に展開して宣言する）。

- [x] RFC 9457（`application/problem+json`）が共通のエラー応答として動く　`app/http/handlers.py`（`install_error_handlers`）
- [x] `violations` に**不変条件ID（I-4 等）が機械可読で載る**　`app/http/problems.py`（`Violation` / `InvariantViolation`）
- [x] ステータスコードの割当（401 / 403 / 404 / 409 / **412** / **428** / 422）が実装されている　`STATUS_PROBLEMS` ＋各ハンドラ
- [x] `PATCH`/`DELETE` で **`If-Match` 欠落を428で弾く**（無条件更新の経路が存在しない）　`app/http/preconditions.py`（`require_if_match`）
- [x] 単一ドキュメント応答が `ETag` を返し、集約GETは各要素に `_etag` を含む　`set_etag` ／ `_etag` は B-07 が全 doc に付与
- [x] **サーバーを信頼境界とする**と明記（フロントのバリデーションはUX補助、正はAPI）　`app/http/__init__.py` の docstring ＋ D-20
- [x] OpenAPI から TS型を生成し、**CIで生成物の差分を検出**する　`scripts/gen_openapi.py` ／ `make gen-types` ／ CI ジョブ `types`
- [x] クエリ規約（論理削除は常時除外・ページングなし・`ORDER BY rank, id` はサーバー保証）　B-07 のポートが構造的に保証（`DEFAULT_ORDER=(rank,id)`・`NOT isDeleted`・ページングなし）

### ✅ B-13 リポジトリ規約の整備　`依存: —`
> **完了（2026-07-28）。** MIT の `LICENSE`（著作権者 y-oga-819）を配置し、
> `CONTRIBUTING.md` に**開発の流れ・ブランチ戦略・コミットメッセージ規約・品質ゲート・
> PR の書き方**を集約した（AI 向けの `CLAUDE.md` と規約を一致させ、二重管理にしない）。
> README からセットアップ手順に加えて CONTRIBUTING とライセンスへ導線を張った。
> **`main` のブランチ保護を有効化し、必須チェック（Backend / Frontend / Types / E2E）が
> 緑でなければマージできない**状態にした（B-11 の申し送りをここで回収。手順
> [`docs/setup/ci-branch-protection.md`](./setup/ci-branch-protection.md)）。
- [x] LICENSE を配置した　MIT・`LICENSE`（Copyright 2026 y-oga-819）
- [x] README に開発セットアップ手順を書いた　`README.md`（`make install`/`dev`/`run`/`test` ＋ 開発への参加・ライセンス節）
- [x] コミットメッセージ規約・ブランチ戦略を決めた　`CONTRIBUTING.md`（Conventional Commits 風／`main` 保護・短命ブランチ・PR）
- [x] CONTRIBUTING（または開発ガイド）を用意した　`CONTRIBUTING.md`
- [x] **ブランチ保護を有効化し、CI 失敗でマージがブロックされる**（`main` の必須チェックに Backend / Frontend / Types / E2E を指定。手順 [`docs/setup/ci-branch-protection.md`](./setup/ci-branch-protection.md)）

---

### ⬜ B-14 ゲストログイン経路　`依存: B-04, B-08`　🔸**任意**
> **方針決定済み** → [`D-21`](./decisions/D-21-bootstrap-and-migration.md)
> 当初は「認証を待たずに画面開発を始める」ための仕組みだったが、**認証を先に作る順序に
> 変えたため存在理由が消えた**。残る価値は「開発時に毎回サインインしなくてよい」という
> 利便性のみ。**不要なら落としてよい。**

- [ ] 開発時に**サインインを省略してサンドボックスを操作できる**
- [ ] B-04のユーザー解決ポートに**実装をもう1つ足すだけ**で実現している
- [ ] **`if guest:` の分岐がAPIハンドラに存在しない**
- [ ] ゲストは**本番プロジェクトにアクセスできない**（サンドボックス限定）
- [ ] 環境変数で制御され、**本番では既定でOFF**
- [ ] `GET /api/me` がゲストでも動き、実ユーザーと**同じ形**を返す（`isGuest` を含む）

---

### ✅ EX-1 E2E 整備（横断・番号外）　`依存: B-11, 各フローの対象画面`
> **横断PBI（着手順の B-NN とは別枠。採番の対応表・付録を参照）。** D-19 の層4（Playwright
> E2E）を「受け皿がある」から「**CI で実際に緑になる**」まで持っていく実行面の整備を 1 か所に
> 集約する。個々のフロー本体は担当PBIが書く（①B-17/B-20 は実装済み・②B-22 ③B-23 ④B-25
> ⑤B-29）が、**5本すべてに共通する土台**——ヘッドレスのサインイン経路・app 起動（`webServer`）・
> 既知の初期状態（seeding）——はどの機能PBIにも属さないため、ここで面倒を見る。B-11 は
> 「テスト戦略とハーネスの確立」で完結させ、実行面の整備は本PBIが担う（B-11 を閉じるための
> 受け皿）。
>
> **まず着手できる範囲**（対象画面が既にある①）から緑にし、②〜⑤は各担当PBIが本PBIの共通
> サインイン経路の上で `test.fixme` を外す。**着手前にサインイン経路の方式**（テスト用トークン
> 注入 or 開発用サインイン省略 B-14）を決める（決めたら `docs/decisions` に残す）。
>
> **完了（2026-08-02）。共通の実行基盤を用意し、フロー①を CI で緑にした。** サインイン方式は
> [`D-22`](./decisions/D-22-e2e-execution.md) に記録した——実サーバ+実ブラウザでは
> `dependency_overrides` が効かないため、バックエンドは env ゲートのテスト用 resolver
> （既定 OFF・fail-closed）、フロントは e2e ビルドで MSAL を無効化する。既知の初期状態は
> Cosmos エミュレータへマイグレーション全適用のうえ `prd_test_<runId>` を seeding し（`prd_test_`
> 以外は拒否・teardown は物理削除。D-21）、`webServer` で e2e SPA + FastAPI を起動して回す。
> ②〜⑤の `test.fixme` 外しはこの共通基盤の上で各担当PBIが行う（本PBIは基盤を提供し続ける）。

- [x] **ヘッドレスのサインイン経路**を決めて実装した（env ゲートのテスト用 resolver + フロント e2e ビルドで MSAL 無効化。CI で対話サインインなしに通る。方式は [`D-22`](./decisions/D-22-e2e-execution.md) に記録）
- [x] `playwright.config.ts` の `webServer` を有効化し、app を起動して E2E を回す導線を通した（`make run-e2e`）
- [x] **既知の初期状態**を seeding で毎回作り直せる（`prd_test_<runId>` に投入 → 物理削除。`scripts/e2e_seed.py` / `e2e_teardown.py`・globalSetup/globalTeardown。D-19/D-21）
- [x] **E2E フロー①を CI で緑にする**（`frontend/e2e/signin-pbi-task.spec.ts` の `test.fixme` を外した。本体は B-20 実装済み・対象画面は B-17/B-20 で存在）
- [x] 残りフロー②〜⑤が本PBIの共通サインイン経路の上で `test.fixme` を外せる状態にした（対象画面が揃い次第、各担当PBI B-22/B-23/B-25/B-29 で外す。本PBIは共通基盤を提供し続ける）
- [x] E2E は **毎 PR（マージ前ゲート）**で回る（main への push でデプロイするため、マージ後では壊れた本番を作ってから気づくことになりゲートにならない — D-19 改定・`e2e.yml`）

### ✅ EX-2 カバレッジ PR コメントの刷新（横断・番号外）　`依存: B-11`
> **横断PBI（着手順の B-NN とは別枠）。** 従来のカバレッジコメントは「今このPRの絶対値」
> だけを貼っており、受け手は「元の状態はどうで、今回どう変わって、次に何をすればいいのか」を
> 読み取れなかった。**事実を見せ、判断は書き手に返す**（D-19 の P-1）方針を、コメントの
> 情報設計にも適用する。
>
> **完了（2026-08-02）。** 数値ゲート（率の下限・Pass/Fail・ビルド失敗）は **置かない**
> ——D-19 が明示的に却下した「カバレッジ率に下限を設ける」に当たるため。代わりに受け手が
> 行動できる 2 つの**事実**だけを出す：**(1) base(main) からの Δ**（元の状態→変化）と、
> **(2) 未カバーの変更行の名指し**（このPRで変更したのにテストが通っていない行＝次の一手）。
> 設計判断は [`D-23`](./decisions/D-23-coverage-comment.md) に記録した。集計は stdlib のみの
> Python ツール（`scripts/coverage/report.py`）に集約し、base は外部SaaS・サードパーティ
> action に依存せず**自前の artifact**（直近 main run）から取る。

- [x] **数値ゲートを入れない**（率の下限・Pass/Fail・ビルド失敗なし。D-19 の「率に下限を設ける」却下を順守。判断は書き手に返す）
- [x] **base(main) からの Δ を出す**（元の状態→変化。main への push でレポート JSON を artifact 化し、PR では直近 main run から取得して比較。初回は「初回」表示にフォールバック）
- [x] **未カバーの変更行を名指しで列挙する**（`git diff base...HEAD` の追加行 ∩ 行単位カバレッジ。率ではなく「どこにテストを足せるか」を行番号で示す）
- [x] 集計ロジックを **stdlib のみの Python ツール**に集約し、`unittest` で検証（`scripts/coverage/`。`make test-scripts` と CI で実行。ubuntu-latest の `python3` で uv 不要）
- [x] frontend の行単位カバレッジ源として istanbul `json` レポーターを追加（`angular.json`）。ビルド出力パス（`dist/test-out/<ts>/src/…`）をソース（`frontend/src/…`）へ写像して差分と突き合わせる

---

---

## M4 — プロダクトバックログが運用できる

### ✅ B-15 PBIのCRUD API　`依存: B-04, B-07`
> **完了（2026-07-28）。M4 の最初のリソース CRUD。** M4 以降でリソースごとの CRUD
> ルータが増える前に、`app/api.py` を **`app/api/` パッケージ**へ切り出した（横断ルート
> は `api/meta.py`・PBI は `api/pbis.py`。`main.py` はルータ群を順に include するだけ）。
> ドメイン規則（状態の語彙 `PbiStatus` と正当な遷移 `is_valid_transition`）は
> **データ層の純関数**（`app/data/pbis.py`）に一元化し、HTTP への翻訳（422・`violations`）
> だけを API 層に置いた（データ層は HTTP を知らない）。エンドポイントは B-09 の
> `require_member` に依存するだけで **非メンバー 403**、B-12 の `require_if_match` で
> **`If-Match` を構造的に必須**にし、`problem_responses` で RFC 9457 応答を OpenAPI に
> 宣言した（規約をハンドラに書き散らさない — D-20）。単一ドキュメント応答は `ETag` を
> ヘッダで返し、本文に `_etag` は載せない（集約 GET の各要素返却は B-17）。`PbiUpdate` は
> `rank`／`parentPbiId`／`completedAt`／`completedSprintId` を持たず、それらの規則を
> 汎用 `PATCH` に漏らさない（採番＝B-16・分割＝B-19・完了地の刻印＝B-25 が所有）。
> フェイク Repository で作成→取得→更新→論理削除・状態遷移・412／428・パーティション
> 境界を端から端まで検証し、OpenAPI から `schema.d.ts` を再生成した
> （`make test` 緑・pytest 171 件／Vitest／`make lint`／`make typecheck` 緑）。実 Cosmos
> での往復は層3（B-11）と実サービス（B-31）へ。
- [x] 作成・取得・更新・論理削除ができる　`app/api/pbis.py`（POST/GET/PATCH/DELETE）＋ `app/data/pbis.py`（`create_pbi`／`get_pbi`）
- [x] 不正な状態遷移（new→ready→inProgress→done 以外）が弾かれる　`is_valid_transition`（前進の隣接＋据え置きのみ許可）→ 不正は 422＋`violations`（`rule=pbi-status-transition`）
- [x] **`PATCH`/`DELETE` は `If-Match` 必須**（欠落は428・不一致は412 — D-20）　`require_if_match`（428）／`repo.replace`・`repo.soft_delete` の `if_match`（412）

### ✅ B-16 並び替え（rank）　`依存: B-07`
> **完了（2026-08-01）。実サービスで並び替えの動作確認が取れ、照合順序検証（Q-E）も
> 解消した。** 実 Cosmos で `ORDER BY rank, id` が序数順と一致することを確認済み（大文字
> ヘッダを含むランクでも整列が壊れないこと・末尾追加／先頭挿入／同一ランク＋別 id の
> 並びが Python の序数ソートと一致することを確認）。提案書 06章のフォールバック（浮動小数＋
> 定期リバランス）への切り替えは不要と判断した。以下は実装完了時（2026-07-28）の記録。
>
> **実装（2026-07-28）:**
> 文字列ランク（fractional indexing）を `app/data/ranking.py`（Base36・ライブラリ委譲）に、
> 並び替えを専用エンドポイント `POST /api/products/{pid}/pbis/{id}/rank`（前後の要素 ID を
> 受け取りサーバーで生成）に実装した。PBI は**作成時にバックログ末尾へ採番**し（全 PBI が
> rank を持つ＝前後補間が常に成り立つ）、移動は**1 ドキュメントだけ**を更新する。規約は
> ハンドラに書き散らさず既存部品に依存（非メンバー 403・If-Match 必須 428/412・前後関係
> 破れ／不明な隣接／自己指定は 422＋`violations` rule=`pbi-rank`）。`make test`（pytest
> 195 件）・`make lint`・`make typecheck` 緑。OpenAPI から `schema.d.ts` 再生成。
>
> ⚠️ **ライブラリの含意**: fractional-indexing は桁部に Base36 を使うが、整数長ヘッダ
> （先頭 1 文字）は `digits` と無関係に `a-z`／`A-Z` を使う。**先頭挿入ではヘッダが大文字
> （`Z`/`Y`…）になり得る**（序数比較では `0-9 < A-Z < a-z` で正しく整列する）。Base36 が
> 消すはずだった「大文字小文字の比較順」を先頭ヘッダで一部残すため、下の Q-E 検証は
> **大文字ヘッダを含むランクも対象**にする（`app/data/ranking.py` の警告に詳細）。
>
> 🔴 **残作業（Q-E・実サービス限定）**: 実 Cosmos で `ORDER BY rank, id` が序数順と一致する
> ことを確認する。`scripts/verify_rank_ordering.py` を用意した（末尾追加・大文字ヘッダの
> 先頭挿入・同一ランク＋別 id を撒き、サーバーの並びと Python の序数ソートを突き合わせて
> PASS/FAIL・後始末まで自動）。**実サービスでのみ意味を持つ（エミュレータ不可 — D-19）。**
> 一度きりの独立ゲートとして扱い、CI には載せない。不一致なら提案書 06章のとおり浮動小数＋
> 定期リバランスへ切り替え、その判断を `docs/decisions` に記録する。
>
>     COSMOS_ENDPOINT=... COSMOS_KEY=... COSMOS_DATABASE=... \
>         python scripts/verify_rank_ordering.py

- [x] **実サービス**で `ORDER BY` が辞書順と一致することを確認済み（不一致なら方式切替を記録）　→ 実 Cosmos で並び替えの動作確認＋序数順一致を確認（Q-E 解消・方式切替は不要）。`scripts/verify_rank_ordering.py` を用意
- [x] 文字列ランク（fractional indexing・ライブラリ利用・Base36）を採用　`app/data/ranking.py`（`fractional-indexing` 委譲・`RANK_DIGITS` Base36）
- [x] 生成はサーバー側（**専用エンドポイントに前後の要素IDを渡す** — D-20）　`app/api/pbis.py`（`POST .../rank`・`RankMove{beforeId, afterId}`）
- [x] 1件を移動したとき更新ドキュメントが**1件だけ**である　`reorder` は移動対象の `rank` だけを `repo.replace`（`test_reorder_updates_only_one_document`）
- [x] `ORDER BY rank, id`（ULIDのidをタイブレーカー）で全端末の並びが一致する　サーバーが `DEFAULT_ORDER=(rank,id)` を保証（B-07/B-12。同一キーは id でタイブレーク）※実サービスでの序数保証は上の Q-E に依存

### ✅ B-17 プロダクトバックログ画面　`依存: B-03, B-15, B-16`
> **完了（2026-08-01）。** 画面と集約 GET を実装した。E2E フロー①の緑化はこの PBI 単独では
> 閉じられない横断課題（5本共通のサインイン経路）に依存するため、その責務は **EX-1 に集約**
> した（下記の完了条件参照。フロー①の本体は B-20 で書き上げ済み）。読み取りを**画面単位**にし
> （`GET /api/products/{pid}/backlog` で 1 往復・`ORDER BY rank, id`）、`PBI 一覧 →
> 各 PBI のタスク` の N+1 を作らない（D-20）。集約 GET は応答全体の ETag を持てないため、
> 各要素の `_etag` を**本文のフィールド**で返し、フロントはそれを並び替え・ステータス
> 変更の `If-Match` にそのまま載せる（`app/api/backlog.py`）。配下タスク・未割当チーム
> タスクの結合はタスク層（B-20）が入った時点でこの集約へ足す（PBI の並び契約はここで完結）。
>
> フロントは画面A（`frontend/src/app/backlog/`）を追加。並びの正はサーバーに置き、
> 受け取った順序をそのまま描画して**再ソートしない**。並び替え・ステータス変更・追加の
> あとは集約 GET を引き直し、サーバーが確定した並び・版を正とする（楽観的な差分計算で
> 二重の真実を作らない）。並び替えは前後の要素 ID を渡すだけ（ランク生成はサーバー所有 —
> B-16）、ステータス遷移の正当性判定もサーバーに委ね不正は 422 の problem を読んで示す
> （フロントで不変条件を再実装しない — D-20）。ドラッグはネイティブ HTML5 DnD で依存を
> 増やさない。型は OpenAPI 生成（`schema.d.ts`）が正。`make test`（pytest 205 件＋Vitest
> 44 件）・`make lint`・`make typecheck`・`make build` 緑。
>
> **繰り延べた作業は受け側 PBI の完了条件へ移譲済み**（宙に浮かせない）:
> - 配下タスクの `/backlog` 結合 と **E2E フロー①の本体**（タスク追加UI）→ **B-20**（実装済み）
> - **E2E フロー①の緑化**（`test.fixme` 解除）は 5 本共通のサインイン経路に依存 → **EX-1**（横断課題として集約）
> - 未割当チームタスクの `/backlog` 露出（`unassignedTeamTasks`）→ **B-29**
>
> いずれも `app/api/backlog.py` の集約に join point を用意してあり、追加時に PBI の並び契約を
> 作り直さない（同じパーティションを型で舐めて束ねるだけ）。
- [x] PBIが優先順位順に並ぶ　サーバーの `ORDER BY rank, id`（`list_backlog`）をそのまま描画・再ソートしない
- [x] ドラッグで並び替えできる　ネイティブ DnD → 前後の要素 ID を `POST .../rank` に渡す（`If-Match` は各要素の `_etag`）
- [x] ステータスを変更できる　`PATCH` で遷移（正当性判定はサーバー。不正は 422・problem 表示）
- [x] **`GET /backlog`（画面単位）で1往復。N+1にしない**（D-20）　`app/api/backlog.py`（各要素に `_etag`）
- [x] **E2E フロー①の「PBI 作成」導線を用意する**（`PBI を追加`／`タイトル`／`保存`）　→ フロー①の本体は B-20 で書き上げ済み（`frontend/e2e/signin-pbi-task.spec.ts`）。`test.fixme` 解除＝実際の緑化は 5 本共通のサインイン経路に依存するため **EX-1 に集約**（この PBI 単独では閉じられない横断課題。D-19 主要フロー網羅）

### ✅ B-18 PBI詳細　`依存: B-17`
> **完了（2026-08-01）。** バックログ（画面A）から 1 件の PBI へ**ドリルダウン**する
> 詳細画面（`/backlog/:pbiId`・`frontend/src/app/pbi-detail/`）を追加した。新しいモードでは
> なく画面Aの掘り下げで、**2画面原則は維持**する（提案書「リファインメント＝書く」は画面Aの
> 作業 — D-21）。バックエンドの更新経路は B-15 の汎用 `PATCH`（`PbiUpdate` が
> `description` / `acceptanceCriteria` / `estimate` / `title` を持つ）で足りるため、この PBI は
> **フロントのみ**。読み取りは B-17 の集約 GET と非対称に**単一 GET**（版は本文でなく `ETag`
> ヘッダ — D-20）を使い、`PbiService` に `getOne` / `update` を足して**応答全体を観測**し版を
> 運ぶ。バリデーションの正はサーバーに置き、フロントは 422 の problem を読んで示すだけ
> （タイトル必須の再実装はしない — D-20）。版がずれたら（412）**黙って上書きせず最新を
> 読み直す**（P-1）。完了条件の項目 id はクライアントで採番し（不透明な識別子）、空文字の
> 項目は保存時に落とす。`make test`（pytest 207 件＋Vitest 54 件）・`make lint`・
> `make typecheck`・`make build` 緑。
- [x] 概要を編集できる　`pbi-detail`（textarea → `PATCH description`）
- [x] 完了条件のチェックリストを編集できる　チェック／テキスト編集／追加・削除 → `PATCH acceptanceCriteria`（id はクライアント採番・空項目は保存時に除外）
- [x] `estimate` を編集できる（**任意入力・未設定でも警告を出さない** — D-06）　空欄は `null` を送り、未設定でも警告を出さない

### ✅ B-19 PBIの分割　`依存: B-17`
> **完了（2026-08-03）。M4 完了。** 「大きな PBI を割る」操作を、分割元を指す**新規作成**
> として実装した。ドメイン操作 `app/data/pbis.py` の **`split_pbi`** は、`create_pbi` と同じく
> 通常の PBI（状態は `new` から・独立して並び替え／編集／完了できる）を作り、唯一
> `parentPbiId` に分割元の id を刻む。分割元自身は**変更しない**——参照は子 → 親の一方向のみで
> （現在地の保持と同じく参照を増やさない — 提案書 04章）、だから更新ではなく作成であり
> **`If-Match` を要さない**（汎用 `PATCH` は `parentPbiId` を触らない — B-15/D-20）。専用
> エンドポイント `POST /api/products/{pid}/pbis/{pbi_id}/split`（`app/api/pbis.py`）は規約を
> ハンドラに書き散らさず既存部品に依存（非メンバー **403**・分割元が無ければ **404**・空
> タイトルは **422**）。入力は作成と同形（`PbiCreate`）で新しい入力語彙を増やさない。子の
> `rank` は `create_pbi` と同じく**バックログ末尾**に採番する——分割元の直後へ割り込ませないのは、
> 同一 rank の隣接（タイブレークは id）へ `rank_between` するとキーが衝突し得るため
> （`app/data/ranking.py` の警告）。位置ではなく `parentPbiId` の参照で辿らせ、末尾採番という
> 壊れにくい1本の経路に寄せた。
>
> フロントはバックログ画面（画面A）に「分割」ボタン＋タイトルだけの軽量フォームを足し、
> 集約 GET（B-17）が各 PBI に既に載せている `parentPbiId` を使って **「↳ 分割元: <名前>」の
> リンク**を一覧上に描く（分割元の詳細 B-18 へ辿れる）。分割元の名前は一覧から解決し、
> 一覧外なら「（一覧外）」を示す。作成後は集約 GET を引き直し、サーバーの並び・版を正とする。
> `make test`（pytest 294 件＋Vitest 65 件）・`make lint`・`make typecheck`・`make gen-types`
> 緑。OpenAPI から `schema.d.ts` 再生成。
- [x] 分割で生成したPBIが `parentPbiId` で元を参照する　`app/data/pbis.py`（`split_pbi`）／`POST .../{pbi_id}/split`。生成物は通常の PBI で `parentPbiId` に分割元を刻む（分割元は不変・作成なので If-Match 不要）
- [x] 一覧から分割元を辿れる　バックログ集約（B-17）の各 PBI が持つ `parentPbiId` から「↳ 分割元: <名前>」リンクを描画し、分割元の詳細（B-18）へ辿れる　`frontend/src/app/backlog/`

### ✅ B-20 タスクのCRUD　`依存: B-07, B-15`
> **完了（2026-08-01）。** CRUD・不変条件・バックログ結合・追加UIまで実装した。E2E フロー①の
> 本体も書き上げたが、その緑化（`test.fixme` 解除）は 5 本共通のサインイン経路に依存する横断
> 課題のため、責務を **EX-1 に集約**した（B-20 の機能スコープは完結）。
> タスクのドメイン規則を **データ層の純関数**（`app/data/tasks.py`）に一元化した。判別子
> `taskType`（pbi/team）と状態（todo/doing/done）の語彙を持ち、不変条件 **I-1〜I-4** を単一の
> `check_invariants(doc) -> list[str]` に集約する（違反した不変条件 ID の列を返す）。**I-5**
> （完了タスクの `sprintId` を持ち越し・除外で動かさない）は単一文書では表せず、スプリント
> 終了操作（B-25）に閉じる（提案書 04章の表・`single_doc=False`）。完了地の刻印（`completedAt`）は
> `completion_changes` に閉じ、done への出入りで I-1・I-2 を保つ（ボード B-23 も同じ経路を通る）。
>
> CRUD は `app/api/tasks.py`（`/api/products/{pid}/tasks`）。作成・更新のたびに結果ドキュメントを
> `check_invariants` に通し、破っていれば **422 + `violations`**（`rule='I-3'` 等・B-12 と揃う）で
> 弾く（サーバーが唯一の信頼境界 — D-20）。`taskType='team'`（親 PBI なし）でも作成でき、pbi
> タスクは親 PBI の実在まで確かめて孤児を作らせない。規約はハンドラに書き散らさず既存部品に
> 依存（非メンバー 403・If-Match 必須 428/412・単一ドキュメント応答は ETag）。
>
> `GET /backlog` は B-17 が用意した join point に配下タスク（`taskType='pbi'`）を結合する。
> パーティションのタスクを 1 回舐めて `pbiId` で束ねるだけで **N+1 にしない**。各タスクも
> `_etag` を本文に持ち、フロントがボード操作の If-Match に使える。未割当チームタスクの露出
> （`unassignedTeamTasks`）は B-29 に残す（同じ join point に足す）。フロントは各 PBI 配下に
> タスクを表示し、「タスクを追加」で pbi タスクを足せる（`TaskService`＋バックログ画面）。
> `make test`（pytest 261 件＋Vitest 61 件）・`make lint`・`make typecheck`・`make build` 緑。
> OpenAPI から `schema.d.ts` 再生成。
- [x] I-1〜I-5 のバリデーションが**単一の関数に集約**されている　`app/data/tasks.py`（`check_invariants` が単一文書の I-1〜I-4 を集約。I-5 は操作をまたぐため B-25 の終了処理に閉じる — 提案書 04章の表）
- [x] I-4: 種別判定は `pbiId` の有無ではなく **`taskType`** で行う　`check_invariants`／`_group_pbi_tasks` が `taskType` で判別
- [x] `taskType='team'`（親PBIなし）でも作成できる　`POST /tasks`（`taskType='team'` は `pbiId=null`。team に pbiId を付けると I-4 で 422）
- [x] **B-11 の不変条件テーブル駆動テストの振る舞い検査を有効化する** — `app.data.tasks.check_invariants(doc) -> list[str]` を実装し、`backend/tests/invariants/` の `VALIDATOR_MODULE` をそこへ向けて `pytest.importorskip` の skip を外した（違反IDは B-12 の `violations` の `rule` と揃う）
- [x] **`GET /backlog` に配下タスクを結合する**（B-17 の join point — `app/api/backlog.py`）。PBI ごとに `tasks` を束ね、パーティションをもう一度型で舐めるだけで **N+1 にしない**（未割当チームタスクの露出は B-29）。フロントのバックログ画面（`frontend/src/app/backlog/`）は各 PBI 配下のタスクを表示する
- [x] **E2E フロー①の「タスク追加」導線とフロー本体を用意する**（`frontend/e2e/signin-pbi-task.spec.ts`）　→ タスク追加UI（`タスクを追加`／`タスク名`／`追加`）を載せ、サインイン→PBI作成→タスク追加のフロー本体を書き上げた。`test.fixme` 解除＝実際の緑化は 5 本共通のサインイン経路（`playwright.config.ts` の宿題・B-14 が一つの選択肢）に依存する横断課題のため **EX-1 に集約**（D-19 主要フロー網羅）

---

---

## M5 — スプリントが1周回る ★ここからドッグフーディング　✅ 達成（2026-08-06）

> 🎉 **M5 達成。** スプリントの CRUD（B-21）→ プランニング（B-22）→ ボード（B-23）→ 進捗表示
> （B-24）→ 終了処理（B-25）→ 楽観排他 UX（B-26）まで積み上がり、**スプリントが計画から締めまで
> 1 周回る**ようになった。★**ここからこのバックログ自体をこのアプリで管理できる**——以降は
> ドッグフーディングで進める。次は M6（デイリースクラムがこの画面だけで完結する）。

### ✅ B-21 スプリントのCRUD　`依存: B-07`
> **完了（2026-08-03）。M5 の最初のリソース CRUD。** スプリント（`sprint`）を、PBI の CRUD
> （B-15）と同じ組み立てでリソース単位に実装した。ドメイン規則を**データ層の純関数**
> （`app/data/sprints.py`）に一元化する：状態の語彙 `SprintStatus`（planned/active/closed）と
> 正当な遷移 `is_valid_transition`（`planned → active → closed` の一方向前進＋据え置き。PBI の
> `_FORWARD` と同型）、期間の破れ判定 `is_valid_period`（`endDate < startDate` を弾く。ISO 日付は
> 辞書順＝暦順のため文字列比較で足りる）。`number` はパーティション内で**連番採番**する
> （`next_number`。作成順に 1, 2, 3…）。HTTP への翻訳（422・`violations`）だけを API 層
> （`app/api/sprints.py`）に置き、データ層は HTTP を知らない。
>
> エンドポイントは B-09 の `require_member` に依存するだけで**非メンバー 403**、B-12 の
> `require_if_match` で **`If-Match` を構造的に必須**（欠落 428・不一致 412）、`problem_responses`
> で RFC 9457 応答を OpenAPI に宣言した（規約をハンドラに書き散らさない — D-20）。`number` は
> 入力に取らず（採番はサーバー所有）、作成時の `status` も取らない（必ず `planned` から）。
> `PATCH` は `status` を動かすときだけ遷移の正当性を、期間を動かすときは**更新後の実効値**
> （部分更新なので現行値と突き合わせ）で逆転を確かめる。単一ドキュメント応答は `ETag` ヘッダで
> 版を返し、一覧（`GET /sprints`）は集約 GET と同じく各要素が `_etag` を本文で運ぶ（フロントが
> 各スプリントの `If-Match` にそのまま使える — D-20）。フェイク Repository で作成→取得→一覧→
> 更新→論理削除・状態遷移・期間逆転・412／428・非メンバー 403・401 を端から端まで検証し、
> OpenAPI から `schema.d.ts` を再生成した（`make test` 緑・pytest 337 件＋Vitest 65 件／
> `make lint`／`make typecheck`／`make build` 緑）。実 Cosmos での往復は層3（B-11）と実サービス
> （B-31）へ。
>
> **繰り延べた（帰属を明確にした）作業:** 同時に `active` なスプリントを1つに絞る**操作級の
> 制約**は、単一ドキュメントの状態遷移では表せず（他スプリントの状態を見る必要がある）、
> それが要るのは「今どのスプリントか」を決めるプランニング／ボード（**B-22 / B-23**）の
> 時点のため、ここでは課さない（I-5 の担保を B-25 に閉じたのと同じ切り分け）。専用の
> プランニング操作（PBI チェックで配下タスクに `sprintId` を付与）は **B-22**、ボードと
> `GET /board` は **B-23**、終了処理は **B-25** が所有する。
- [x] 期間とゴールを設定できる　`SprintCreate`/`SprintUpdate`（`goal`/`startDate`/`endDate`。逆転期間は 422＋`violations` rule=`sprint-period`）
- [x] `planned` / `active` / `closed` が遷移する　`app/data/sprints.py`（`is_valid_transition`。前進の隣接＋据え置きのみ許可）→ 不正は 422＋`violations`（rule=`sprint-status-transition`）

### ✅ B-22 プランニングモード（右ペイン）　`依存: B-17, B-20, B-21`
> **完了（2026-08-06）。** 「どの PBI を今スプリントで回すか」を決める操作を実装した。要点は
> **PBI 自身はスプリントへの参照を持たない**こと（提案書 04章・D-08）——「PBI が今スプリントに
> いる」は配下タスクの `sprintId` から**導出**できるため二重に持たない。したがってプランニングの
> 実体は**配下タスクの `sprintId` の付け外し**であり、その規則を**専用エンドポイント**
> （`POST/DELETE /api/products/{pid}/sprints/{sid}/pbis/{pbiId}`・`app/api/planning.py`）に
> 閉じた（D-20。複数ドキュメントを1規則で束ねる操作を汎用 `PATCH` に分解するとクライアントに
> 規則が漏れる）。ドメイン操作は純関数 `app/data/planning.py`（`plan_pbi_into_sprint` /
> `unplan_pbi_from_sprint`）に一元化し、HTTP への翻訳（403/404）だけを API 層に置く。
>
> **取り込み**は配下の未完了タスクに `sprintId` を付け、**タスク0件なら「タスク分解」タスクを
> 1件生成**する（D-15。タスクの無い PBI をスプリントに置けるようにし「どこにも表示されない状態」
> を作らない。2回目以降の取り込みでは生成済みが未完了で残るため増えない＝冪等）。**外す**は
> このスプリントにいる未完了タスクだけを `sprintId=null` に戻し、**完了タスクは動かさない**
> （I-5。他スプリントのタスクにも触れない）。`If-Match` は取らない——分割（B-19）と同じく複数
> タスクを束ねるサーバー所有のドメイン操作で、単一リソースの更新ではない（個々のタスクの楽観
> 排他はデータ層が読み直した `_etag` で内部的に満たす）。
>
> フロントは画面A（バックログ）に**プランニング右ペイン**を足した（`SprintService` ＋
> `frontend/src/app/backlog/`）。開いたときにだけ `GET /sprints` を読み（既存の初期表示を変えない）、
> 取り込み先スプリントを選ぶ／その場で作る。各 PBI のチェックの状態は保持せず、配下タスクの
> `sprintId` から**毎回導出**する（サーバーとフロントに2つの真実を作らない — D-08）。取り込み／
> 外すの後は集約 GET を引き直し、サーバーが確定した状態を正とする。実ブラウザ（e2e ビルド＋
> メモリ DB）で「PBI 追加 → プランニングを開く → スプリント作成 → チェック → タスク分解生成」
> まで目視確認済み。`make test`（pytest 354 件＋Vitest 76 件）・`make lint`・`make typecheck`・
> `make build` 緑。OpenAPI から `schema.d.ts` 再生成。
- [x] PBIのチェックで配下の未完了タスクに `sprintId=S` が付く　`app/data/planning.py`（`plan_pbi_into_sprint`。未完了だけ・既に S なら飛ばす）
- [x] **タスク0件のPBIをチェックすると「タスク分解」タスクが1件生成される**（D-15）　`_create_decomposition_task`（生成と同時に `sprintId` を打つ・冪等）
- [x] 外すと**未完了タスクのみ** `sprintId=null` に戻る（完了タスクは動かさない — I-5）　`unplan_pbi_from_sprint`（`sprintId` 一致かつ未完了のみ）
- [x] 上記の規則が**専用エンドポイントとしてサーバー側に閉じている**（D-20）　`POST/DELETE .../sprints/{sid}/pbis/{pbiId}`（`app/api/planning.py`。非メンバー 403・不明な sprint/pbi は 404）
- [x] **B-11 の E2E フロー②（プランニング, `frontend/e2e/planning.spec.ts`）の `test.fixme` を外して緑にする**（タスク0件のPBIで「タスク分解」生成まで含む — D-19）　→ EX-1 の共通サインイン経路の上で `test.fixme` を解除。スプリントはフロー内でプランニング右ペインから作る

### ✅ B-23 スプリント画面のボード　`依存: B-20, B-21`
> **完了（2026-08-06）。着手前に Q-F（412 発生後の UX）を [`D-24`](./decisions/D-24-optimistic-concurrency-ux.md)
> で決めてから実装した。** 2画面構成の2枚目（画面B・`/board`・`frontend/src/app/board/`）。選んだ
> スプリントのタスクを **todo / doing / done** の 3 カラムに並べ、ドラッグで状態を移し、ブロック中
> フラグを立てられる。要点は **書き込み側を新設しない**こと——状態移動は `status`、ブロックは
> `isBlocked` で、どちらも B-20 の汎用 `PATCH /tasks` で足りる（完了地 `completedAt` の刻印は
> `completion_changes` がサーバー側で行う。I-1・I-2 を再実装しない）。したがってこの PBI で新規に
> 要るのは**画面単位の集約 GET** だけだった。
>
> 読み取りは `GET /api/products/{pid}/sprints/{sid}/board`（`app/api/board.py`）で 1 往復
> （最頻出の画面のため軽く保つ — 提案書 07章・D-20）。データ層は `list_sprint_tasks`（`sprintId`
> 一致を 1 クエリ）に閉じ、`GET /backlog` と同じく **N+1 にしない**。各タスクは `_etag` を本文で
> 返し（集約 GET は応答全体の ETag を持てない）、フロントはそれをボード操作の `If-Match` に載せる。
> **todo/doing/done の 3 カラムへの振り分けは `status` からの導出**であって不変条件ではないため、
> サーバーは `rank, id` 順のフラットな列を返し、カラム分けはフロントが行う（二重の真実を作らない —
> D-20）。進捗集計（2本バー）を後から足せるよう応答はオブジェクトで包んだ（join point は B-24）。
>
> **楽観排他は D-24 のとおり実装した。** 版がずれて 412 になったら**黙って上書きせず**、ボードを
> 引き直して最新を見せ、再操作を促す（自動マージしない）。412 発生後の文言は画面ごとに書き分けず
> `app/api/errors.ts` の `messageForError` に一本化し、既存のバックログもこれに載せ替えて**一貫適用**
> した。表示スプリントは実行中（active）を優先し、無ければ番号最大に寄せる。`make test`（pytest
> 362 件＋Vitest 88 件）・`make lint`・`make typecheck`・`make build` 緑。OpenAPI から
> `schema.d.ts` 再生成。E2E フロー③の `test.fixme` を外した（実緑化は EX-1 の共通基盤の上で CI が検証）。
- [x] todo / doing / done をドラッグで移動できる　ネイティブ DnD → カラムへのドロップで `PATCH status`（`frontend/src/app/board/`）
- [x] ブロック中フラグを立てられる　カード上のトグル → `PATCH isBlocked`（警告色を使わず事実を可視化 — D-13）
- [x] **2人が同時に触っても片方の更新が消えない**（楽観排他）　各タスクの `_etag` を `If-Match` に載せ、不一致は 412。発生後は最新を引き直して再操作を促す（**D-24**。lost update の経路が無い）
- [x] **`GET /board`（画面単位）で1往復**。各要素に `_etag` が含まれる（D-20）　`app/api/board.py`（`list_sprint_tasks` で N+1 にしない・各タスクが `_etag` を本文で運ぶ）
- [x] **B-11 の E2E フロー③（ボード操作 todo→doing→done, `frontend/e2e/board.spec.ts`）の `test.fixme` を外して緑にする**（D-19）　→ EX-1 の共通サインイン経路の上で解除（サインイン→PBI作成→プランニングで取り込み→ボードで移動）

### ✅ B-24 進捗表示　`依存: B-23`
> **完了（2026-08-06）。着手前に「営業日」の定義（祝日・タイムゾーン）を [`D-25`](./decisions/D-25-business-days-and-timezone.md)
> で決めてから実装した。** デイリースクラムで「このペースで計画通り終わるか」を読むための計器
> （提案書 05章）。要点は **B-23 が用意した join point に足すだけ**で済ませたこと——集計は
> `GET /board` が既に引いた `tasks` から数え、追加クエリを撃たない（N+1 を作らない）。
>
> 集計は**データ層の純関数** `app/data/progress.py`（`compute_progress`）に一元化した：
> 計画タスク（`taskType='pbi'`）／チームタスク（`taskType='team'`）それぞれの**完了 / 総数**
> と、マーカーの**経過営業日 / 総営業日**を返す。営業日は土日に加えて**日本の祝日も除外**し
> （D-25。`jpholiday` に委譲——振替休日・国民の休日・春分/秋分・ハッピーマンデーを自前で誤ると
> 静かに1日ずれる）、「今日」は **Asia/Tokyo の暦日**（`clock.jst_date`）で数える。**「今日」は
> 引数注入**で、`GET /board` は `get_clock`（`app.state.clock`・`get_repository` と同型）から供給
> するため、日付を固定してテストできる（D-19。B-25 の終了処理も同じ時計に乗る）。マーカーの
> 分子は区間 [0, 総営業日] に収め、**期間未設定なら営業日は `null`**——マーカーを描かない
> （ありもしない位置をでっち上げない — P-1）。API 層（`app/api/board.py`）は `BoardResponse` に
> `progress` を足すだけ（データ層の snake_case → 応答の camelCase 翻訳のみ担う。ドメイン語彙を
> 画面語彙に侵食させない — D-20）。
>
> フロントは画面B（`frontend/src/app/board/`）に**進捗パネル**を足した。件数はサーバー由来で、
> フロントは**描画のための導出だけ**——2本のバーを**共通目盛**（分母の大きい方）で並べて長さが
> そのまま件数比になるようにし、マーカーを計画タスクのトラック内で経過/総営業日の位置に置く。
> **色は種別（計画=ティール / チーム=アンバー）の区別のみで、遅れを警告する色は使わない**
> （P-1 / D-13）。`make test`（pytest 379 件＋Vitest 92 件）・`make lint`・`make typecheck`・
> `make build` 緑。OpenAPI から `schema.d.ts` 再生成。
- [x] 提案書 05章の**2本バー**（計画タスク / チームタスク）が表示される　`frontend/src/app/board/`（`progressView` が共通目盛で2本を描く）／`app/api/board.py`（`progress`）
- [x] マーカーが**営業日**で計算されている（暦日にしない）　`app/data/progress.py`（`business_days_between`。土日＋日本の祝日を除外 — D-25）
- [x] **警告色を使っていない**（色は種別の区別のみ — P-1 / D-13）　`board.scss`（planned=`#0b6e7a` / team=`#8a6a1e`。遅れで色を変えない）
- [x] （要確認）祝日・タイムゾーンの扱いを決めた　→ [`D-25`](./decisions/D-25-business-days-and-timezone.md)（**日本の祝日も除外**・`jpholiday` に委譲・**Asia/Tokyo** 固定）
- [x] **「今日」が注入可能で、日付を固定してテストできる**（D-19。B-25の終了処理も同様）　`compute_progress(today=…)` 純関数＋`get_clock`（`app.state.clock` 差し替え）

### ✅ B-25 スプリント終了処理　`依存: B-21, B-23`
> **完了（2026-08-06）。着手前に持ち越しの規則と移動先を [`D-26`](./decisions/D-26-sprint-close.md)
> で決めてから実装した。** スプリントを締める操作を、提案書 07章のとおり **2 つの更新**
> （未完了タスクを次スプリントへ・スプリントを `closed` に）に尽きる形で実装した。要点は
> **I-5**（完了タスクは持ち越し・除外の対象にしない・`sprintId` を変更しない）——単一文書では
> 表せない操作級の不変条件で、その担保をこの終了操作に閉じる（プランニングの「外す」B-22 と
> 同じ切り分け。B-20 の `check_invariants` は単一文書の I-1〜I-4 だけを見る）。
>
> ドメイン操作は純関数 `app/data/sprint_close.py`（`carry_over_targets`＝プレビュー用の
> 読み取り／`close_sprint`＝未完了の `sprintId` 付け替え＋`status=closed`）に一元化した。
> エンドポイント（`app/api/sprint_close.py`）は D-20 の**読み書き非対称**に乗せ、
> **`GET .../close/preview`（持ち越し一覧・副作用なし）と `POST .../close`（確定）を分ける**
> ——頻度は低いが取り返しのつかない操作なので、事実を見せてから確定する（P-1）。締められるのは
> **`active` のスプリントだけ**（状態機械 planned→active→closed と揃える）、移動先は
> `nextSprintId` で**既存の別スプリント**を指定し（提案書 07章 `sprintId = <nextSprintId>`。
> 自己指定／終了済みは 422・実在しなければ 404）、自動で新規作成も `null` 戻し（＝「外す」B-22）
> もしない。規約はハンドラに書き散らさず既存部品に依存（非メンバー **403**）、`If-Match` は
> 取らない——分割（B-19）・プランニング（B-22）と同じ**複数ドキュメントを束ねるサーバー所有の
> 操作**（個々の楽観排他はデータ層が読み直した `_etag` で内部的に満たす）。
>
> フロントは画面B（ボード）に**開始→終了**の導線を足した。状態で出し分け（`planned` は
> 「スプリントを開始」＝`active` へ・`active` は「スプリントを終了」）、M5 の「1 周回る」を
> 開始から締めまで一筆で辿れるようにした。終了はプレビュー（未完了だけ・完了は含まない I-5）を
> 見せてから移動先を選んで確定し、締めた後は**持ち越し先を表示スプリントにして**移った未完了
> タスクをそのまま確認できる。件数の通知は**中立色**（警告色を使わない — D-13）。`make test`
> （pytest 397 件＋Vitest 99 件）・`make lint`・`make typecheck`・`make build` 緑。OpenAPI から
> `schema.d.ts` 再生成。E2E フロー④の `test.fixme` を外した（実緑化は EX-1 の共通基盤の上で CI が検証）。
- [x] 持ち越し対象の一覧をプレビューしてから確定できる（`close/preview` と `close` を分ける — D-20）　`app/api/sprint_close.py`（`GET .../close/preview`＝読み取り・`POST .../close`＝確定）
- [x] **完了タスクは移動しない・`sprintId` を変更しない**（未完了のみ次スプリントへ）　→ **不変条件 I-5 の担保はここ**（`app/data/sprint_close.py` が `status != 'done'` だけを付け替え・完了は凍結。単一文書で表せない操作級の不変条件。B-20 の `check_invariants` は I-1〜I-4 の単一文書のみを見る）
- [x] 強制も警告もせず事実だけ見せる（P-1）　プレビューは持ち越し一覧を見せるだけ・締められるのは active だけ・移動先は人が選ぶ（D-26）。件数通知は中立色（警告色を使わない — D-13）
- [x] **B-11 の E2E フロー④（スプリント終了・完了タスクは動かず未完了だけ持ち越し, `frontend/e2e/sprint-close.spec.ts`）の `test.fixme` を外して緑にする**（D-19）　→ EX-1 の共通サインイン経路の上で解除（サインイン→PBI に完了/未完了2タスク→S1 開始→完了へドラッグ→終了プレビュー→S2 へ持ち越し確定）

### ✅ B-26 楽観排他（412）のUX方針と実装　`依存: B-23`
> **完了（2026-08-06）。方針は先に [`D-24`](./decisions/D-24-optimistic-concurrency-ux.md) で決め、実装は
> B-23（ボード）で入れ、横断適用を B-25 まで積んだ。本 PBI は「4 条件が別 PBI で満たされている
> ことを実地で監査し、証跡を残して閉じる」性質のもの**（Q-F は決定済み）。**
>
> **Q-F**: B-23 は 412 の**検出**を保証するが、**発生後どうするか**が未定義だった。朝会の同時
> 操作が前提のため体験を左右する。方針は D-24 で決めた——**黙って上書きせず、画面を最新に
> 引き直して事実を見せ、次の一手は人に返す（再操作を促す）。自動再取得マージは採らない。412
> 本文に最新値は含めない**（最新の源は集約 GET に一本化。二重の真実を作らない）。
>
> **横断適用の監査（④の裏取り）**: `If-Match` を載せる＝ 412 しうる全書き込み経路が、失敗時に
> **黙って上書きせず再取得している**ことを確認した——board（`onDrop`/`toggleBlocked`/
> `activateSprint` → `reloadBoard`/`loadSprints`）・backlog（`changeStatus`/`reorder` → `load`）・
> pbi-detail（`save` → 412 を検出して `load`）。文言は 412 とその他で分けるが（D-24 が許容）、
> 「再取得して事実を見せる」動きは共通で、**lost update（更新が黙って消える）の経路は無い。**
> 412 の一貫文言は `frontend/src/app/api/errors.ts` の `messageForError`（board/backlog が共有）。
- [x] 412発生時の振る舞いを決定（自動再取得マージ / ユーザーに再操作を促す 等）　→ [`D-24`](./decisions/D-24-optimistic-concurrency-ux.md)（**再操作を促す**＋即時再取得。自動マージは却下）
- [x] **412応答に最新値を含めるかを決定**（D-20が判断を委ねている）　→ D-24（**含めない**。最新は集約 GET に一本化）
- [x] 決めた振る舞いがボード操作で一貫して適用される　`board.ts`（`onDrop`/`toggleBlocked` が `messageForError` ＋ `reloadBoard`。B-23 で実装）
- [x] 更新が黙って消える経路が存在しないことを確認　→ 版を持つ全書き込み経路（board/backlog/pbi-detail）が失敗時に再取得することを監査（上記）

---

---

## M6 — デイリースクラムがこの画面だけで完結する

### ✅ B-27 デイリーパネル　`依存: B-23`
> **完了（2026-08-07）。M6 に着手。着手前に 1日1件のキーと取得方式を [`D-27`](./decisions/D-27-daily-note.md)
> で決めてから実装した。** デイリースクラムを画面B（ボード）だけで完結させる第一歩として、
> **その日のアジェンダと議事録**を編集するパネルを足した。要点は提案書 04章の **1日1ドキュメント**
> を**決定的 ID `dly_<sprintId>_<date>`** で構造的に担保したこと——連番 ULID を振らず (スプリント,
> 日付) から id を導くので、同じ日には**1件しか作れず**ポイントリード1件で引ける（`mbr_<oid>` /
> `usr_<oid>` と同じ発想 — D-21）。
>
> 読み書きは D-20 の非対称に乗せた。**`GET .../sprints/{sid}/daily/{date}` は get-or-create**
> （`app/data/daily_notes.py` の `ensure_daily_note`。無ければ空のノートを作って返す・冪等・同時
> 実行の 409 は握りつぶす）——パネルが常に**編集対象と版（`ETag`）**を持てるようにする（初回
> サインインの `GET /api/me` が user/member を作るのと同じ既定パターン — D-21/D-27）。**編集は
> 単一リソースの汎用 `PATCH`＋`If-Match`**（`app/api/daily_notes.py`。B-18 の PBI 詳細と同型）で、
> `agenda` / `minutes` を部分更新する。書き込みに専用経路を新設しない。日付は `YYYY-MM-DD` のみ
> 受け（不正は 422）、**スプリント期間内かは問わない**（朝会は期間外の日にも開く — 事実を縛らない
> P-1/D-27）。規約はハンドラに書き散らさず既存部品に依存（非メンバー 403・幻のスプリント 404・
> `If-Match` 欠落 428・不一致 412）。
>
> フロントは画面B（`frontend/src/app/board/`）に**デイリーパネル**を足した（`DailyNoteService`）。
> 「デイリー」を開くと **Asia/Tokyo の「今日」**（D-25 と暦を合わせる）のノートを get-or-create し、
> アジェンダ（チェック・テキスト・追加/削除。項目 id はクライアント採番）と議事録（textarea）を
> 編集して保存する。版がずれたら（412）**黙って上書きせず最新を読み直す**（D-24）。`make test`
> （pytest 426 件＋Vitest 105 件）・`make lint`・`make typecheck`・`make build` 緑。OpenAPI から
> `schema.d.ts` 再生成。
- [x] アジェンダと議事録を編集できる　`app/api/daily_notes.py`（`PATCH .../daily/{date}` で `agenda` / `minutes` を更新・`If-Match` 必須）／フロントのデイリーパネル（`frontend/src/app/board/`）
- [x] **1日1ドキュメント**で保存される（肥大化と同時編集競合を避ける）　→ **決定的 ID `dly_<sprintId>_<date>`** のポイントリードで構造的に担保（`app/data/daily_notes.py`。同じ (sprint, date) は1件のみ・`GET` は get-or-create で create-if-absent。D-27）

### ⬜ B-28 NextActionの表示　`依存: B-27`
- [ ] 前スプリントのアクションが今スプリントのパネルに出る
- [ ] 完了にできる

### ⬜ B-29 未割当のチームタスク　`依存: B-17, B-22`
- [ ] スプリントから外したチームタスクがバックログ画面に現れる（**`GET /backlog` に `unassignedTeamTasks` を足す** — B-17 が集約の join point を用意済み `app/api/backlog.py`。`taskType='team'` かつ `sprintId=null` を束ねる）
- [ ] **どこにも表示されない状態が存在しない**（唯一許容できない失敗 — D-16）
- [ ] **B-11 の E2E フロー⑤（未割当チームタスクが現れ消えない, `frontend/e2e/unassigned-team-task.spec.ts`）の `test.fixme` を外して緑にする**（D-16「唯一許容できない失敗」の回帰テスト — D-19）

---

---

## M7 — 実運用に耐える

### ⬜ B-30 ベロシティ表示　`依存: B-25`
- [ ] `completedSprintId` ごとの `estimate` 合計が出る
- [ ] 未設定の `estimate` は除外される
- [ ] **3スプリントの移動平均**で表示される（Q-3）

### ⬜ B-31 本番運用の確認　`依存: B-06, 全機能`
- [ ] F1のスリープからの復帰時間を実測した
- [ ] RU消費を実測し、無料枠に収まることを確認した
- [ ] 予算アラートが発火することを確認した

---

---

## M8 — プロジェクトを自分たちで管理できる（将来）

> **優先度は低い。** アプリ基盤と認証を固め、スクラム機能を作り込むほうが先（D-21）。
> ここまで入るとサンドボックスは「最初の1つ」以上の意味を持たなくなる可能性があり、
> その時点で位置づけを見直してよい。

### ⬜ B-32 プロジェクト作成　`依存: B-10`
- [ ] ユーザーがプロジェクトを作成できる
- [ ] **作成者が `admin` として登録される**
- [ ] **`_system` が予約語として弾かれる**（D-21）

### ⬜ B-33 招待・参加申請・権限付与　`依存: B-32`
- [ ] 作成者が他ユーザーを招待できる
- [ ] ユーザーが参加申請できる（`joinRequest` 型を追加）
- [ ] 作成者が参加申請を承認・拒否できる（承認時に `member` を作る）
- [ ] 共同管理者を付与できる（**`role` を `admin` にするだけ。新しいroleを作らない** — D-21）

---

---

## 付録 — 追加PBIと採番の履歴

### 提案書初版に無い追加PBI

| PBI | 区分 | 要旨 |
|:---:|:---|:---|
| **B-08** | 🔴 Blocker | `productId` の発生源と初期データ投入が未定義。全設計の土台なのにPBIに無い |
| **B-10** | 🔴 Blocker | 認可のブートストラップが未定義。全員403で詰む鶏卵問題 |
| **B-11** | 🔴 Blocker | テスト戦略が空白。不変条件・認証・rankの退行を検知する仕組みが無い |
| **B-12** | 🟠 設計の穴 | API共通規約が未定。最初のCRUDが暗黙規約化する |
| **B-13** | 🟡 品質/運用 | LICENSE/README/コミット規約等が未整備 |
| **B-14** | 🔸 任意 | 開発時にサインインを省略する抜け道。当初の存在理由（画面開発の解禁）は認証を先に作る順序に変えたため消えた |
| **B-26** | 🟠 設計の穴 | 楽観排他412の**発生後UX**が未定義。検出はするが振る舞いが無い |
| **B-32** | 将来 | プロジェクト作成 |
| **B-33** | 将来 | 招待・参加申請・共同管理者 |
| **EX-1** | ✅ 横断/番号外（完了） | E2E を CI で実際に緑にする実行面の整備（サインイン経路・`webServer`・seeding）。5本共通の土台でどの機能PBIにも属さないため、着手順の B-NN とは別枠に切り出した。方式は [`D-22`](./decisions/D-22-e2e-execution.md)。フロー①を緑にし、②〜⑤は各担当PBIが同じ基盤で `test.fixme` を外す |

> **`EX-N` は横断・番号外の名前空間。** 着手順で消化する `B-NN` と違い、複数のマイルストーンに
> またがる基盤整備で「どの B-NN にも自然には属さない」ものをここに置く（`B-NN` の連番を
> 途中に割り込ませて全体をずらさない）。第1号が **EX-1**（E2E 実行整備。B-11 を閉じるために
> 切り出した）。

既存PBIへ**注記のみ**で反映した事項:

- **rankのフォールバック分岐**（🟠）→ B-16 の冒頭注記（Q-E）
- **論理削除の全クエリ除外**（🟡）→ B-07 の完了条件
- **日付・タイムゾーン・祝日**（🟡）→ B-24 の完了条件
- **Repositoryのポート化**（D-19）→ B-07 の完了条件
- **`member` のポイントリード化**（D-21）→ B-09 の完了条件

### 採番の対応表（旧 → 新）

実装順序の再編（D-21）にあわせ、**着手順どおりに 01〜33 を振り直した**。
これ以前のコミットや議論は旧IDを参照しているため、対応を残す。

| 旧ID | 新ID |
|:---:|:---:|
| `B-03` | `B-01` |
| `B-01` | `B-02` |
| `B-05` | `B-03` |
| `B-06` | `B-04` |
| `B-02` | `B-05` |
| `B-04` | `B-06` |
| `B-07` | `B-07` |
| `B-26` | `B-08` |
| `B-14` | `B-09` |
| `B-27` | `B-10` |
| `B-00` | `B-11` |
| `B-25` | `B-12` |
| `B-29` | `B-13` |
| `B-30` | `B-14` |
| `B-08` | `B-15` |
| `B-09` | `B-16` |
| `B-10` | `B-17` |
| `B-11` | `B-18` |
| `B-12` | `B-19` |
| `B-13` | `B-20` |
| `B-15` | `B-21` |
| `B-16` | `B-22` |
| `B-17` | `B-23` |
| `B-18` | `B-24` |
| `B-19` | `B-25` |
| `B-28` | `B-26` |
| `B-20` | `B-27` |
| `B-21` | `B-28` |
| `B-22` | `B-29` |
| `B-23` | `B-30` |
| `B-24` | `B-31` |
| `B-31` | `B-32` |
| `B-32` | `B-33` |

---

_最終更新: 2026-08-07（**M6 に着手**。B-27 デイリーパネルを完了。着手前に 1日1件のキーと取得方式を
[`D-27`](./decisions/D-27-daily-note.md) で決めた——**決定的 ID `dly_<sprintId>_<date>`** で「1日1件」を
構造的に担保し（`mbr_<oid>` / `usr_<oid>` と同じ発想 — D-21）、`GET` は **get-or-create**（パネルが常に
編集対象と版を持てる）、編集は単一リソースの `PATCH`＋`If-Match`（B-18 と同型）に乗せた。日付は
`YYYY-MM-DD` のみ受け、スプリント期間で縛らない（P-1）。フロントは画面B にデイリーパネルを足し、当日
（Asia/Tokyo）のアジェンダ・議事録を編集して保存、412 は最新を読み直す（D-24）。M3 は 3/4（残り B-14
任意）、M4・M5 は達成。M6 は 1/3（残り B-28・B-29）。次は B-28（NextAction 表示）。B-series 26/33＋
EX 2/2）_
