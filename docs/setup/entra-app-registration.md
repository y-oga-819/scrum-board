# セットアップ手順書 — Entra ID アプリ登録（B-02）

> **この手順書の位置づけ**
> [`docs/progress.md`](../progress.md) の **B-02「Entra IDにアプリを登録する」** の成果物。
> 設計の正は [提案書](../proposal.html)（08章 認証・認可 / 09章 環境構築の再現性）にあり、
> 本書はそれを**再実行可能な形**に落とした実務手順である。
>
> 提案書 09章の方針に従い、**手順の中心は az CLI スクリプト**
> （[`scripts/setup/register-entra-app.sh`](../../scripts/setup/register-entra-app.sh)）に置く。
> ポータルのクリック手順は UI 変更で静かに陳腐化するため、
> **CLI で完結しない部分だけを本書の文章で補う。**

---

## 0. なぜスクリプト中心なのか

アプリ登録は一度きりの作業に見えるが、**無料枠の作り直し・検証環境の追加・
メンバーの増加で必ず再実行される**（提案書 08/09章）。そして Entra ID の
**設定漏れは後の工程で分かりにくい形で表面化する**。この2点から、手順は
「読んでクリックする文章」ではなく「**流せば同じ状態に収束するスクリプト**」で持つ。

スクリプトは**冪等**である。同じ表示名のアプリが既にあれば作り直さず、設定だけを
再適用する。何度流しても壊れない。

---

## 1. 前提

