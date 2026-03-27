import os
import sqlite3
from urllib.parse import urlparse


DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def createSqliteConnection(databaseUrl: str = DEFAULT_DATABASE_URL) -> sqlite3.Connection:
    parsedUrl = urlparse(databaseUrl)
    if parsedUrl.scheme != "sqlite":
        raise ValueError("apenas sqlite é suportado neste ambiente")

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
