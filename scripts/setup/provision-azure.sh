#!/usr/bin/env bash
#
# B-05 — Azure リソースを用意する（再実行可能）
#
# 提案書 09章「環境構築の再現性」に従い、Azure リソースの作成は az CLI スクリプトを
# 手順の中心に置く。ポータルのクリック手順は UI 変更で静かに陳腐化し、古くなったことに
# 気づけないためである。このスクリプトは **何度実行しても同じ状態に収束する**
# （冪等）ように書いてある。無料枠の作り直し・検証環境の追加で必ず再実行される。
#
# 作るもの:
#   - リソースグループ
#   - App Service プラン（F1 = 無料。Linux）
#   - Web App（Python 3.11。フロント + API を同居配信する単一 App Service）
#   - Cosmos DB アカウント（★無料レベルを明示的に選択）＋ データベース
#   - 予算アラート（★Azure には自動の支出上限がないため初日に設定する）
#
# 作らないもの（別スクリプト）:
#   - Entra ID アプリ登録        → scripts/setup/register-entra-app.sh（B-02）
#   - GitHub Actions のデプロイ権限 → scripts/setup/setup-github-oidc.sh（B-06）
#
# 使い方:
#   az login
#   az account set --subscription "<SUBSCRIPTION_ID or NAME>"
#   ./scripts/setup/provision-azure.sh
#
# 主要な値は環境変数で上書きできる（既定値は下の設定ブロック参照）。
set -euo pipefail

# ---- 設定（環境変数で上書き可能） ------------------------------------------------
# App Service の名前はグローバルに一意でなければならない（<name>.azurewebsites.net）。
# 既定は衝突しやすいので、初回に AZ_WEBAPP_NAME を自分用の値に決めて控えておくこと。
LOCATION="${AZ_LOCATION:-japaneast}"
RESOURCE_GROUP="${AZ_RESOURCE_GROUP:-rg-scrum-board}"
PLAN_NAME="${AZ_PLAN_NAME:-plan-scrum-board}"
WEBAPP_NAME="${AZ_WEBAPP_NAME:-scrum-board}"
COSMOS_ACCOUNT="${AZ_COSMOS_ACCOUNT:-cosmos-scrum-board}"
COSMOS_DATABASE="${AZ_COSMOS_DATABASE:-scrumboard}"
# Cosmos のリージョンは App Service と別に指定できる。特定リージョンが容量不足
# （ServiceUnavailable / high demand）のとき、空いている近隣リージョンへ逃がすため。
# 既定は LOCATION と同じ（同居）。App Service と別地方にすると遅延が増える点に注意。
COSMOS_LOCATION="${AZ_COSMOS_LOCATION:-$LOCATION}"
PYTHON_RUNTIME="${AZ_PYTHON_RUNTIME:-PYTHON:3.11}"

# 予算アラート。BUDGET_CONTACT は必ず設定する（未設定なら控えめな既定にフォールバック）。
BUDGET_NAME="${AZ_BUDGET_NAME:-budget-scrum-board}"
BUDGET_AMOUNT="${AZ_BUDGET_AMOUNT:-1000}"           # 通貨単位はサブスクリプション既定（例: JPY）
BUDGET_CONTACT="${AZ_BUDGET_CONTACT:-}"             # 通知先メール（カンマ区切り可）

# App Service に流し込む環境変数。B-02 が発行する実値を渡すとサインインが通る
# （未設定でも起動はする。fail closed で実トークンはすべて 401 になる → app/auth/settings.py）。
ENTRA_TENANT_ID="${ENTRA_TENANT_ID:-}"
ENTRA_CLIENT_ID="${ENTRA_CLIENT_ID:-}"

# ---- 前提チェック --------------------------------------------------------------
command -v az >/dev/null 2>&1 || { echo "❌ az CLI が見つからない。https://aka.ms/azcli" >&2; exit 1; }

SUBSCRIPTION_ID="$(az account show --query id -o tsv 2>/dev/null || true)"
if [[ -z "${SUBSCRIPTION_ID}" ]]; then
  echo "❌ ログインしていない。'az login' と 'az account set --subscription ...' を先に。" >&2
  exit 1
fi
echo "▶ サブスクリプション: ${SUBSCRIPTION_ID}"

# ---- ヘルパ: 冪等な「無ければ作る」 ---------------------------------------------
log() { printf '\n\033[36m▶ %s\033[0m\n' "$*"; }

# ---- リソースプロバイダーの登録 ------------------------------------------------
# 新規サブスクリプションでは各リソースプロバイダーが未登録のことがある。未登録のまま
# create すると MissingSubscriptionRegistration で落ちるため、使うものを先に登録する。
#   Microsoft.Web         … App Service
#   Microsoft.DocumentDB  … Cosmos DB
#   Microsoft.Consumption … 予算アラート
# 登録済みなら即返る（冪等）。--wait で「Registered」まで待ってから次に進む。
log "リソースプロバイダーの登録"
for ns in Microsoft.Web Microsoft.DocumentDB Microsoft.Consumption; do
  state="$(az provider show --namespace "${ns}" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)"
  if [[ "${state}" == "Registered" ]]; then
    echo "  ✅ ${ns} 登録済み"
  else
    echo "  … ${ns} を登録中（数分かかることがある）"
    az provider register --namespace "${ns}" --wait
    echo "  ✅ ${ns} 登録完了"
  fi
