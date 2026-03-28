import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from gtd_backend.persistence import hasTableColumn


VALID_INBOX_STATUSES = {"inbox", "next_action", "waiting"}


class RF02Service:
    def __init__(
        self,
        nowProvider: Callable[[], datetime] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inbox_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        if not hasTableColumn(connection=self.connection, tableName="inbox_items", columnName="user_id"):
            self.connection.execute("ALTER TABLE inbox_items ADD COLUMN user_id INTEGER")
        self.connection.commit()

    def _normalizeContent(self, content: str) -> str:
        return " ".join(content.strip().split())

    def captureInboxItem(self, content: str, userId: int | None = None) -> int:
        normalizedContent = self._normalizeContent(content)
        if not normalizedContent:
            raise ValueError("conteúdo da captura é obrigatório")
        if userId is not None and userId <= 0:
            raise ValueError("usuário da captura é inválido")

        createdAt = self.nowProvider().isoformat()
        cursor = self.connection.execute(
            """
            INSERT INTO inbox_items (user_id, content, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (userId, normalizedContent, "inbox", createdAt),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def _normalizeStatus(self, status: str) -> str:
        normalizedStatus = status.strip().lower()
        if normalizedStatus not in VALID_INBOX_STATUSES:
            raise ValueError("status inválido")
        return normalizedStatus

    def changeInboxItemStatus(
        self,
        itemId: int,
        targetStatus: str,
        userId: int | None = None,
    ) -> dict[str, int | str]:
        normalizedTargetStatus = self._normalizeStatus(targetStatus)
        if normalizedTargetStatus == "inbox":
            raise ValueError("status de destino inválido")
        if userId is not None and userId <= 0:
            raise ValueError("usuário da atualização é inválido")

        if userId is None:
            row = self.connection.execute(
                """
                SELECT id, status
                FROM inbox_items
                WHERE id = ?
                """,
                (itemId,),
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT id, status
                FROM inbox_items
                WHERE id = ? AND user_id = ?
                """,
                (itemId, userId),
            ).fetchone()

        if row is None:
            raise LookupError("item da caixa de entrada não encontrado")

        currentStatus = str(row["status"])
        if currentStatus != "inbox":
            raise ValueError("transição de status inválida")

        if userId is None:
            self.connection.execute(
                """
                UPDATE inbox_items
                SET status = ?
                WHERE id = ?
                """,
                (normalizedTargetStatus, itemId),
            )
        else:
            self.connection.execute(
                """
                UPDATE inbox_items
                SET status = ?
                WHERE id = ? AND user_id = ?
                """,
                (normalizedTargetStatus, itemId, userId),
            )
        self.connection.commit()

        return {"id": itemId, "status": normalizedTargetStatus}

    def listInboxItems(
        self,
        status: str | None = None,
        userId: int | None = None,
    ) -> list[dict[str, int | str | None]]:
        if userId is not None and userId <= 0:
            raise ValueError("usuário da listagem é inválido")

        if status is None and userId is None:
            rows = self.connection.execute(
                """
                SELECT id, user_id, content, status, created_at
                FROM inbox_items
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        elif status is not None and userId is None:
            normalizedStatus = self._normalizeStatus(status)
            rows = self.connection.execute(
                """
                SELECT id, user_id, content, status, created_at
                FROM inbox_items
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                """,
                (normalizedStatus,),
            ).fetchall()
        elif status is None and userId is not None:
            rows = self.connection.execute(
                """
                SELECT id, user_id, content, status, created_at
                FROM inbox_items
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (userId,),
            ).fetchall()
        else:
            normalizedStatus = self._normalizeStatus(status or "")
            rows = self.connection.execute(
                """
                SELECT id, user_id, content, status, created_at
                FROM inbox_items
                WHERE status = ? AND user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (normalizedStatus, userId),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "userId": int(row["user_id"]) if row["user_id"] is not None else None,
                "content": str(row["content"]),
                "status": str(row["status"]),
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]
