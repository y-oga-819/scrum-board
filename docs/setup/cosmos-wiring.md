# Cosmos を App Service に配線して点灯させる（手順書）

デプロイ済みの App Service は、**Cosmos の接続情報（`COSMOS_*`）が未設定だと「DB 無し」
モードで起動する**（`backend/app/main.py` の lifespan）。この状態では:

- `GET /api/me` がブートストラップ（`ensure_bootstrapped`）を飛ばし、所属が空になる
  → 画面に「**どのプロダクトにも属していません（所属なし）**」と出る。
- product スコープの API（`/api/products/{pid}/…`）は `require_member` が repo=None で
  **503** を返す（B-15/B-16 を本番で確認できない）。

この手順書は、**Cosmos を用意・配線して認証だけの状態から「所属あり」まで点灯させる**ための
一度きりの作業をまとめたもの。az CLI を主にし（Data Explorer がグレーでも進められる）、
GUI でやる場合の場所も併記する。

> **前提**: `az login` 済みで、対象サブスクリプションが選択されている
> （`az account set --subscription <ID>`）。az CLI はローカル、または Azure ポータル上部の
> **Cloud Shell（`>_`）**でも動く。Cloud Shell は Data Explorer と無関係に使える。

---

## 0. 値と状態の確認（最初に1回）

以降で使うリソース名・接続値を確定させ、**Cosmos アカウントが「使える状態」か**を先に見る。
名前は環境で違うので、既定値（`rg-scrum-board` / `scrum-board-yoga` / `cosmos-scrum-board` /
`scrumboard`）を鵜呑みにせず実物を確認する。

```bash
# App Service と所属 RG・ホスト名（az が正しいサブスクを見ているかの確認も兼ねる）
az webapp list --query "[].{name:name, rg:resourceGroup, host:defaultHostName}" -o table
```

> ⚠️ **`az cosmosdb list` は当てにしない。** 失敗状態のアカウントや API バージョンの都合で
> **存在するのに空を返す**ことがある。存在確認は型指定の resource list か、名前指定の
> `show` を使う:
>
> ```bash
> az resource list --resource-type Microsoft.DocumentDB/databaseAccounts \
>   --query "[].{name:name, rg:resourceGroup}" -o table
> ```

Cosmos アカウントの**状態**を名前指定で確認する（ここが今回の肝）:

```bash
az cosmosdb show -g rg-scrum-board -n cosmos-scrum-board \
  --query "{state:provisioningState, disableLocalAuth:disableLocalAuth, publicNetwork:publicNetworkAccess, endpoint:documentEndpoint}" -o table
```

- `state` = **`Succeeded`** … 使える。→ **Step 2**（DB 作成）へ進む
- `state` = **`Failed`** … 作成が途中で失敗した器が残っている。**Step 1 で削除して作り直す**
- `NotFound` 系エラー … アカウントが無い。**Step 1 で新規作成する**
- `disableLocalAuth` が `true` … キー方式が使えない。下記で解除するか Managed ID へ（B-31）
- `publicNetwork` が `Disabled` … App Service から到達できない。公開アクセスを許可するか
  VNet 統合が要る

この手順書では以下を例として使う（自分の値に読み替える）:

| 役割 | 値（例） | 環境変数 |
|:---|:---|:---|
| リソースグループ | `rg-scrum-board` | — |
| Cosmos アカウント | `cosmos-scrum-board` | — |
| App Service | `scrum-board-yoga` | — |
| データベース名 | `scrumboard` | `COSMOS_DATABASE` |
| エンドポイント | `https://cosmos-scrum-board.documents.azure.com:443/` | `COSMOS_ENDPOINT` |
| プライマリキー | （Step 3 で取得） | `COSMOS_KEY` |

キー認証を解除する場合（`disableLocalAuth=true` のとき。PoC 向けの最短。恒久運用なら
Managed ID を検討）:

```bash
az resource update --ids $(az cosmosdb show -g rg-scrum-board -n cosmos-scrum-board --query id -o tsv) \
  --set properties.disableLocalAuth=false
```