done

# ---- リソースグループ ----------------------------------------------------------
# RG の location は「メタデータの置き場所」でしかなく、中のリソースは別リージョンでも
# 構わない。既存 RG に別 location で create を投げると InvalidResourceGroupLocation で
# 落ちるため、「無ければ作る」だけにして既存の location はそのまま尊重する
# （リソース自体の配置は下の各コマンドの ${LOCATION} で決まる）。
log "リソースグループ ${RESOURCE_GROUP}"
if az group show --name "${RESOURCE_GROUP}" --output none 2>/dev/null; then
  RG_LOCATION="$(az group show --name "${RESOURCE_GROUP}" --query location -o tsv)"
  echo "  ✅ 既にある（location=${RG_LOCATION}。リソースは ${LOCATION} に作る）"
else
  az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}" --output none
  echo "  ✅ 作った (${LOCATION})"
fi

# ---- App Service プラン（F1・Linux） -------------------------------------------
# F1 は無料枠。既定では選ばれないので --sku F1 を明示する。Linux（--is-linux）で作る。
log "App Service プラン ${PLAN_NAME} (F1 / Linux)"
if az appservice plan show --name "${PLAN_NAME}" --resource-group "${RESOURCE_GROUP}" --output none 2>/dev/null; then
  echo "  ✅ 既にある"
else
  az appservice plan create \
    --name "${PLAN_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --location "${LOCATION}" \
    --sku F1 \
    --is-linux \
    --output none
  echo "  ✅ 作った"
fi

# ---- Web App（Python 3.11） ----------------------------------------------------
log "Web App ${WEBAPP_NAME} (${PYTHON_RUNTIME})"
if az webapp show --name "${WEBAPP_NAME}" --resource-group "${RESOURCE_GROUP}" --output none 2>/dev/null; then
  echo "  ✅ 既にある"
else
  az webapp create \
    --name "${WEBAPP_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${PLAN_NAME}" \
    --runtime "${PYTHON_RUNTIME}" \
    --output none
  echo "  ✅ 作った"
fi

# 起動コマンド: gunicorn + uvicorn ワーカー。F1 は RAM 1GB なので 1 ワーカーに絞る。
# app.main:app は wwwroot 直下に app/ を配置する前提（deploy.yml のパッケージ構成と対）。
log "Web App の起動コマンドと設定"
az webapp config set \
  --name "${WEBAPP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --startup-file "gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:8000 --timeout 120" \
  --output none

# アプリ設定:
#   SCM_DO_BUILD_DURING_DEPLOYMENT=true  … Oryx が requirements.txt から依存を入れる
#   ENTRA_TENANT_ID / ENTRA_CLIENT_ID     … B-02 の実値。トークン検証に使う（auth/settings.py）
#
# SPA_DIST_DIR は**あえて設定しない**。Oryx はビルド成果物を output.tar.zst に圧縮し、
# 起動時に動的なテンポラリ領域へ展開して実行するため、/home/site/wwwroot/spa/browser の
# ような固定の絶対パスは的を外す。config.py が app パッケージからの相対で spa/browser を
# 見つける（deploy.yml が app/ と spa/ を隣同士で同梱している）。
az webapp config appsettings set \
  --name "${WEBAPP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --settings \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    ENTRA_TENANT_ID="${ENTRA_TENANT_ID}" \
    ENTRA_CLIENT_ID="${ENTRA_CLIENT_ID}" \
  --output none
echo "  ✅ 起動コマンドとアプリ設定を反映"

# HTTPS 強制（Entra のリダイレクトは https 前提）。
az webapp update \
  --name "${WEBAPP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --https-only true \
  --output none

# ---- Cosmos DB（★無料レベルを明示） -------------------------------------------
# 無料レベルは 1 サブスクリプションに 1 アカウントのみ。既定では選ばれないため
# --enable-free-tier true を明示する。作り直し時に別アカウントが無料枠を握っていると
# 失敗する点に注意（その場合は既存の無料枠アカウントを流用する）。
log "Cosmos DB アカウント ${COSMOS_ACCOUNT}（無料レベル / ${COSMOS_LOCATION}）"
if az cosmosdb show --name "${COSMOS_ACCOUNT}" --resource-group "${RESOURCE_GROUP}" --output none 2>/dev/null; then
  echo "  ✅ 既にある"
else
  # リージョンが容量不足（ServiceUnavailable）のときは AZ_COSMOS_LOCATION で
  # 空いている近隣リージョンへ逃がす（例: AZ_COSMOS_LOCATION=japaneast）。
  az cosmosdb create \
    --name "${COSMOS_ACCOUNT}" \
    --resource-group "${RESOURCE_GROUP}" \
    --locations regionName="${COSMOS_LOCATION}" failoverPriority=0 isZoneRedundant=False \
    --enable-free-tier true \
    --default-consistency-level Session \
    --output none
  echo "  ✅ 作った（無料レベル / ${COSMOS_LOCATION}）"
