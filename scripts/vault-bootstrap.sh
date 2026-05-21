#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(dirname "$SCRIPT_DIR")

if [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck disable=SC1090
  . "$REPO_ROOT/.env"
fi

: "${VAULT_ADDR:=http://localhost:8200}"
: "${VAULT_TOKEN:=devroot}"
: "${JWT_SECRET:?Set JWT_SECRET to the signing secret}"
: "${GEMINI_API_KEY:=${OPENAI_API_KEY:-}}"

if [ -z "${GEMINI_API_KEY:-}" ] && [ -z "${VOYAGE_API_KEY:-}" ]; then
  echo "Set GEMINI_API_KEY or VOYAGE_API_KEY before running this script. OPENAI_API_KEY is still accepted as a legacy alias for GEMINI_API_KEY." >&2
  exit 1
fi

: "${DB_PASSWORD:?Set DB_PASSWORD to the database password}"
: "${MINIO_ROOT_USER:?Set MINIO_ROOT_USER to the MinIO access key}"
: "${MINIO_ROOT_PASSWORD:?Set MINIO_ROOT_PASSWORD to the MinIO secret key}"
: "${GITHUB_TOKEN:?Set GITHUB_TOKEN to the GitHub token}"

export VAULT_ADDR VAULT_TOKEN

echo "Waiting for Vault at ${VAULT_ADDR}..."
until vault status >/dev/null 2>&1; do
  sleep 1
done

if vault secrets list | grep -q '^kv/'; then
  echo "KV v2 is already enabled."
else
  vault secrets enable -path=kv -version=2 kv
fi

vault kv put kv/copilot \
  jwt_secret="$JWT_SECRET" \
  openai_api_key="$OPENAI_API_KEY" \
  db_password="$DB_PASSWORD" \
  minio_access_key="$MINIO_ROOT_USER" \
  minio_secret_key="$MINIO_ROOT_PASSWORD" \
  github_token="$GITHUB_TOKEN"

if [ -n "${GEMINI_API_KEY:-}" ]; then
  set -- "$@" gemini_api_key="$GEMINI_API_KEY"
fi

if [ -n "${VOYAGE_API_KEY:-}" ]; then
  set -- "$@" voyage_api_key="$VOYAGE_API_KEY"
fi

"$@"

cat <<'EOF' | vault policy write copilot -
path "kv/data/copilot" {
  capabilities = ["read"]
}
EOF

if [ "${CREATE_TOKEN:-false}" = "true" ]; then
  vault token create -policy=copilot -format=json
fi

echo "Vault bootstrap complete."
