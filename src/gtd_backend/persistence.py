import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlparse


DEFAULT_DATABASE_URL = "sqlite:///:memory:"
SUPPORTED_DATABASE_SCHEMES = {"sqlite", "postgres", "postgresql"}
MIGRATIONS_TABLE_NAME = "schema_migrations"


class PersistenceConfigurationError(ValueError):
    """Erro de configuração de persistência sem vazamento de segredos."""


class DbCursorProtocol(Protocol):
    def fetchall(self) -> list[object]:
        ...


class DbConnectionProtocol(Protocol):
    def execute(self, query: str, params: tuple | None = None) -> DbCursorProtocol | None:
        ...

    def commit(self) -> None:
        ...


@dataclass(frozen=True)
class DatabaseSettings:
    databaseUrl: str
    environmentName: str
    dialect: str


def resolveDatabaseUrl(databaseUrl: str | None = None, environmentName: str | None = None) -> str:
    normalizedEnvironment = (environmentName or os.environ.get("APP_ENV", "development")).strip().lower()
    resolvedUrl = (databaseUrl or os.environ.get("DATABASE_URL", "")).strip()

    if resolvedUrl:
        return resolvedUrl

    if normalizedEnvironment in {"prod", "production"}:
        raise PersistenceConfigurationError("DATABASE_URL é obrigatório em produção")

    return DEFAULT_DATABASE_URL


def _redactDatabaseUrl(databaseUrl: str) -> str:
    parsedUrl = urlparse(databaseUrl)
    if parsedUrl.scheme in {"postgres", "postgresql"}:
        host = parsedUrl.hostname or "host-indefinido"
        port = f":{parsedUrl.port}" if parsedUrl.port else ""
        database = parsedUrl.path.lstrip("/") or "db-indefinido"
        return f"{parsedUrl.scheme}://***@{host}{port}/{database}"

    if parsedUrl.scheme == "sqlite":
        if parsedUrl.path in {":memory:", "/:memory:"}:
            return "sqlite:///:memory:"
        return "sqlite:///***"

    return "database://***"


def getDatabaseSettings(
    databaseUrl: str | None = None,
    environmentName: str | None = None,
) -> DatabaseSettings:
    normalizedEnvironment = (environmentName or os.environ.get("APP_ENV", "development")).strip().lower()
    resolvedDatabaseUrl = resolveDatabaseUrl(databaseUrl=databaseUrl, environmentName=normalizedEnvironment)
    parsedUrl = urlparse(resolvedDatabaseUrl)
    scheme = parsedUrl.scheme.strip().lower()

    if scheme not in SUPPORTED_DATABASE_SCHEMES:
        raise PersistenceConfigurationError("esquema de banco não suportado")

    dialect = "postgresql" if scheme in {"postgres", "postgresql"} else "sqlite"

    return DatabaseSettings(
        databaseUrl=resolvedDatabaseUrl,
        environmentName=normalizedEnvironment,
        dialect=dialect,
    )


def createSqliteConnection(databaseUrl: str = DEFAULT_DATABASE_URL) -> sqlite3.Connection:
    parsedUrl = urlparse(databaseUrl)
    if parsedUrl.scheme != "sqlite":
        raise PersistenceConfigurationError("apenas sqlite é suportado neste conector")

    databasePath = parsedUrl.path or ":memory:"
    if databasePath in {"/:memory:", ":memory:"}:
        sqlitePath = ":memory:"
    else:
        if databaseUrl.startswith("sqlite:///./"):
            sqlitePath = databasePath[1:]
        else:
            sqlitePath = databasePath
        parentDir = os.path.dirname(sqlitePath)
        if parentDir:
            os.makedirs(parentDir, exist_ok=True)

    connection = sqlite3.connect(sqlitePath, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.commit()
    return connection


def _createPostgresqlConnection(databaseUrl: str) -> DbConnectionProtocol:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as error:
        raise PersistenceConfigurationError(
            "driver PostgreSQL indisponível; instale dependência de produção"
        ) from error

    connection = psycopg.connect(databaseUrl, row_factory=dict_row)
    connection.autocommit = False
    return connection


def createDatabaseConnection(
    databaseUrl: str | None = None,
    environmentName: str | None = None,
    postgresqlConnector: Callable[[str], DbConnectionProtocol] | None = None,
) -> DbConnectionProtocol:
    settings = getDatabaseSettings(databaseUrl=databaseUrl, environmentName=environmentName)

    if settings.dialect == "sqlite":
        return createSqliteConnection(databaseUrl=settings.databaseUrl)

    connector = postgresqlConnector or _createPostgresqlConnection
    try:
        return connector(settings.databaseUrl)
    except PersistenceConfigurationError:
        raise
    except Exception as error:
        sanitizedUrl = _redactDatabaseUrl(settings.databaseUrl)
        raise PersistenceConfigurationError(
            f"falha ao conectar no banco configurado ({sanitizedUrl})"
        ) from error


def _resolveMigrationsDir(dialect: str) -> Path:
    migrationsBaseDir = Path(__file__).resolve().parent / "db" / "migrations" / dialect
    if not migrationsBaseDir.exists():
        raise PersistenceConfigurationError("diretório de migrações não encontrado")
    return migrationsBaseDir


def _ensureMigrationsTable(connection: DbConnectionProtocol) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE_NAME} (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _listAppliedMigrations(connection: DbConnectionProtocol) -> set[str]:
    cursor = connection.execute(
        f"SELECT version FROM {MIGRATIONS_TABLE_NAME}"
    )
    if cursor is None:
        return set()
    rows = cursor.fetchall()
    return {str(row[0] if not isinstance(row, dict) else row["version"]) for row in rows}


def applyMigrations(connection: DbConnectionProtocol, databaseUrl: str | None = None) -> None:
    settings = getDatabaseSettings(databaseUrl=databaseUrl)
    migrationsDir = _resolveMigrationsDir(dialect=settings.dialect)

    _ensureMigrationsTable(connection=connection)
    appliedVersions = _listAppliedMigrations(connection=connection)

    migrationFiles = sorted(migrationsDir.glob("*.sql"))
    for migrationFile in migrationFiles:
        version = migrationFile.stem
        if version in appliedVersions:
            continue

        sqlScript = migrationFile.read_text(encoding="utf-8")
        connection.executescript(sqlScript) if hasattr(connection, "executescript") else connection.execute(sqlScript)
        connection.execute(
            f"INSERT INTO {MIGRATIONS_TABLE_NAME} (version, applied_at) VALUES (?, datetime('now'))"
            if settings.dialect == "sqlite"
            else f"INSERT INTO {MIGRATIONS_TABLE_NAME} (version, applied_at) VALUES (%s, NOW()::TEXT)",
            (version,),
        )
        connection.commit()
