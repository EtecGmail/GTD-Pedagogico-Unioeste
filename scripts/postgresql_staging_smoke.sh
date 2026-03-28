#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -z "${POSTGRES_STAGING_DATABASE_URL:-}" ]]; then
  echo "[erro] Defina POSTGRES_STAGING_DATABASE_URL antes de executar." >&2
  exit 1
fi

echo "[info] Executando validação técnica com PostgreSQL real (URL mascarada)."
poetry run python - <<'PY'
import os
from gtd_backend.persistence import _redactDatabaseUrl
print(f"[info] Banco alvo: {_redactDatabaseUrl(os.environ['POSTGRES_STAGING_DATABASE_URL'])}")
PY

poetry run pytest -q tests/test_postgresql_staging.py -m "postgresql and integration"