---

## Step 1. Cosmos アカウントを用意する（無い／`Failed` のとき）

**なぜ**: 後続（DB 作成・アプリの接続）は**使える状態（`Succeeded`）のアカウント**を前提に
する。作成が途中で失敗した器（`Failed`）は endpoint も払い出されず、Data Explorer もグレーに
なり、DB 作成は `BadRequest`（"failed provisioning state … delete before recreate"）で弾かれる。
Azure は失敗状態のアカウントを**その場で修復できない**ので、**削除して作り直す**しかない。

> Step 0 で `state=Succeeded` だったなら、このステップは**丸ごとスキップ**して Step 2 へ。

### 1-a.（`Failed` のときだけ）失敗した器を削除する

中身は無い（一度も使える状態になっていない）ので削除は安全。

```bash
az cosmosdb delete -g rg-scrum-board -n cosmos-scrum-board --yes
```

数分かかる。**完全に消えてから**次へ（残っていると名前衝突で作成が失敗する）:

```bash
az cosmosdb show -g rg-scrum-board -n cosmos-scrum-board -o table
# → NotFound 系エラーになれば削除完了
```

### 1-b. アカウントを作成する（無料レベル）

```bash
az cosmosdb create \
  --name cosmos-scrum-board \
  --resource-group rg-scrum-board \
  --locations regionName=japaneast failoverPriority=0 isZoneRedundant=False \
  --enable-free-tier true \
  --default-consistency-level Session
```

- ★**リージョン容量に注意**。作成が `ServiceUnavailable` / high demand で落ちたら、
  `regionName` を `japanwest`（App Service と同居で遅延も減る）や他リージョンに変えて再実行。
  過去にこのプロジェクトが実際に踏んだ壁（B-05: japanwest が容量不足で Cosmos を japaneast へ
  逃がした）。
- 無料レベルは**1サブスクリプションに1つ**。別アカウントが無料枠を握っていると失敗する
  → その枠を使っていた失敗アカウントを 1-a で消してあれば `--enable-free-tier true` のままで
  よい。どうしても取れなければ `--enable-free-tier` を外す（課金対象。予算アラートは設定済み）。
- 5〜10 分かかる。**完了を確認**してから Step 2 へ:

```bash
az cosmosdb show -g rg-scrum-board -n cosmos-scrum-board --query provisioningState -o tsv
# → Succeeded なら成功
```

---

## Step 2. データベース `scrumboard` を作る（コンテナは作らない）

**なぜ**: アプリは `client.get_database_client(name)` で DB ハンドルを取るだけで、**DB 自体は
作らない**（`backend/app/data/settings.py`）。DB が無いとコンテナ作成時に「database not
found」で起動が失敗する。一方、**コンテナ `documents` はアプリが起動時に自動生成する**
（PK `/productId` ＋長文フィールドのインデックス除外つき。`provisioning.ensure_container`）。
だから**手で作るのは DB だけ／コンテナは作らない**（手作りすると PK を間違える）。

**操作（az CLI）**:

```bash
az cosmosdb sql database create \
  --account-name cosmos-scrum-board \
  --resource-group rg-scrum-board \
  --name scrumboard
```

> GUI でやる場合: Data Explorer → **New Database** → id `scrumboard`。**「Provision
> throughput（DB 共有スループット）」はオフ**にする（アプリが作るコンテナが既定
> 400 RU/s＝無料枠内を自分で持つ）。「New Container」は使わない（コンテナまで手作りに
> なるため）。Data Explorer がグレーなら az CLI / Cloud Shell を使う。

**確認**:

```bash
az cosmosdb sql database show \
  --account-name cosmos-scrum-board -g rg-scrum-board --name scrumboard \
  --query id -o tsv
# → .../sqlDatabases/scrumboard が出れば OK
```

---

## Step 3. App Service に `COSMOS_*` を登録して再起動