| 項目 | 内容 |
|:---|:---|
| ツール | [Azure CLI (`az`)](https://aka.ms/azure-cli) と `uuidgen`（macOS / 主要 Linux に同梱） |
| サインイン | `az login` 済みで、**対象テナントが選択されている**こと |
| 権限 | アプリ登録の権限（**アプリケーション開発者**ロール、またはテナントが一般ユーザーのアプリ登録を許可） |
| ライセンス | **Entra ID Free で足りる**（ユーザー単位の割り当てまで可能。グループ単位や条件付きアクセスは P1 以上 — 提案書 09章） |

```bash
az login                      # 対象テナントでサインイン
az account show               # テナントが合っているか確認
# 複数テナントに属する場合:
# az login --tenant <tenantId>
```

---

## 2. 実行

リポジトリのルートで、**本番 App Service のホスト名**を渡して実行する。

```bash
APP_HOSTNAME=<アプリ名>.azurewebsites.net ./scripts/setup/register-entra-app.sh
```

本番ホスト名がまだ決まっていない場合（B-05 より前）は、そのまま実行してよい。
本番リダイレクトURIだけがプレースホルダになる。**ホストが決まったら
`APP_HOSTNAME` を指定して再実行する**（冪等なので安全に上書きされる）。

### 渡せる環境変数

| 変数 | 既定 | 意味 |
|:---|:---|:---|
| `DISPLAY_NAME` | `scrum-board` | アプリの表示名 |
| `APP_HOSTNAME` | `<アプリ名>.azurewebsites.net` | 本番 App Service のホスト |
| `LOCAL_ORIGIN` | `http://localhost:4200` | ローカル開発オリジン |
| `GRANT_CONSENT` | `0` | `1` で管理者同意まで実行（Global Admin 権限が必要） |

スクリプトが行うこと（＝提案書 08章「アプリ登録チェックリスト」の自動化）:

1. **シングルテナント**（`AzureADMyOrg`）でアプリ登録
2. リダイレクトURIを **SPA と Web に分けて**登録（§3 で詳述）
3. API公開 `api://<clientId>/access_as_user` ＋ `requestedAccessTokenVersion: 2`
4. APIアクセス許可 `openid` `profile` `email`（Microsoft Graph 委任）
5. エンタープライズアプリを作成し **「割り当てが必要 = はい」**
6. （任意）管理者同意
7. **控える値**（テナントID / クライアントID ほか）を出力

---

## 3. リダイレクトURI — なぜ SPA と Web を分けるのか（重要）

提案書 08章は3つのリダイレクトURIを「まとめて登録する」と書いているが、
**プラットフォームの割り当てを間違えると `AADSTS9002326` で必ず詰まる**
（最頻出の事故）。スクリプトは次のように**正しく振り分けている**。

| URI | プラットフォーム | 用途 |
|:---|:---|:---|
| `https://<host>` | **SPA** | 本番。MSAL.js が実際に使う |
| `http://localhost:4200` | **SPA** | ローカル開発。MSAL.js が実際に使う |
| `https://<host>/.auth/login/aad/callback` | **Web** | Easy Auth に切替える場合の保険（D-10） |

`AADSTS9002326`（*cross-origin token redemption is permitted only for the
'Single-Page Application' client-type*）は、**MSAL.js が使う URI を Web に
登録したとき**に起きる。だから本番・ローカルの2つは必ず **SPA** に置く。
Easy Auth のコールバックはサーバー側フロー用なので **Web** でよく、こちらは
9002326 を引き起こさない。**ローカル用を忘れると開発初日に止まる**ので3つ入れておく。

---

## 4. CLI で完結しない手動ステップ

以下は「誰を入れるか」「同意を与えられる権限があるか」という**人間の判断**が
絡むため、スクリプトからは切り離してある。ポータル（GUI）での操作を前提に記す。

### 4-1. サインインを許可するユーザーの割り当て（必須）

「割り当てが必要 = はい」にしてあるため、**割り当てたユーザーだけ**がサインインできる。

1. Entra 管理センター → **エンタープライズ アプリケーション** → `scrum-board`
2. **ユーザーとグループ** → **ユーザーの追加** → 対象ユーザーを選ぶ

CLI で行う場合（`<userObjectId>` は `az ad user show --id <upn> --query id -o tsv`）:

```bash
APP_ID=<clientId>
SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' -o tsv)
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_ID/appRoleAssignedTo" \
  --headers 'Content-Type=application/json' \
  --body '{"principalId":"<userObjectId>","resourceId":"'"$SP_ID"'","appRoleId":"00000000-0000-0000-0000-000000000000"}'
```

### 4-2. 管理者同意（テナント方針次第）

`openid` / `profile` / `email` は通常ユーザー同意で足りるが、テナントが
ユーザー同意を無効化している場合は管理者同意が要る。Global Admin なら:

- ポータル: アプリ登録 → **API のアクセス許可** → **管理者の同意を与えます**
- CLI: スクリプトを `GRANT_CONSENT=1` で再実行、または `az ad app permission admin-consent --id <clientId>`

---

## 5. 控える値

スクリプト末尾が出力する。**トークンではない**のでリポジトリにコミットしても安全
（`.env` に置いて B-03 / B-04 で参照する）。

```
ENTRA_TENANT_ID=<tenantId>
ENTRA_CLIENT_ID=<clientId>
ENTRA_API_SCOPE=api://<clientId>/access_as_user
```

後続PBIが使う導出値:

| 値 | 用途 |
|:---|:---|
| `api://<clientId>/access_as_user` | B-03 フロントが要求するスコープ |
| `https://login.microsoftonline.com/<tenantId>/v2.0` | **V-3**（`iss` の期待値） |
| `https://login.microsoftonline.com/<tenantId>/discovery/v2.0/keys` | **V-1**（JWKS の取得元） |
| `<clientId>` | **V-2**（`aud` の期待値） |

---

## 6. 完了条件チェックリスト（B-02 / 提案書 08章）

スクリプトを流し、§4 の手動ステップを終えたら、以下を確認する。
これがそのまま [`docs/progress.md`](../progress.md) の B-02 チェック項目に対応する。

- [ ] **シングルテナント**で登録されている（`signInAudience = AzureADMyOrg`）
- [ ] プラットフォームが **シングルページアプリケーション**（本番・ローカルが **SPA** 側）→ `AADSTS9002326` 回避
- [ ] スコープ **`api://<clientId>/access_as_user`** が公開されている
- [ ] マニフェスト **`requestedAccessTokenVersion: 2`**
- [ ] APIアクセス許可 **`openid` `profile` `email`**
- [ ] エンタープライズアプリ **「割り当てが必要 = はい」** ＋ 利用者を割り当て済み
- [ ] リダイレクトURI **3種**（本番SPA / `localhost:4200` / Easy Auth 保険）が登録済み
- [ ] **テナントID・クライアントID** を控えた（シークレットは不要）
- [ ] **手順が再実行可能な形（az CLI 中心）で残っている** ← 本書とスクリプトがこれを満たす

### 登録内容を CLI で検証する

```bash
APP_ID=<clientId>
az ad app show --id "$APP_ID" --query "{
  audience: signInAudience,
  identifierUris: identifierUris,
  tokenVersion: api.requestedAccessTokenVersion,
  scopes: api.oauth2PermissionScopes[].value,
  spaRedirects: spa.redirectUris,
  webRedirects: web.redirectUris
}"

# 「割り当てが必要」が true か
SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' -o tsv)
az ad sp show --id "$SP_ID" --query appRoleAssignmentRequired
```

---

## 7. トラブルシュート

| 症状 | 原因と対処 |
|:---|:---|
| `AADSTS9002326` | MSAL が使う URI が **Web** に入っている。§3 のとおり本番・ローカルは **SPA** に置く（再実行で修正される） |
| `Insufficient privileges` | アプリ登録／同意の権限不足。アプリケーション開発者ロールの付与、または管理者に §4-2 を依頼 |
| サインインできるが 403 | これは B-09/B-10（認可）の範囲。アプリ登録の問題ではない（`member` 未登録） |
| ローカルでサインインが返ってこない | `http://localhost:4200` が **SPA** リダイレクトに無い。スクリプト再実行で復旧 |

---

_関連: [提案書 08章 認証・認可 / 09章](../proposal.html) ・ [D-10（Easy Auth を使わない）](../proposal.html) ・ [D-21](../decisions/D-21-bootstrap-and-migration.md)_
