import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime


VALID_INBOX_STATUSES = {"inbox", "next_action", "waiting"}


class RF02Service:
    def __init__(self, nowProvider: Callable[[], datetime] | None = None) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inbox_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def _normalizeContent(self, content: str) -> str:
        return " ".join(content.strip().split())

    def captureInboxItem(self, content: str) -> int:
        normalizedContent = self._normalizeContent(content)
        if not normalizedContent:
            raise ValueError("conteúdo da captura é obrigatório")

        createdAt = self.nowProvider().isoformat()
        cursor = self.connection.execute(
            """
            INSERT INTO inbox_items (content, status, created_at)
            VALUES (?, ?, ?)
            """,
            (normalizedContent, "inbox", createdAt),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def _normalizeStatus(self, status: str) -> str:
        normalizedStatus = status.strip().lower()
        if normalizedStatus not in VALID_INBOX_STATUSES:
            raise ValueError("status inválido")
        return normalizedStatus

    def changeInboxItemStatus(self, itemId: int, targetStatus: str) -> dict[str, int | str]:
        normalizedTargetStatus = self._normalizeStatus(targetStatus)
        if normalizedTargetStatus == "inbox":
            raise ValueError("status de destino inválido")

        row = self.connection.execute(
            """
            SELECT id, status
            FROM inbox_items
            WHERE id = ?
            """,
            (itemId,),
        ).fetchone()

        if row is None:
            raise LookupError("item da caixa de entrada não encontrado")

        currentStatus = str(row["status"])
        if currentStatus != "inbox":
            raise ValueError("transição de status inválida")

        self.connection.execute(
            """
            UPDATE inbox_items
            SET status = ?
            WHERE id = ?
            """,
            (normalizedTargetStatus, itemId),
        )
        self.connection.commit()

        return {"id": itemId, "status": normalizedTargetStatus}

    def listInboxItems(self, status: str | None = None) -> list[dict[str, int | str]]:
        if status is None:
            rows = self.connection.execute(
                """
                SELECT id, content, status, created_at
                FROM inbox_items
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        else:
            normalizedStatus = self._normalizeStatus(status)
            rows = self.connection.execute(
                """
                SELECT id, content, status, created_at
                FROM inbox_items
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                """,
                (normalizedStatus,),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "content": str(row["content"]),
                "status": str(row["status"]),
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]
