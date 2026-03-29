from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from gtd_backend.auth import DuplicateEmailError
from gtd_backend.http import createApp
from gtd_backend.persistence import (
    PostgresqlConnectionCompat,
    PersistenceConfigurationError,
    applyMigrations,
    createDatabaseConnection,
    hasTableColumn,
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


def test_postgresql_connection_compat_deve_adaptar_paramstyle_qmark_para_percent_s() -> None:
    class FakeCursor:
        def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
            self._rows = rows or []
            self.rowcount = 1

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def fetchall(self):
            return self._rows

    class FakeRawConnection:
        def __init__(self) -> None:
            self.executed: list[tuple[str, tuple]] = []

        def execute(self, query: str, params: tuple = ()):
            self.executed.append((query, params))
            if query.startswith("SELECT currval"):
                return FakeCursor([{"id": 7}])
            return FakeCursor()

        def commit(self) -> None:
            pass

    raw = FakeRawConnection()
    connection = PostgresqlConnectionCompat(rawConnection=raw)

    cursor = connection.execute("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)", ("a", "b", "c"))

    assert raw.executed[0] == (
        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
        ("a", "b", "c"),
    )
    assert "pg_get_serial_sequence('users', 'id')" in raw.executed[1][0]
    assert cursor.lastrowid == 7


def test_has_table_column_deve_consultar_information_schema_em_postgresql() -> None:
    class FakeCursor:
        def __init__(self, rows: list[dict[str, str]]) -> None:
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakePostgresConnection:
        __gtd_dialect__ = "postgresql"

        def __init__(self) -> None:
            self.query: str | None = None
            self.params: tuple | None = None

        def execute(self, query: str, params: tuple | None = None):
            self.query = query
            self.params = params
            return FakeCursor([{"column_name": "role"}])

        def commit(self) -> None:
            pass

    connection = FakePostgresConnection()

    assert hasTableColumn(connection=connection, tableName="users", columnName="role") is True
    assert "information_schema.columns" in str(connection.query)
    assert connection.params == ("users",)


def test_apply_migrations_deve_inferir_dialeto_postgresql_pela_conexao_quando_database_url_ausente() -> None:
    class FakeCursor:
        def __init__(self, rows: list[dict[str, str]] | None = None) -> None:
            self._rows = rows or []

        def fetchall(self):
            return self._rows

    class FakePostgresConnection:
        __gtd_dialect__ = "postgresql"

        def __init__(self) -> None:
            self.executed: list[tuple[str, tuple]] = []
            self.commits = 0

        def execute(self, query: str, params: tuple | None = None):
            self.executed.append((query.strip(), params or ()))
            if "SELECT version FROM schema_migrations" in query:
                return FakeCursor([])
            return FakeCursor()

        def commit(self) -> None:
            self.commits += 1

    connection = FakePostgresConnection()

    applyMigrations(connection=connection)

    assert any(
        "VALUES (%s, NOW()::TEXT)" in query
        for query, _ in connection.executed
    )


def test_apply_migrations_postgresql_deve_executar_script_em_statements_individuais(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migrationsDir = tmp_path / "postgresql"
    migrationsDir.mkdir(parents=True, exist_ok=True)
    (migrationsDir / "0001_baseline.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS auth_sessions (token_hash TEXT PRIMARY KEY);
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "gtd_backend.persistence._resolveMigrationsDir",
        lambda dialect: migrationsDir,
    )

    class FakeCursor:
        def __init__(self, rows: list[dict[str, str]] | None = None) -> None:
            self._rows = rows or []

        def fetchall(self):
            return self._rows

    class FakeSingleStatementPostgresConnection:
        __gtd_dialect__ = "postgresql"

        def __init__(self) -> None:
            self.executed: list[str] = []

        def execute(self, query: str, params: tuple | None = None):
            normalized = " ".join(query.split())
            if normalized.count(";") > 1:
                raise AssertionError("migração deve executar statements individualmente")
            self.executed.append(normalized)
            if "SELECT version FROM schema_migrations" in normalized:
                return FakeCursor([])
            return FakeCursor()

        def commit(self) -> None:
            pass

    connection = FakeSingleStatementPostgresConnection()

    applyMigrations(connection=connection)

    assert any(
        query.startswith("CREATE TABLE IF NOT EXISTS users")
        for query in connection.executed
    )
    assert any(
        query.startswith("CREATE TABLE IF NOT EXISTS auth_sessions")
        for query in connection.executed
    )
