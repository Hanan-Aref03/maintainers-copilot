#!/bin/sh
set -eu

: "${VAULT_ADDR:?Set VAULT_ADDR to the target Vault endpoint}"
: "${VAULT_TOKEN:?Set VAULT_TOKEN to a token with bootstrap permissions}"
: "${JWT_SECRET:?Set JWT_SECRET to the signing secret}"
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY to the OpenAI API key}"
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

cat <<'EOF' | vault policy write copilot -
path "kv/data/copilot" {
  capabilities = ["read"]
}
EOF

if [ "${CREATE_TOKEN:-false}" = "true" ]; then
  vault token create -policy=copilot -format=json
fi

echo "Vault bootstrap complete."
