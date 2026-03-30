# GTD Pedagógico Unioeste

Backend do projeto **GTD Pedagógico Unioeste**, focado em apoio acadêmico para estudantes de Pedagogia da Unioeste com princípios de GTD (captura, organização, execução) e segurança por padrão.

## Visão geral (estado atual)

O backend já entrega uma base funcional com:
- autenticação com hash Argon2id e respostas genéricas de login;
- sessão Bearer com persistência em banco e expiração;
- módulos RF-01 a RF-10 implementados de forma incremental;
- migrações SQL formais por dialeto (SQLite e PostgreSQL) via `applyMigrations`;
- suíte de testes automatizada com foco em regressão e segurança.

> **Padrão de execução local:** SQLite para desenvolvimento/testes rápidos.
>
> **Staging técnico:** PostgreSQL real com validação dedicada.

---

## Stack atual

- **Linguagem:** Python 3.12
- **Gerenciador de dependências:** Poetry
- **API:** FastAPI
- **Testes:** pytest
- **Persistência:**
  - SQLite (dev/test)
  - PostgreSQL (staging/produção)
- **Segurança:** Argon2id para senha, login blindado, eventos de segurança (RF-09), validação de ownership

---

## Pré-requisitos

- Python 3.12+
- Poetry instalado
- (Opcional para staging técnico) Docker + Docker Compose **ou** PostgreSQL acessível externamente
- Shell bash (para scripts em `scripts/`)

---

## Clonar o repositório

```bash
git clone <URL_DO_REPOSITORIO>
cd GTD-Pedagogico-Unioeste
```

---

## Instalação de dependências (Poetry)

```bash
poetry install
```

Para entrar no ambiente virtual:

```bash
poetry shell
```

Ou execute comandos diretamente com `poetry run ...`.

---

## Variáveis de ambiente

### Fluxo local padrão (SQLite)

Nenhuma variável é obrigatória para rodar testes locais padrão.

Opcional:

```bash
export APP_ENV=development
export DATABASE_URL='sqlite:///:memory:'
```

### Fluxo staging técnico (PostgreSQL real)

```bash
export APP_ENV=production
export DATABASE_URL='postgresql://USUARIO:SENHA@HOST:5432/NOME_DO_BANCO'
export POSTGRES_STAGING_DATABASE_URL="$DATABASE_URL"
```

### Chave do cofre (produção/staging)

Para evitar fallback inseguro em ambiente de produção, configure chave ativa:

```bash
export CERTIFICATE_KEY_ACTIVE_VERSION='v1'
export CERTIFICATE_KEY_v1='<CHAVE_FORTE_BASE64_OU_STRING_SECRETA>'
```

> Não commitar segredos em arquivos versionados.

---

## Rodando a suíte local padrão

### Suíte completa (principal)

```bash
poetry run pytest -q
```

### Testes de persistência/migração

```bash
poetry run pytest -q tests/test_persistence.py
```

---

## PostgreSQL local com Docker (exemplo)

Suba um container PostgreSQL local:

```bash
docker run --name gtd-postgres \
  -e POSTGRES_USER=gtd \
  -e POSTGRES_PASSWORD=gtd \
  -e POSTGRES_DB=gtd_pedagogico \
  -p 5432:5432 \
  -d postgres:16
```

Configure as variáveis:

```bash
export APP_ENV=production
export DATABASE_URL='postgresql://gtd:gtd@localhost:5432/gtd_pedagogico'
export POSTGRES_STAGING_DATABASE_URL="$DATABASE_URL"
export CERTIFICATE_KEY_ACTIVE_VERSION='v1'
export CERTIFICATE_KEY_v1='chave-local-apenas-desenvolvimento'
```

---

## Executar staging técnico com PostgreSQL real

### 1) Aplicar migrações (idempotência)

```bash
poetry run python - <<'PY'
import os
from gtd_backend.persistence import createDatabaseConnection, applyMigrations

url = os.environ['POSTGRES_STAGING_DATABASE_URL']
conn = createDatabaseConnection(databaseUrl=url, environmentName='production')
applyMigrations(connection=conn, databaseUrl=url)
applyMigrations(connection=conn, databaseUrl=url)
print('OK: migrações aplicadas com idempotência')
PY
```

