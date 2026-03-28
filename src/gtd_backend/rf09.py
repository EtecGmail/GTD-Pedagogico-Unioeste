import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from gtd_backend.persistence import applyMigrations


class SecurityEventService:
    def __init__(
        self,
        nowProvider: Callable[[], datetime] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        ownsConnection = connection is None
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        if ownsConnection:
            applyMigrations(connection=self.connection)
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))

    def recordEvent(
        self,
        eventType: str,
        result: str,
        userId: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        normalizedEventType = eventType.strip().lower()
        normalizedResult = result.strip().lower()
        if not normalizedEventType:
            raise ValueError("tipo de evento é obrigatório")
        if not normalizedResult:
            raise ValueError("resultado do evento é obrigatório")
        if userId is not None and userId <= 0:
            raise ValueError("usuário do evento é inválido")

        safeMetadata = self._sanitizeMetadata(metadata or {})
        timestamp = self.nowProvider().isoformat()
        cursor = self.connection.execute(
            """
            INSERT INTO security_events (event_type, timestamp, result, user_id, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (normalizedEventType, timestamp, normalizedResult, userId, json.dumps(safeMetadata, sort_keys=True)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def listEvents(self, limit: int = 100) -> list[dict[str, Any]]:
        boundedLimit = max(1, min(limit, 500))
        rows = self.connection.execute(
            """
            SELECT id, event_type, timestamp, result, user_id, metadata
            FROM security_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (boundedLimit,),
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "eventType": str(row["event_type"]),
                "timestamp": str(row["timestamp"]),
                "result": str(row["result"]),
                "userId": int(row["user_id"]) if row["user_id"] is not None else None,
                "metadata": json.loads(str(row["metadata"])),
            }
            for row in rows
        ]

    def _sanitizeMetadata(self, metadata: dict[str, Any]) -> dict[str, str | int | bool | None]:
        forbiddenKeys = {
            "password",
            "newpassword",
            "token",
            "resettoken",
            "authorization",
            "contentbase64",
            "email",
            "rawemail",
        }
        sanitized: dict[str, str | int | bool | None] = {}
        for rawKey, rawValue in metadata.items():
            normalizedKey = str(rawKey).strip()
            if not normalizedKey:
                continue

            comparableKey = normalizedKey.replace("_", "").replace("-", "").lower()
            if comparableKey in forbiddenKeys:
                continue

            if isinstance(rawValue, bool) or rawValue is None:
                sanitized[normalizedKey] = rawValue
            elif isinstance(rawValue, int):
                sanitized[normalizedKey] = rawValue
            else:
                sanitized[normalizedKey] = str(rawValue)[:200]

        return sanitized
