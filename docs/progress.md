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
| **M3** | 開発の土台（テスト/CI/API規約/リポジトリ規約） | B-11 〜 B-14 | 🟨 1 / 4（B-12 完了・B-11 進行中） |
| **M4** | プロダクトバックログが運用できる | B-15 〜 B-20 | 0 / 6 |
| **M5** | ★**スプリントが1周回る**（ここからドッグフーディング） | B-21 〜 B-26 | 0 / 6 |
| **M6** | デイリースクラムがこの画面だけで完結する | B-27 〜 B-29 | 0 / 3 |
| **M7** | 実運用に耐える | B-30 〜 B-31 | 0 / 2 |
| **M8** | *（将来）* プロジェクトを自分たちで管理できる | B-32 〜 B-33 | 0 / 2 |
| | | **合計** | **11 / 33** |

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
| Q-E | Cosmos の `ORDER BY` が辞書順と一致するか（提案書 Q-1） | B-16 | B-16の最初の作業 |
| Q-F | 楽観排他 412 発生後のUX（再取得マージ／再操作促し） | B-26 | B-23着手前 |

**🔴 Blocker はすべて解消済み。** 残る Q-E は実装時の検証、Q-F は B-23 着手時に決めれば足りる。

### 決定の記録

方針が固まったものは `docs/decisions/` に残す。提案書10章の **D-シリーズを継続**しており、
番号空間は1つ（提案書が「仕様を変更したくなったら、まずこの表を引く」と定めているため）。

| # | 決定 | 対応PBI |
|:---:|:---|:---:|
| [D-19](./decisions/D-19-test-strategy.md) | テスト戦略とCI基盤（4層構成・エミュレータ・カバレッジ方針） | B-11 |
| [D-20](./decisions/D-20-api-conventions.md) | API共通規約（読み書き非対称・RFC 9457・`If-Match`必須・型生成） | B-12 |
| [D-21](./decisions/D-21-bootstrap-and-migration.md) | マイグレーション・ユーザー登録・**認証の実装順序** | B-08, B-10, B-14 |

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

### 🟨 B-11 テスト戦略とCI基盤の確立　`依存: B-01`
> **方針決定済み** → [`D-19`](./decisions/D-19-test-strategy.md)
> pytest / Vitest / Playwright。Cosmos契約テストはエミュレータ、
> **照合順序の検証だけは実サービス**（B-16）。カバレッジは数値目標を置かない。
>
> **土台は一通り整備した（2026-07-26）。** フロントを Karma→**Vitest**（jsdom）へ移行し、
> I-1〜I-7 のテーブル駆動雛形・Cosmos 契約（層3）ハーネス＋**ready ポーリング**CI・
> Playwright 主要5フローの受け皿・ブランチ保護手順書を追加した。`make test` は
> pytest 113件＋Vitest 25件で緑。**残るのは「検証対象の機能がまだ無い／管理者操作が要る」
> 項目のみ**（下の未チェック参照）で、いずれもこのPBI内では閉じられない性質のもの。