### 2) Executar teste de staging dedicado

```bash
poetry run pytest -q tests/test_postgresql_staging.py
```

### 3) Executar smoke script oficial

```bash
bash scripts/postgresql_staging_smoke.sh
```

### 4) Garantir não regressão em SQLite

```bash
poetry run pytest -q tests/test_persistence.py
poetry run pytest -q
```

---

## Scripts e testes importantes

- `scripts/postgresql_staging_smoke.sh`
  - valida o caminho técnico PostgreSQL real com `tests/test_postgresql_staging.py`.
- `tests/test_persistence.py`
  - cobre bootstrap de conexão, migrações, idempotência e cenários de falha.
- `tests/test_postgresql_staging.py`
  - smoke de fluxo real com autenticação, RBAC, RF-02..RF-10 no banco PostgreSQL.

---

## Fluxos principais suportados hoje

- Autenticação e sessão (login/logout, proteção anti-enumeração)
- RF-01: disciplinas e professores com ownership por usuário
- RF-02/RF-06: caixa de entrada e categorização de ações
- RF-03/RF-08: plano de leitura, avanço e dashboard
- RF-04/RF-05: upload de certificado + progresso de ACC
- RF-07: recuperação de senha (fluxo técnico)
- RF-09: registro de eventos de segurança
- RF-10: monitoramento de cota de armazenamento

---

## Limitações conhecidas (estado atual)

- Sessão distribuída/multi-instância ainda requer validação operacional avançada para produção de alta escala.
- Integração real com provedor de e-mail transacional ainda é evolução futura.
- Upload atual está em JSON (`contentBase64`), com migração para `multipart/form-data` planejada.

---

## Continuidade da equipe/Codex

Antes de qualquer alteração, leia nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `PLAN.md`
4. `STATE.md`

Arquivos de referência para continuidade:
- `src/gtd_backend/persistence.py` (bootstrap e migrações)
- `src/gtd_backend/http.py` (composição da aplicação)
- `tests/test_persistence.py` e `tests/test_postgresql_staging.py`

---

## Validação rápida (checklist)

```bash
poetry run pytest -q tests/test_persistence.py
poetry run pytest -q tests/test_postgresql_staging.py
bash scripts/postgresql_staging_smoke.sh
poetry run pytest -q
```

---

## Troubleshooting

### 1) Suíte padrão contaminada por variáveis de produção

**Sintoma:** testes locais (SQLite) quebram após exportar variáveis de PostgreSQL.

**Ação:** limpe variáveis e rode novamente.

```bash
unset APP_ENV
unset DATABASE_URL
unset POSTGRES_STAGING_DATABASE_URL
```

### 2) `psycopg` ausente

**Sintoma:** erro de driver PostgreSQL indisponível.

**Ação:** reinstale dependências do projeto com Poetry.

```bash
poetry install
```

### 3) PostgreSQL não acessível

**Sintoma:** timeout/conexão recusada.

**Ações:**
- verificar host/porta/credenciais no `POSTGRES_STAGING_DATABASE_URL`;
- validar se container/serviço está ativo;
- testar conexão com cliente SQL externo.

### 4) Problema de import/contexto no pytest

**Sintoma:** falhas de import de módulos `gtd_backend`.

**Ação:** executar sempre via Poetry a partir da raiz do repositório.

```bash
poetry run pytest -q
```

### 5) Staging PostgreSQL falhando com tabela ausente

**Sintoma típico:** `relation "users" does not exist`.

**Checklist técnico:**
1. confirmar `POSTGRES_STAGING_DATABASE_URL` e `DATABASE_URL` apontando para o mesmo banco alvo de staging;
2. executar `applyMigrations` duas vezes (idempotência);
3. validar presença de `users` e `schema_migrations` no mesmo banco/schema;
4. executar novamente `tests/test_postgresql_staging.py`.

---

## Referências

- Guia técnico complementar: `docs/staging-postgresql.md`
- Estado atual do trabalho: `STATE.md`
