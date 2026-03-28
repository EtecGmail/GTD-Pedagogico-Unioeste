from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from gtd_backend.auth import DuplicateEmailError
from gtd_backend.http import createApp
from gtd_backend.persistence import (
    PersistenceConfigurationError,
    applyMigrations,
    createDatabaseConnection,
    resolveDatabaseUrl,
)


def _autenticarUsuario(client: TestClient, app, email: str) -> dict[str, str]:
    try:
        app.state.authService.register_user(email, "SenhaForte123")
    except (ValueError, DuplicateEmailError, sqlite3.IntegrityError):
        pass
    respostaLogin = client.post(
        "/auth/login",
        json={"email": email, "password": "SenhaForte123"},
    )
    token = respostaLogin.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_create_app_deve_persistir_dados_em_sqlite_compartilhado_entre_instancias(tmp_path: Path) -> None:
    databaseFile = tmp_path / "gtd-shared.db"
    databaseUrl = f"sqlite:///{databaseFile}"

    appPrimeiraInstancia = createApp(databaseUrl=databaseUrl)
    clientPrimeiraInstancia = TestClient(appPrimeiraInstancia)
    headersPrimeiraInstancia = _autenticarUsuario(
        client=clientPrimeiraInstancia,
        app=appPrimeiraInstancia,
        email="aluna@unioeste.br",
    )
    respostaCriacao = clientPrimeiraInstancia.post(
        "/rf01/professors",
        json={"name": "Professora Ana", "email": "ana@unioeste.br"},
        headers=headersPrimeiraInstancia,
    )
    assert respostaCriacao.status_code == 201

    appSegundaInstancia = createApp(databaseUrl=databaseUrl)
    clientSegundaInstancia = TestClient(appSegundaInstancia)
    headersSegundaInstancia = _autenticarUsuario(
        client=clientSegundaInstancia,
        app=appSegundaInstancia,
        email="aluna@unioeste.br",
    )
    respostaListagem = clientSegundaInstancia.get("/rf01/professors", headers=headersSegundaInstancia)

    assert respostaListagem.status_code == 200
    assert respostaListagem.json() == [
        {"id": 1, "name": "Professora Ana", "email": "ana@unioeste.br"}
    ]


def test_resolve_database_url_deve_usar_sqlite_em_desenvolvimento_quando_ausente() -> None:
    assert resolveDatabaseUrl(databaseUrl=None, environmentName="development") == "sqlite:///:memory:"


def test_resolve_database_url_deve_exigir_url_em_producao() -> None:
    with pytest.raises(PersistenceConfigurationError, match="DATABASE_URL"):
        resolveDatabaseUrl(databaseUrl=None, environmentName="production")


def test_create_database_connection_deve_validar_postgresql_sem_expor_segredo() -> None:
    databaseUrl = "postgresql://usuario:segredo-super-secreto@db.exemplo.local:5432/gtd"

    with pytest.raises(PersistenceConfigurationError) as error:
        createDatabaseConnection(databaseUrl=databaseUrl, environmentName="production")

    assert "segredo-super-secreto" not in str(error.value)


def test_create_database_connection_deve_ser_compativel_com_bootstrap_postgresql() -> None:
    captured: dict[str, str] = {}

    class DummyConnection:
        def __init__(self) -> None:
            self.commits = 0

        def commit(self) -> None:
            self.commits += 1

        def execute(self, query: str, params: tuple | None = None):
            return None

    def fakeConnector(databaseUrl: str):
        captured["url"] = databaseUrl
        return DummyConnection()

    connection = createDatabaseConnection(
        databaseUrl="postgresql://usuario:segredo@localhost:5432/gtd",
        environmentName="production",
        postgresqlConnector=fakeConnector,
    )

    assert captured["url"] == "postgresql://usuario:segredo@localhost:5432/gtd"
    assert connection.__class__.__name__ == "DummyConnection"


def test_apply_migrations_deve_criar_tabela_de_versao_e_ser_idempotente(tmp_path: Path) -> None:
    databaseFile = tmp_path / "gtd-migrations.db"
    databaseUrl = f"sqlite:///{databaseFile}"
    connection = createDatabaseConnection(databaseUrl=databaseUrl)

    applyMigrations(connection=connection, databaseUrl=databaseUrl)
    applyMigrations(connection=connection, databaseUrl=databaseUrl)

    migrationRows = connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version ASC"
    ).fetchall()
    versions = [str(row[0]) for row in migrationRows]
    assert versions == ["0001_baseline"]


def test_apply_migrations_deve_criar_tabelas_principais_necessarias(tmp_path: Path) -> None:
    databaseFile = tmp_path / "gtd-migrations-main.db"
    databaseUrl = f"sqlite:///{databaseFile}"
    connection = createDatabaseConnection(databaseUrl=databaseUrl)

    applyMigrations(connection=connection, databaseUrl=databaseUrl)

    expectedTables = {
        "users",
        "auth_sessions",
        "professors",
        "disciplines",
        "discipline_professor",
        "inbox_items",
        "reading_plans",
        "acc_certificates",
        "password_reset_tokens",
        "security_events",
    }
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    createdTables = {str(row[0]) for row in rows}
    assert expectedTables.issubset(createdTables)
