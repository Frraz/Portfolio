#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH="${PROJECT_PATH:-/home/ubuntu/Portfolio}"

echo "[smoke] Testando socket..."
curl --unix-socket "${PROJECT_PATH}/gunicorn.sock" http://localhost/healthz -sS -o /dev/null -w "%{http_code}\n" | grep -qE "200|204"

echo "[smoke] Testando Nginx HTTP (host header)..."
code=$(curl -sS -o /dev/null -w "%{http_code}" http://localhost/ -H "Host: portfolio.ferzion.com.br")
if [ "$code" -ne 200 ] && [ "$code" -ne 301 ]; then
  echo "[smoke] Falha: HTTP retornou código $code"
  exit 1
fi

echo "[smoke] OK."