**なぜ**: 起動時の lifespan が `COSMOS_ENDPOINT / COSMOS_KEY / COSMOS_DATABASE` を読んで
`is_configured` が真になると、リポジトリを構築して DB モードで立ち上がる。3つ揃わないと
「DB 無し」のまま。

**値の取得**:

```bash
# COSMOS_ENDPOINT
az cosmosdb show -g rg-scrum-board -n cosmos-scrum-board --query documentEndpoint -o tsv

# COSMOS_KEY（プライマリキー。取り扱い注意・チャットや画像に貼らない）
az cosmosdb keys list -g rg-scrum-board -n cosmos-scrum-board --query primaryMasterKey -o tsv
```

**登録（az CLI。この set は自動で再起動が走る）**:

```bash
az webapp config appsettings set \
  --name scrum-board-yoga --resource-group rg-scrum-board \
  --settings \
    COSMOS_ENDPOINT="https://cosmos-scrum-board.documents.azure.com:443/" \
    COSMOS_KEY="<Step で取得したプライマリキー>" \
    COSMOS_DATABASE="scrumboard"
```

> GUI でやる場合: **App Service → 設定 → 環境変数 → アプリケーション設定** →「＋ 追加」で
> 上の3件を入れる →「適用」。「デプロイ スロット設定」のチェックは不要。適用で再起動が走る。
> キーは値がマスクされて保存される。

念のため明示再起動:

```bash
az webapp restart --name scrum-board-yoga --resource-group rg-scrum-board
```

**確認（キー以外が入っているか。キーは表示しない）**:

```bash
az webapp config appsettings list --name scrum-board-yoga -g rg-scrum-board \
  --query "[?name=='COSMOS_ENDPOINT' || name=='COSMOS_DATABASE'].{name:name, value:value}" -o table
```

---

## Step 4. 起動時の配線を確認する（ログ）

**なぜ**: 再起動後、lifespan が「コンテナ作成 → マイグレーション適用」まで行う。ここで
`documents` コンテナと `prd_sandbox`（サンドボックス）/ `prd_scrum_board`（スクラムボード）の
product ドキュメントが作られる（`run_migrations`）。ログでこれが起きたことを確かめる。

**操作（ログをストリーム）**:

```bash
# 初回はアプリログを有効化（未設定なら）
az webapp log config --name scrum-board-yoga -g rg-scrum-board \
  --application-logging filesystem --level information

az webapp log tail --name scrum-board-yoga -g rg-scrum-board
```

**期待するログ**（`main.py` が出す）:

```
Cosmos に接続しました（リポジトリを app.state に配置）。
マイグレーションを適用しました: 001, 002        # 初回のみ。2回目以降は出ない（冪等）
```

- `Cosmos 未構成のため DB 無しで起動します` が出る → Step 3 の設定が反映されていない
  （名前の綴り／再起動漏れ）。
- 起動が失敗する／`documents` 作成で例外 → キーが誤り・`disableLocalAuth=true`・
  `publicNetwork=Disabled`・アカウントが `Failed` のいずれか（Step 0 / Step 1 を見直す）。

**コンテナができたかの確認**（データ面のクエリは az CLI では扱いにくいので、コンテナの
存在で代替。product の中身は Step 5 の `/api/me` で確認する）:

```bash
az cosmosdb sql container show \
  --account-name cosmos-scrum-board -g rg-scrum-board -d scrumboard -n documents \
  --query "{id:id, partitionKey:partitionKey.paths}" -o table
# → id=documents / partitionKey=['/productId'] なら OK
```

---

## Step 5. `/api/me` を叩いて「所属なし」が消えることを確認

**なぜ**: `GET /api/me` は毎回 `ensure_bootstrapped` を呼び、**初回サインインなら user と
サンドボックスの member を作る**（冪等）。ここで初めて自分が `prd_sandbox` の member になる。

**操作**: 公開 URL（`https://scrum-board-yoga.azurewebsites.net`）に**サインインした状態で
アクセス／リロード**する。フロントが `/api/me` を叩く。