fi

# データベース（コンテナは B-07 で PK /productId 付きで作るのでここでは作らない）。
log "Cosmos データベース ${COSMOS_DATABASE}"
az cosmosdb sql database create \
  --account-name "${COSMOS_ACCOUNT}" \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${COSMOS_DATABASE}" \
  --output none 2>/dev/null && echo "  ✅ ある / 作った" || echo "  ✅ 既にある"

# ---- 予算アラート（★初日に必須） ----------------------------------------------
# Azure には自動の支出上限がない。無料枠を超えた瞬間から課金が始まるため、
# 予算アラートを必ず設定する。ARM の Microsoft.Consumption/budgets を az rest で PUT する
# （az consumption のサブコマンドはバージョン差が大きいため、安定した REST を直接叩く）。
log "予算アラート ${BUDGET_NAME}（${BUDGET_AMOUNT}）"
if [[ -z "${BUDGET_CONTACT}" ]]; then
  echo "  ⚠ AZ_BUDGET_CONTACT（通知先メール）が未設定。予算は作るが通知先が空だと届かない。"
  echo "     例) AZ_BUDGET_CONTACT='you@example.com' ./scripts/setup/provision-azure.sh"
fi

# 通知先メールを JSON 配列に変換（カンマ区切り → ["a","b"]）。
CONTACT_JSON="$(python3 - "$BUDGET_CONTACT" <<'PY'
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
emails = [e.strip() for e in raw.split(",") if e.strip()]
print(json.dumps(emails))
PY
)"

# 開始日は当月の 1 日（budgets は月初め起点を要求する）。
BUDGET_START="$(date -u +%Y-%m-01)"
BUDGET_URI="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Consumption/budgets/${BUDGET_NAME}?api-version=2023-11-01"

# 50% / 80% / 100% で通知する（Actual ベース）。100% はほぼ「もう課金が始まる」合図。
BUDGET_BODY="$(cat <<JSON
{
  "properties": {
    "category": "Cost",
    "amount": ${BUDGET_AMOUNT},
    "timeGrain": "Monthly",
    "timePeriod": { "startDate": "${BUDGET_START}T00:00:00Z" },
    "notifications": {
      "actual_50": { "enabled": true, "operator": "GreaterThanOrEqualTo", "threshold": 50,  "contactEmails": ${CONTACT_JSON}, "thresholdType": "Actual" },
      "actual_80": { "enabled": true, "operator": "GreaterThanOrEqualTo", "threshold": 80,  "contactEmails": ${CONTACT_JSON}, "thresholdType": "Actual" },
      "actual_100": { "enabled": true, "operator": "GreaterThanOrEqualTo", "threshold": 100, "contactEmails": ${CONTACT_JSON}, "thresholdType": "Actual" }
    }
  }
}
JSON
)"

az rest --method put --uri "${BUDGET_URI}" --body "${BUDGET_BODY}" --output none
echo "  ✅ 予算アラートを設定（${BUDGET_START} 起点・月次）"

# ---- まとめ --------------------------------------------------------------------
DEFAULT_HOST="$(az webapp show --name "${WEBAPP_NAME}" --resource-group "${RESOURCE_GROUP}" --query defaultHostName -o tsv)"
cat <<EOF

────────────────────────────────────────────────────────
✅ B-05 完了: Azure リソースが揃った
────────────────────────────────────────────────────────
  公開 URL      : https://${DEFAULT_HOST}
  リソースグループ: ${RESOURCE_GROUP}
  App Service   : ${WEBAPP_NAME} (F1 / Linux / ${PYTHON_RUNTIME})
  Cosmos DB     : ${COSMOS_ACCOUNT} / db=${COSMOS_DATABASE}（無料レベル）
  予算アラート  : ${BUDGET_NAME} = ${BUDGET_AMOUNT}

次のステップ:
  1) B-02 の Entra 実値をまだ入れていなければ、下記で反映してから再実行:
       ENTRA_TENANT_ID=... ENTRA_CLIENT_ID=... ./scripts/setup/provision-azure.sh
  2) Entra のリダイレクト URI（SPA プラットフォーム）に本番 SPA を登録:
       https://${DEFAULT_HOST}
       ※末尾スラッシュなし。MSAL は redirectUri=window.location.origin を送るため
         （frontend/src/app/auth/auth.config.ts）。スラッシュ有無が違うと AADSTS で弾かれる。
  3) GitHub Actions からデプロイできるように OIDC を設定:
       AZ_RESOURCE_GROUP=${RESOURCE_GROUP} AZ_WEBAPP_NAME=${WEBAPP_NAME} \\
         ./scripts/setup/setup-github-oidc.sh <github-owner>/<repo>
  4) main に push すると .github/workflows/deploy.yml が自動デプロイする（B-06）
────────────────────────────────────────────────────────
EOF
