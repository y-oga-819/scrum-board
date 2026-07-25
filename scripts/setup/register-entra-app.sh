#!/usr/bin/env bash
#
# register-entra-app.sh — Entra ID アプリ登録を az CLI で再現する（B-02）
#
# 提案書 08章「アプリ登録チェックリスト」を、ポータルのクリックではなく
# スクリプトで実行する。UI変更で陳腐化しないよう、手順の正はこのファイルに置く
# （提案書 09章「環境構築の再現性」／progress.md B-02）。
#
# 冪等: 同じ表示名のアプリが既にあれば作り直さず、設定だけを再適用する。
#       何度実行しても同じ状態に収束する。
#
# 前提:
#   - az CLI にサインイン済み（`az login`）で、対象テナントが選択されている。
#   - 実行者にアプリ登録の権限がある（アプリケーション開発者ロール、または
#     テナントが一般ユーザーのアプリ登録を許可している）。
#   - uuidgen が使えること（macOS / 主要な Linux に同梱）。
#
# 使い方:
#   APP_HOSTNAME=myscrum.azurewebsites.net ./scripts/setup/register-entra-app.sh
#
#   環境変数（すべて任意。未指定なら既定値）:
#     DISPLAY_NAME   アプリの表示名            （既定: scrum-board）
#     APP_HOSTNAME   本番 App Service のホスト  （既定: <アプリ名>.azurewebsites.net ← 要指定）
#     LOCAL_ORIGIN   ローカル開発オリジン        （既定: http://localhost:4200）
#     GRANT_CONSENT  1 なら管理者同意まで実行     （既定: 0。Global Admin 権限が要る）
#
set -euo pipefail

DISPLAY_NAME="${DISPLAY_NAME:-scrum-board}"
APP_HOSTNAME="${APP_HOSTNAME:-<アプリ名>.azurewebsites.net}"
LOCAL_ORIGIN="${LOCAL_ORIGIN:-http://localhost:4200}"
GRANT_CONSENT="${GRANT_CONSENT:-0}"

GRAPH="https://graph.microsoft.com/v1.0"
MS_GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"   # Microsoft Graph の appId（固定）

# Microsoft Graph 委任スコープの well-known ID（テナントに依らず固定）
OPENID_ID="37f7f235-527c-4136-accd-4a02d197296e"
PROFILE_ID="14dad69e-099b-42c9-810b-d002981feec1"
EMAIL_ID="64a6cdd6-aab1-4aac-94b8-3cc8405e90d0"