- [x] pytest（層1・2）と Vitest（フロント単体）が導入され、1コマンドで走る　`make test`
- [x] **層1・2が Cosmos なしで走る**（Repositoryフェイクを使用 → B-07 と対で実施）
- [x] 不変条件 I-1〜I-7 の**テーブル駆動**テスト雛形がある　`backend/tests/invariants/`（表の自己検査は稼働・振る舞い検査は B-20 で有効化）
- [x] V-1〜V-4 をテスト用鍵ペア＋JWKSスタブで検証している（実テナントに接続しない）　`backend/tests/auth/`（B-04 で実施済み）
- [x] Cosmos契約テスト（412／バッチ原子性／RU）が**エミュレータ上で走る導線がある**　`backend/tests/contract/`＋CI `cosmos-contract`（412・除外パスは実装済み／バッチは雛形。初回CIで実緑を確認）
- [x] エミュレータの起動待ちが**固定sleepではなくreadyポーリング**である　`ci.yml`（証明書エンドポイントを poll）
- [ ] Playwright で主要フロー5本が**通る**　→ 受け皿5本は `frontend/e2e/`（`test.fixme`）。**通るのは対象画面（M4/M5）実装後**。各フローの緑化は担当PBIの完了条件に載せ直した（①B-17 ②B-22 ③B-23 ④B-25 ⑤B-29）
- [ ] GitHub Actions で毎PR実行され、**失敗でマージがブロックされる**　→ 毎PR実行は稼働。**マージブロック（ブランチ保護・管理者操作）は B-13 の完了条件に載せ直した** [`docs/setup/ci-branch-protection.md`](./setup/ci-branch-protection.md)
- [x] 必須4領域（I-1〜I-7／V-1〜V-4／rank／認可）の合意が文書化されている　[`D-19`](./decisions/D-19-test-strategy.md#カバレッジ方針)

> **未チェック2項目の扱い**: どちらも B-11 単独では閉じられない性質のため、**宙に浮かせず
> 担当PBIの完了条件へ明示的に移した**。E2E フローは対象画面が揃う各PBI（①B-17 ②B-22
> ③B-23 ④B-25 ⑤B-29）で `test.fixme` を外して緑にする（ハーネスは完成済み）。マージ
> ブロックは B-13 でブランチ保護を有効化すれば閉じる（手順書あり）。加えて不変条件の
> 振る舞い検査（`tests/invariants/` の skip）は検証関数を持つ **B-20** で有効化する。

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

### ⬜ B-13 リポジトリ規約の整備　`依存: —`
- [ ] LICENSE を配置した
- [ ] README に開発セットアップ手順を書いた
- [ ] コミットメッセージ規約・ブランチ戦略を決めた
- [ ] CONTRIBUTING（または開発ガイド）を用意した
- [ ] **ブランチ保護を有効化し、CI 失敗でマージがブロックされる**（B-11 で導線は完成・管理者操作で閉じる。手順 [`docs/setup/ci-branch-protection.md`](./setup/ci-branch-protection.md)）

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

---

## M4 — プロダクトバックログが運用できる

### ⬜ B-15 PBIのCRUD API　`依存: B-04, B-07`
- [ ] 作成・取得・更新・論理削除ができる
- [ ] 不正な状態遷移（new→ready→inProgress→done 以外）が弾かれる
- [ ] **`PATCH`/`DELETE` は `If-Match` 必須**（欠落は428・不一致は412 — D-20）

### ⬜ B-16 並び替え（rank）　`依存: B-07`
> **最初の作業（Q-E）**: 実データを10件ほど投入し `ORDER BY` の結果が辞書順と一致するか確認する。
> 通らなければ**浮動小数＋定期リバランスに切り替える**（この分岐はB-16の工数を膨らませ得ると認識しておく）。
>
> ⚠️ **この検証は実サービスで行う。エミュレータでの確認は不可**（D-19）。
> エミュレータと実サービスで照合順序が異なった場合、「テストが通っているのに本番で
> 並びが静かに壊れる」という最悪の形になる。一度きりの独立ゲートとして扱い、CIには載せない。

- [ ] **実サービス**で `ORDER BY` が辞書順と一致することを確認済み（不一致なら方式切替を記録）
- [ ] 文字列ランク（fractional indexing・ライブラリ利用・Base36）を採用
- [ ] 生成はサーバー側（**専用エンドポイントに前後の要素IDを渡す** — D-20）
- [ ] 1件を移動したとき更新ドキュメントが**1件だけ**である
- [ ] `ORDER BY rank, id`（ULIDのidをタイブレーカー）で全端末の並びが一致する

### ⬜ B-17 プロダクトバックログ画面　`依存: B-03, B-15, B-16`
- [ ] PBIが優先順位順に並ぶ
- [ ] ドラッグで並び替えできる
- [ ] ステータスを変更できる
- [ ] **`GET /backlog`（画面単位）で1往復。N+1にしない**（D-20）
- [ ] **B-11 の E2E フロー①（サインイン→PBI作成→タスク追加, `frontend/e2e/signin-pbi-task.spec.ts`）の `test.fixme` を外して緑にする**（D-19 主要フロー網羅。タスク追加UIが B-18/B-20 側に載る場合は、それらが揃う時点で緑化してよい）

### ⬜ B-18 PBI詳細　`依存: B-17`
- [ ] 概要を編集できる
- [ ] 完了条件のチェックリストを編集できる
- [ ] `estimate` を編集できる（**任意入力・未設定でも警告を出さない** — D-06）

### ⬜ B-19 PBIの分割　`依存: B-17`
- [ ] 分割で生成したPBIが `parentPbiId` で元を参照する
- [ ] 一覧から分割元を辿れる

### ⬜ B-20 タスクのCRUD　`依存: B-07, B-15`
- [ ] I-1〜I-5 のバリデーションが**単一の関数に集約**されている
- [ ] I-4: 種別判定は `pbiId` の有無ではなく **`taskType`** で行う
- [ ] `taskType='team'`（親PBIなし）でも作成できる
- [ ] **B-11 の不変条件テーブル駆動テストの振る舞い検査を有効化する** — `app.tasks.validation` に `check_invariants(doc) -> list[str]`（違反した不変条件IDの列）を実装し、`backend/tests/invariants/` の `pytest.importorskip` による skip が外れて緑になる（D-19 の必須4領域の1つ。違反IDは B-12 の `violations` の `rule` と揃える）

---

---

## M5 — スプリントが1周回る ★ここからドッグフーディング

### ⬜ B-21 スプリントのCRUD　`依存: B-07`
- [ ] 期間とゴールを設定できる
- [ ] `planned` / `active` / `closed` が遷移する

### ⬜ B-22 プランニングモード（右ペイン）　`依存: B-17, B-20, B-21`
- [ ] PBIのチェックで配下の未完了タスクに `sprintId=S` が付く
- [ ] **タスク0件のPBIをチェックすると「タスク分解」タスクが1件生成される**（D-15）
- [ ] 外すと**未完了タスクのみ** `sprintId=null` に戻る（完了タスクは動かさない — I-5）
- [ ] 上記の規則が**専用エンドポイントとしてサーバー側に閉じている**（D-20）
- [ ] **B-11 の E2E フロー②（プランニング, `frontend/e2e/planning.spec.ts`）の `test.fixme` を外して緑にする**（タスク0件のPBIで「タスク分解」生成まで含む — D-19）

### ⬜ B-23 スプリント画面のボード　`依存: B-20, B-21`
- [ ] todo / doing / done をドラッグで移動できる
- [ ] ブロック中フラグを立てられる
- [ ] **2人が同時に触っても片方の更新が消えない**（楽観排他）
- [ ] **`GET /board`（画面単位）で1往復**。各要素に `_etag` が含まれる（D-20）
- [ ] **B-11 の E2E フロー③（ボード操作 todo→doing→done, `frontend/e2e/board.spec.ts`）の `test.fixme` を外して緑にする**（D-19）

### ⬜ B-24 進捗表示　`依存: B-23`
- [ ] 提案書 05章の**2本バー**（計画タスク / チームタスク）が表示される
- [ ] マーカーが**営業日**で計算されている（暦日にしない）
- [ ] **警告色を使っていない**（色は種別の区別のみ — P-1 / D-13）
- [ ] （要確認）祝日・タイムゾーンの扱いを決めた
- [ ] **「今日」が注入可能で、日付を固定してテストできる**（D-19。B-25の終了処理も同様）

### ⬜ B-25 スプリント終了処理　`依存: B-21, B-23`
- [ ] 持ち越し対象の一覧をプレビューしてから確定できる（`close/preview` と `close` を分ける — D-20）
- [ ] **完了タスクは移動しない**（未完了のみ次スプリントへ）
- [ ] 強制も警告もせず事実だけ見せる（P-1）
- [ ] **B-11 の E2E フロー④（スプリント終了・完了タスクは動かず未完了だけ持ち越し, `frontend/e2e/sprint-close.spec.ts`）の `test.fixme` を外して緑にする**（D-19）

### ⬜ B-26 楽観排他（412）のUX方針と実装　`依存: B-23`
> **Q-F**: B-23は412の**検出**を保証するが、**発生後どうするか**が未定義。
> 朝会の同時操作が前提なので体験を左右する。B-23着手時に決める。

- [ ] 412発生時の振る舞いを決定（自動再取得マージ / ユーザーに再操作を促す 等）
- [ ] **412応答に最新値を含めるかを決定**（D-20が判断を委ねている）
- [ ] 決めた振る舞いがボード操作で一貫して適用される
- [ ] 更新が黙って消える経路が存在しないことを確認

---

---

## M6 — デイリースクラムがこの画面だけで完結する

### ⬜ B-27 デイリーパネル　`依存: B-23`
- [ ] アジェンダと議事録を編集できる
- [ ] **1日1ドキュメント**で保存される（肥大化と同時編集競合を避ける）

### ⬜ B-28 NextActionの表示　`依存: B-27`
- [ ] 前スプリントのアクションが今スプリントのパネルに出る
- [ ] 完了にできる

### ⬜ B-29 未割当のチームタスク　`依存: B-17, B-22`
- [ ] スプリントから外したチームタスクがバックログ画面に現れる
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

_最終更新: 2026-07-26（B-12 API共通規約 完了。problem+json／If-Match 必須／OpenAPI→TS 型生成。
B-11 テスト基盤マージ済み・進行中。B-11 の後続待ち申し送り〔E2E fixme・不変条件の振る舞い検査・
ブランチ保護〕を担当PBIの完了条件へ移設）_
