# GTD-Pedagogico-Unioeste

Backend do projeto **GTD Pedagógico Unioeste**.

## Execução rápida (SQLite)

```bash
poetry install
poetry run pytest -q
```

## Validação de staging técnico (PostgreSQL real)

Consulte o guia operacional em:

- [`docs/staging-postgresql.md`](docs/staging-postgresql.md)

Resumo do fluxo:

1. configurar `APP_ENV=production` e `DATABASE_URL`;
2. aplicar migrações com idempotência;
3. executar smoke tests PostgreSQL (`scripts/postgresql_staging_smoke.sh`);
4. reexecutar suíte padrão em SQLite para garantir não regressão.
