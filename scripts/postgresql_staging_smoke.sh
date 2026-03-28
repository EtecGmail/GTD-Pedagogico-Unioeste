#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${POSTGRES_STAGING_DATABASE_URL:-}" ]]; then
  echo "[erro] Defina POSTGRES_STAGING_DATABASE_URL antes de executar." >&2
  exit 1
fi

echo "[info] Executando validação técnica com PostgreSQL real (URL mascarada)."
python - <<'PY'
import os
from gtd_backend.persistence import _redactDatabaseUrl
print(f"[info] Banco alvo: {_redactDatabaseUrl(os.environ['POSTGRES_STAGING_DATABASE_URL'])}")
PY

poetry run pytest -q tests/test_postgresql_staging.py -m "postgresql and integration"
