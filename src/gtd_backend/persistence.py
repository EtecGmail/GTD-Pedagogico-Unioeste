import os
import sqlite3
import re
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlparse


DEFAULT_DATABASE_URL = "sqlite:///:memory:"
SUPPORTED_DATABASE_SCHEMES = {"sqlite", "postgres", "postgresql"}
MIGRATIONS_TABLE_NAME = "schema_migrations"
MIGRATION_MATERIALIZATION_GUARDS: dict[str, set[str]] = {
    "0001_baseline": {"users"},
}


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


def getConnectionDialect(connection: object) -> str:
    explicitDialect = getattr(connection, "__gtd_dialect__", None)
    if isinstance(explicitDialect, str) and explicitDialect in {"sqlite", "postgresql"}:
        return explicitDialect
    if isinstance(connection, sqlite3.Connection):
        return "sqlite"
    return "postgresql"


def hasTableColumn(connection: DbConnectionProtocol, tableName: str, columnName: str) -> bool:
    dialect = getConnectionDialect(connection)
    if dialect == "sqlite":
        rows = connection.execute(f"PRAGMA table_info({tableName})").fetchall()
        existingColumns = {str(row["name"]) for row in rows}
        return columnName in existingColumns

    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (tableName,),
    ).fetchall()
    existingColumns = {str(row["column_name"]) if isinstance(row, dict) else str(row[0]) for row in rows}
    return columnName in existingColumns


def _adaptQueryToDialect(query: str, dialect: str) -> str:
    if dialect != "postgresql":
        return query
    return query.replace("?", "%s")


class PostgresqlCursorCompat:
    def __init__(self, cursor: object, lastrowid: int | None = None) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return int(getattr(self._cursor, "rowcount", 0))

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[object]:
        return list(self._cursor.fetchall())