**期待する結果**:

- 「どのプロダクトにも属していません（所属なし）」の表示が消える。
- **プロダクトセレクタに「サンドボックス」**（`prd_sandbox`）が現れ、「選択中のプロダクト」が
  それになる。
- `API が検証した oid` は従来どおり表示される（この値が Step 6 で使う自分の oid）。

まだ「所属なし」のまま → Step 4 のログを確認（DB 無しで起動していないか）。

---

## Step 6.（任意）本番プロジェクト `prd_scrum_board` に自分を登録

**なぜ**: サンドボックスは全員自動参加だが、**本番（スクラムボード）は権限を緩めない**。
入るには明示登録が要る（`scripts/add_member.py`・再実行可能）。このアプリ自身のバックログを
本番プロジェクトで管理したいならこれを行う。

**自分の oid を確認**（アプリ画面の「API が検証した oid」と同じ値）:

```bash
az ad signed-in-user show --query id -o tsv
```

**登録（リポジトリのルートで、backend の依存を使って実行）**:

```bash
COSMOS_ENDPOINT="https://cosmos-scrum-board.documents.azure.com:443/" \
COSMOS_KEY="<プライマリキー>" \
COSMOS_DATABASE="scrumboard" \
  uv run --project backend python scripts/add_member.py \
    --product prd_scrum_board --oid <自分のoid> --role admin
```

**期待する出力**:

```
registered: product=prd_scrum_board oid=<oid> role=admin
```

**確認**: 公開 URL を再度リロードすると、プロダクトセレクタに **「スクラムボード」**
（`prd_scrum_board`）が増える。

---

## 点いたあとの確認（B-15 / B-16 の API）

所属が付けば、product スコープ API が 503 ではなく通るようになる。画面（B-17）は未実装
なので、確認は API レベル（またはローカルの `make dev-fake`）で行う:

- ローカルでロジックだけ確かめるなら `make dev-fake`（サインイン・Cosmos 不要。
  [`dev-fake.md`](./dev-fake.md)）。
- 実 Cosmos 相手の rank 照合順序（Q-E）を検証するなら `scripts/verify_rank_ordering.py`
  （`COSMOS_*` を渡して実行。B-16 の唯一の残作業）。

---

## トラブルシューティング早見表

| 症状 | 原因の候補 | 見るところ |
|:---|:---|:---|
| `az cosmosdb list` が空 | list の取りこぼし（存在しても空を返す） | `az resource list --resource-type …` / 名前指定 `show` で確認 |
| `az cosmosdb show` が `state=Failed` | 作成が途中で失敗した器が残存 | **Step 1**（削除して作り直す） |
| DB 作成が `BadRequest`（failed provisioning state） | 同上 | **Step 1** |
| アカウント作成が `ServiceUnavailable` | リージョン容量不足 | Step 1-b で `regionName` を変える |
| 画面が「所属なし」のまま | `COSMOS_*` 未反映 / 再起動漏れ | Step 4 ログに「DB 無しで起動」が出ていないか |
| product API が 503 | repo=None（DB 無し起動） | 同上 |
| 起動失敗 / コンテナ作成で例外 | キー誤り・`disableLocalAuth=true`・`publicNetwork=Disabled` | Step 0 の各項目 |
| ログに「database not found」 | Step 2（DB 作成）未実施 | Step 2 |
| Data Explorer がグレー | アカウントが `Failed` / ネットワーク制限 / キー無効 / ブラウザ | Step 0 → 該当すれば Step 1 |

## 再現性についての申し送り

この配線はいま手作業だが、本来は `scripts/setup/provision-azure.sh` が Cosmos 作成後に
`COSMOS_ENDPOINT / COSMOS_KEY / COSMOS_DATABASE` を App Service の app settings に流し込む
べき箇所（現状は `ENTRA_*` の3つしか入れていない）。恒久化するときはそこへ反映する。
キーの平文保存を避けるなら Managed Identity + RBAC か Key Vault 参照へ寄せる（B-31）。
