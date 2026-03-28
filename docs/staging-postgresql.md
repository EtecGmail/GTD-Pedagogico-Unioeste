# Staging técnico com PostgreSQL real

Este guia descreve a validação mínima do backend contra uma instância **real** de PostgreSQL, mantendo SQLite para desenvolvimento/testes rápidos.

## 1) Pré-requisitos

- Python 3.12+
- Poetry
- Instância PostgreSQL acessível (local, container ou ambiente efêmero)
- Banco dedicado para validação técnica

> Segurança: não registre `DATABASE_URL`/`POSTGRES_STAGING_DATABASE_URL` em logs públicos.

## 2) Configuração de conexão

```bash
export APP_ENV=production
export DATABASE_URL='postgresql://USUARIO:SENHA@HOST:5432/NOME_DO_BANCO'
export POSTGRES_STAGING_DATABASE_URL="$DATABASE_URL"
```

## 3) Aplicação de migrações (idempotência)

Execute duas vezes para validar idempotência:

```bash
poetry run python - <<'PY'
from gtd_backend.persistence import applyMigrations, createDatabaseConnection
import os

url = os.environ['DATABASE_URL']
connection = createDatabaseConnection(databaseUrl=url, environmentName='production')
applyMigrations(connection=connection, databaseUrl=url)
applyMigrations(connection=connection, databaseUrl=url)
print('Migrações aplicadas com sucesso (idempotência OK).')
PY
```

## 4) Smoke tests centrais em PostgreSQL real

```bash
scripts/postgresql_staging_smoke.sh
```

O script executa `tests/test_postgresql_staging.py`, cobrindo:
- autenticação, sessão e logout;
- RBAC aluno/admin (RF-09 admin);
- RF-02 + RF-06;
- RF-03 + RF-08;
- RF-04 + RF-05 + RF-10;
- RF-07 (solicitação de reset cega).

## 5) Regressão em SQLite

Após validar PostgreSQL, rode a suíte padrão:

```bash
poetry run pytest -q
```

Assim garantimos que o caminho SQLite de dev/teste continua íntegro.