log()  { printf '\033[36m▶ %s\033[0m\n' "$*" >&2; }
warn() { printf '\033[33m⚠ %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
guid() { uuidgen | tr 'A-Z' 'a-z'; }

command -v az >/dev/null      || die "az CLI が見つからない。https://aka.ms/azure-cli を参照。"
command -v uuidgen >/dev/null || die "uuidgen が見つからない。"
az account show >/dev/null 2>&1 || die "未サインイン。先に 'az login' を実行する。"

if [[ "$APP_HOSTNAME" == "<アプリ名>.azurewebsites.net" ]]; then
  warn "APP_HOSTNAME が既定のプレースホルダのまま。本番リダイレクトURIは仮の値になる。"
  warn "本番ホストが決まったら APP_HOSTNAME=... を指定して再実行すること（冪等なので安全）。"
fi

TENANT_ID="$(az account show --query tenantId -o tsv)"
PROD_ORIGIN="https://${APP_HOSTNAME}"
EASY_AUTH_CALLBACK="https://${APP_HOSTNAME}/.auth/login/aad/callback"

log "テナント: ${TENANT_ID}"
log "表示名  : ${DISPLAY_NAME}"

# ── 1. アプリ登録（無ければ作成、有れば再利用）────────────────────────────────
#     シングルテナント（AzureADMyOrg）で登録する。外部テナントのユーザーを
#     サインイン画面に到達させない（提案書 08章）。
OBJECT_ID="$(az ad app list --display-name "$DISPLAY_NAME" --query '[0].id' -o tsv)"
if [[ -z "${OBJECT_ID:-}" ]]; then
  log "アプリを新規作成する"
  OBJECT_ID="$(az ad app create \
    --display-name "$DISPLAY_NAME" \
    --sign-in-audience AzureADMyOrg \
    --query id -o tsv)"
else
  log "既存アプリを再利用する（objectId=${OBJECT_ID}）"
  az ad app update --id "$OBJECT_ID" --sign-in-audience AzureADMyOrg >/dev/null
fi
APP_ID="$(az ad app show --id "$OBJECT_ID" --query appId -o tsv)"
log "clientId (appId) = ${APP_ID}"

# ── 2. リダイレクトURI（SPA と Web を分けて登録）──────────────────────────────
#     MSAL.js が実際に使う本番・ローカルの2つは "spa" プラットフォームに置く。
#     Web に置くと AADSTS9002326（cross-origin token redemption は SPA 限定）で
#     必ず詰まる — 最頻出の事故（提案書 08章 / D-10）。
#     Easy Auth のコールバックはサーバー側フロー用なので "web" に置く（保険。D-10）。
log "リダイレクトURI を設定する（spa: 本番/ローカル, web: Easy Auth 保険）"
BODY_REDIRECT="$(mktemp)"
cat >"$BODY_REDIRECT" <<JSON
{
  "spa": { "redirectUris": ["${PROD_ORIGIN}", "${LOCAL_ORIGIN}"] },
  "web": { "redirectUris": ["${EASY_AUTH_CALLBACK}"] }
}
JSON
az rest --method PATCH --uri "${GRAPH}/applications/${OBJECT_ID}" \
  --headers 'Content-Type=application/json' --body "@${BODY_REDIRECT}" >/dev/null
rm -f "$BODY_REDIRECT"

# ── 3. APIの公開: スコープ api://<clientId>/access_as_user ───────────────────
#     requestedAccessTokenVersion=2 も同時に設定する。これで発行トークンの
#     iss が .../v2.0 になり、API側の V-3 検証と一致する（提案書 08章）。
#     冪等性: 既存スコープがあれば同じ id を再利用する（有効なスコープの id は
#     変更できないため、新しい GUID を振ると失敗する）。
EXISTING_SCOPE_ID="$(az ad app show --id "$OBJECT_ID" \
  --query "api.oauth2PermissionScopes[?value=='access_as_user'].id | [0]" -o tsv 2>/dev/null || true)"
SCOPE_ID="${EXISTING_SCOPE_ID:-$(guid)}"

log "APIを公開する: api://${APP_ID}/access_as_user （scopeId=${SCOPE_ID}）"
BODY_API="$(mktemp)"
cat >"$BODY_API" <<JSON
{
  "identifierUris": ["api://${APP_ID}"],
  "api": {
    "requestedAccessTokenVersion": 2,
    "oauth2PermissionScopes": [
      {
        "id": "${SCOPE_ID}",
        "value": "access_as_user",
        "type": "User",
        "isEnabled": true,
        "adminConsentDisplayName": "スクラムボードAPIにユーザーとしてアクセスする",
        "adminConsentDescription": "サインインしたユーザーとして、スクラムボードAPIにアクセスすることを許可する。",
        "userConsentDisplayName": "スクラムボードにアクセスする",
        "userConsentDescription": "あなたとして、スクラムボードAPIにアクセスすることを許可する。"
      }
    ]
  }
}
JSON
az rest --method PATCH --uri "${GRAPH}/applications/${OBJECT_ID}" \
  --headers 'Content-Type=application/json' --body "@${BODY_API}" >/dev/null
rm -f "$BODY_API"

# ── 4. APIアクセス許可: Microsoft Graph の openid / profile / email（委任）──────
#     az ad app permission add は重複追加を弾かないため、未設定のときだけ足す。
log "APIアクセス許可を設定する（openid profile email）"
HAS_GRAPH="$(az ad app show --id "$OBJECT_ID" \
  --query "requiredResourceAccess[?resourceAppId=='${MS_GRAPH_APP_ID}'] | length(@)" -o tsv)"
if [[ "$HAS_GRAPH" == "0" ]]; then
  az ad app permission add --id "$APP_ID" \
    --api "$MS_GRAPH_APP_ID" \
    --api-permissions \
      "${OPENID_ID}=Scope" "${PROFILE_ID}=Scope" "${EMAIL_ID}=Scope" >/dev/null
else
  log "Graph の委任許可は設定済み（スキップ）"
fi

# ── 5. エンタープライズアプリ（サービスプリンシパル）────────────────────────────
#     「割り当てが必要 = はい」にして、割り当てたユーザーだけがサインインできる
#     ようにする（ユーザー単位の割り当ては Entra ID Free で可能。提案書 08章）。
log "サービスプリンシパルを用意し、ユーザー割り当てを必須にする"
SP_ID="$(az ad sp list --filter "appId eq '${APP_ID}'" --query '[0].id' -o tsv)"
if [[ -z "${SP_ID:-}" ]]; then
  SP_ID="$(az ad sp create --id "$APP_ID" --query id -o tsv)"
fi
az rest --method PATCH --uri "${GRAPH}/servicePrincipals/${SP_ID}" \
  --headers 'Content-Type=application/json' \
  --body '{"appRoleAssignmentRequired": true}' >/dev/null

# ── 6. （任意）管理者同意 ─────────────────────────────────────────────────────
if [[ "$GRANT_CONSENT" == "1" ]]; then
  log "管理者同意を付与する（Global Admin 権限が必要）"
  az ad app permission admin-consent --id "$APP_ID" \
    || warn "管理者同意に失敗。権限が無い場合はポータルで実施する（手順書 §4 参照）。"
else
  warn "管理者同意は未実行（GRANT_CONSENT=1 で実行可）。openid/profile/email は"
  warn "通常ユーザー同意で足りるが、テナント方針次第では管理者同意が要る。"
fi

# ── 7. 控える値の出力（B-03 フロント / B-04 API 検証で使う）──────────────────
ISSUER="https://login.microsoftonline.com/${TENANT_ID}/v2.0"
JWKS="https://login.microsoftonline.com/${TENANT_ID}/discovery/v2.0/keys"

cat <<SUMMARY

$(printf '\033[32m✓ Entra ID アプリ登録が完了した（冪等・再実行可能）\033[0m')

  控える値（提案書 08章「控えるもの」）:
    TENANT_ID  = ${TENANT_ID}
    CLIENT_ID  = ${APP_ID}
    ※ SPA のためクライアントシークレットは不要。

  後続PBIで使う値:
    API_SCOPE  = api://${APP_ID}/access_as_user
    ISSUER     = ${ISSUER}         # V-3 の期待値
    JWKS_URI   = ${JWKS}           # V-1 の鍵取得元
    AUDIENCE   = ${APP_ID}         # V-2 の期待値

  貼り付け用（.env など。トークンではないのでコミットしても安全）:
    ENTRA_TENANT_ID=${TENANT_ID}
    ENTRA_CLIENT_ID=${APP_ID}
    ENTRA_API_SCOPE=api://${APP_ID}/access_as_user

  次の手動ステップ（手順書 §4 参照 — CLI で完結しない判断が要る部分）:
    1) エンタープライズアプリでサインインを許可するユーザーを割り当てる。
    2) （テナント方針次第）openid/profile/email に管理者同意を与える。
SUMMARY
