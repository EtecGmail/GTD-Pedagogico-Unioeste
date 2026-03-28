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
from urllib.parse import urlparse

database_url = os.environ["POSTGRES_STAGING_DATABASE_URL"]
parsed = urlparse(database_url)
scheme = parsed.scheme or "database"
host = parsed.hostname or "host-indefinido"
port = f":{parsed.port}" if parsed.port else ""
database = parsed.path.lstrip("/") or "db-indefinido"
print(f"[info] Banco alvo: {scheme}://***@{host}{port}/{database}")
PY

poetry run pytest -q tests/test_postgresql_staging.py -m "postgresql and integration"