class PostgresqlConnectionCompat:
    __gtd_dialect__ = "postgresql"

    def __init__(self, rawConnection: object) -> None:
        self._rawConnection = rawConnection

    def commit(self) -> None:
        self._rawConnection.commit()

    def _resolveLastRowId(self, query: str) -> int | None:
        normalizedQuery = " ".join(query.strip().split()).lower()
        if not normalizedQuery.startswith("insert into "):
            return None
        tableMatch = re.match(r"insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalizedQuery)
        if tableMatch is None:
            return None
        tableName = tableMatch.group(1)
        try:
            idCursor = self._rawConnection.execute(
                f"SELECT currval(pg_get_serial_sequence('{tableName}', 'id')) AS id"
            )
            row = idCursor.fetchone()
            if row is None:
                return None
            if isinstance(row, dict):
                return int(row["id"])
            return int(row[0])
        except Exception:
            return None

    def execute(self, query: str, params: tuple | None = None) -> PostgresqlCursorCompat:
        adaptedQuery = _adaptQueryToDialect(query=query, dialect="postgresql")
        try:
            cursor = self._rawConnection.execute(adaptedQuery, params or ())
        except Exception as error:
            try:
                from psycopg import IntegrityError as PsycopgIntegrityError
            except Exception:
                PsycopgIntegrityError = None
            if PsycopgIntegrityError is not None and isinstance(error, PsycopgIntegrityError):
                raise sqlite3.IntegrityError("violação de integridade relacional") from error
            raise
        return PostgresqlCursorCompat(cursor=cursor, lastrowid=self._resolveLastRowId(query=query))


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
    return PostgresqlConnectionCompat(rawConnection=connection)


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


def _listMigrationFiles(migrationsDir: Path) -> list[Path]:
    migrationFiles = sorted(migrationsDir.glob("*.sql"))
    if not migrationFiles:
        raise PersistenceConfigurationError("nenhuma migração SQL encontrada para o dialeto configurado")
    return migrationFiles


def _tableExists(connection: DbConnectionProtocol, tableName: str, dialect: str) -> bool:
    if dialect == "sqlite":
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (tableName,),
        )
    else:
        cursor = connection.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = %s
            ) AS table_exists
            """,
            (tableName,),
        )
    if cursor is None:
        return False
    row = cursor.fetchall()
    if not row:
        return False
    firstRow = row[0]
    if isinstance(firstRow, dict):
        if "table_exists" in firstRow:
            return bool(firstRow["table_exists"])
        return bool(next(iter(firstRow.values()), False))
    return bool(firstRow[0])


def _isMigrationMaterialized(connection: DbConnectionProtocol, version: str, dialect: str) -> bool:
    guardedTables = MIGRATION_MATERIALIZATION_GUARDS.get(version, set())
    if not guardedTables:
        return True
    return all(
        _tableExists(connection=connection, tableName=tableName, dialect=dialect)
        for tableName in guardedTables
    )


def _splitSqlStatements(sqlScript: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    quoteChar: str | None = None
    previousChar = ""
    index = 0

    while index < len(sqlScript):
        currentChar = sqlScript[index]
        nextChar = sqlScript[index + 1] if index + 1 < len(sqlScript) else ""

        if quoteChar is None and currentChar == "-" and nextChar == "-":
            while index < len(sqlScript) and sqlScript[index] not in {"\n", "\r"}:
                index += 1
            continue

        if quoteChar is None and currentChar in {"'", '"'}:
            quoteChar = currentChar
            buffer.append(currentChar)
            previousChar = currentChar
            index += 1
            continue

        if quoteChar is not None and currentChar == quoteChar and previousChar != "\\":
            quoteChar = None
            buffer.append(currentChar)
            previousChar = currentChar
            index += 1
            continue

        if quoteChar is None and currentChar == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            previousChar = currentChar
            index += 1
            continue

        buffer.append(currentChar)
        previousChar = currentChar
        index += 1

    trailingStatement = "".join(buffer).strip()
    if trailingStatement:
        statements.append(trailingStatement)

    return statements


def applyMigrations(connection: DbConnectionProtocol, databaseUrl: str | None = None) -> None:
    if databaseUrl is None:
        dialect = getConnectionDialect(connection)
    else:
        settings = getDatabaseSettings(databaseUrl=databaseUrl)
        dialect = settings.dialect

    migrationsDir = _resolveMigrationsDir(dialect=dialect)

    _ensureMigrationsTable(connection=connection)
    appliedVersions = _listAppliedMigrations(connection=connection)

    migrationFiles = _listMigrationFiles(migrationsDir=migrationsDir)
    for migrationFile in migrationFiles:
        version = migrationFile.stem
        versionAlreadyApplied = version in appliedVersions
        if versionAlreadyApplied and _isMigrationMaterialized(connection=connection, version=version, dialect=dialect):
            continue

        sqlScript = migrationFile.read_text(encoding="utf-8")
        if hasattr(connection, "executescript"):
            connection.executescript(sqlScript)
        else:
            statements = _splitSqlStatements(sqlScript=sqlScript)
            for statement in statements:
                connection.execute(statement)
        if not _isMigrationMaterialized(connection=connection, version=version, dialect=dialect):
            raise PersistenceConfigurationError(
                f"migração {version} executada sem materializar tabelas obrigatórias"
            )
        if versionAlreadyApplied:
            connection.execute(
                f"UPDATE {MIGRATIONS_TABLE_NAME} SET applied_at = datetime('now') WHERE version = ?"
                if dialect == "sqlite"
                else f"UPDATE {MIGRATIONS_TABLE_NAME} SET applied_at = NOW()::TEXT WHERE version = %s",
                (version,),
            )
        else:
            connection.execute(
                f"INSERT INTO {MIGRATIONS_TABLE_NAME} (version, applied_at) VALUES (?, datetime('now'))"
                if dialect == "sqlite"
                else f"INSERT INTO {MIGRATIONS_TABLE_NAME} (version, applied_at) VALUES (%s, NOW()::TEXT)",
                (version,),
            )
            appliedVersions.add(version)
        connection.commit()
