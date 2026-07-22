#!/usr/bin/env bash
set -euo pipefail

SITE="${1:?Usage: verify_deployment.sh SITE}"

echo "[china_finance] Checking installed applications on $SITE"
bench --site "$SITE" list-apps | awk 'NF {print $1}' | grep -qx "china_finance"

echo "[china_finance] Running first migration"
bench --site "$SITE" migrate

echo "[china_finance] Running idempotency migration"
bench --site "$SITE" migrate

echo "[china_finance] Building application assets"
bench build --app china_finance

echo "[china_finance] Running deployment health check"
bench --site "$SITE" execute china_finance.api.deployment_health

echo "[china_finance] Deployment verification passed"
