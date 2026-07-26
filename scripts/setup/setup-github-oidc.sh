#!/usr/bin/env bash
#
# B-06 の下ごしらえ — GitHub Actions から Azure へ「シークレットレス」でデプロイする
#
# 発行済みの publish profile をシークレットとして GitHub に貼る方式は、値が漏れると
# そのまま本番を書き換えられる。代わりに OIDC（フェデレーション資格情報）を使う:
#   - GitHub Actions が発行する短命トークンで azure/login する
#   - 保存する秘密が無い（GitHub に置くのは client/tenant/subscription の ID だけ）
#   - 権限はこのリソースグループの Contributor に限定する（最小権限）
#
# このスクリプトは冪等。何度でも安全に再実行できる。
#
# 使い方:
#   az login
#   AZ_RESOURCE_GROUP=rg-scrum-board AZ_WEBAPP_NAME=scrum-board \
#     ./scripts/setup/setup-github-oidc.sh y-oga-819/scrum-board
#
# 出力された 3 つの値を GitHub の «リポジトリ Variables» に登録する（Secrets ではない。
# ID は秘密ではないうえ、Variables の方が扱いを誤りにくい）:
#   AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_SUBSCRIPTION_ID
set -euo pipefail

REPO="${1:-}"
if [[ -z "${REPO}" || "${REPO}" != */* ]]; then
  echo "使い方: $0 <github-owner>/<repo>   例) $0 y-oga-819/scrum-board" >&2
  exit 1
fi

RESOURCE_GROUP="${AZ_RESOURCE_GROUP:-rg-scrum-board}"
WEBAPP_NAME="${AZ_WEBAPP_NAME:-scrum-board}"
APP_NAME="${AZ_GH_APP_NAME:-github-deploy-scrum-board}"   # デプロイ専用のアプリ登録名
# デプロイを許すブランチ。既定は main（deploy.yml のトリガーと対）。
DEPLOY_BRANCH="${AZ_DEPLOY_BRANCH:-main}"

command -v az >/dev/null 2>&1 || { echo "❌ az CLI が見つからない。" >&2; exit 1; }
SUBSCRIPTION_ID="$(az account show --query id -o tsv 2>/dev/null || true)"
TENANT_ID="$(az account show --query tenantId -o tsv 2>/dev/null || true)"
[[ -n "${SUBSCRIPTION_ID}" ]] || { echo "❌ 'az login' を先に。" >&2; exit 1; }

log() { printf '\n\033[36m▶ %s\033[0m\n' "$*"; }

# ---- デプロイ専用アプリ登録（無ければ作る） -----------------------------------
log "アプリ登録 ${APP_NAME}"
APP_ID="$(az ad app list --display-name "${APP_NAME}" --query "[0].appId" -o tsv 2>/dev/null || true)"
if [[ -z "${APP_ID}" ]]; then
  APP_ID="$(az ad app create --display-name "${APP_NAME}" --query appId -o tsv)"
  echo "  ✅ 作った (${APP_ID})"
else
  echo "  ✅ 既にある (${APP_ID})"
fi

# サービスプリンシパル（無ければ作る）。
log "サービスプリンシパル"
if ! az ad sp show --id "${APP_ID}" --output none 2>/dev/null; then
  az ad sp create --id "${APP_ID}" --output none
  echo "  ✅ 作った"
else
  echo "  ✅ 既にある"
fi
SP_OBJECT_ID="$(az ad sp show --id "${APP_ID}" --query id -o tsv)"

# ---- フェデレーション資格情報（GitHub → Azure の信頼） -------------------------
# subject を «repo:<owner>/<repo>:ref:refs/heads/<branch>» に固定する。
# これで «このリポジトリの main ブランチの Actions» だけがこの権限を借りられる。
log "フェデレーション資格情報（${REPO} @ ${DEPLOY_BRANCH}）"
FIC_NAME="gh-${DEPLOY_BRANCH}"
FIC_SUBJECT="repo:${REPO}:ref:refs/heads/${DEPLOY_BRANCH}"
if az ad app federated-credential list --id "${APP_ID}" --query "[?name=='${FIC_NAME}']" -o tsv | grep -q .; then
  echo "  ✅ 既にある"
else
  az ad app federated-credential create \
    --id "${APP_ID}" \
    --parameters "$(cat <<JSON
{
  "name": "${FIC_NAME}",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "${FIC_SUBJECT}",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
)" \
    --output none
  echo "  ✅ 作った"
fi

# ---- 権限付与（最小権限: リソースグループ限定の Contributor） -------------------
log "ロール割り当て（Contributor / スコープ = リソースグループ ${RESOURCE_GROUP}）"
SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
if az role assignment list --assignee "${APP_ID}" --scope "${SCOPE}" --query "[?roleDefinitionName=='Contributor']" -o tsv | grep -q .; then
  echo "  ✅ 既にある"
else
  # SP 作成直後は AAD 伝播待ちで失敗することがあるため数回リトライする。
  for i in 1 2 3 4 5; do
    if az role assignment create \
        --assignee-object-id "${SP_OBJECT_ID}" \
        --assignee-principal-type ServicePrincipal \
        --role Contributor \
        --scope "${SCOPE}" \
        --output none 2>/dev/null; then
      echo "  ✅ 付与した"
      break
    fi
    echo "  … 伝播待ち (${i}/5)"; sleep $((i * 3))
  done
fi

# ---- 出力 ----------------------------------------------------------------------
cat <<EOF

────────────────────────────────────────────────────────
✅ OIDC の下ごしらえ完了
────────────────────────────────────────────────────────
GitHub の «Settings → Secrets and variables → Actions → Variables»
に以下を «Repository variables» として登録する:

  AZURE_CLIENT_ID        ${APP_ID}
  AZURE_TENANT_ID        ${TENANT_ID}
  AZURE_SUBSCRIPTION_ID  ${SUBSCRIPTION_ID}

さらに «Variables» に App Service 名も登録しておくとワークフローが参照する:

  AZURE_WEBAPP_NAME      ${WEBAPP_NAME}

登録後、main に push すると .github/workflows/deploy.yml が
シークレットレスでデプロイする。
────────────────────────────────────────────────────────
EOF
