import math
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime


class RF03Service:
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
            CREATE TABLE IF NOT EXISTS reading_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total_pages INTEGER NOT NULL,
                deadline_days INTEGER NOT NULL,
                daily_goal INTEGER NOT NULL,
                is_overloaded INTEGER NOT NULL,
                remaining_pages INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = self.connection.execute("PRAGMA table_info(reading_plans)").fetchall()
        existingColumns = {str(column["name"]) for column in columns}
        if "user_id" not in existingColumns:
            self.connection.execute("ALTER TABLE reading_plans ADD COLUMN user_id INTEGER")
        self.connection.commit()

    def createReadingPlan(self, totalPages: int, deadlineDays: int, userId: int | None = None) -> int:
        if totalPages <= 0:
            raise ValueError("total de páginas deve ser maior que zero")
        if deadlineDays <= 0:
            raise ValueError("prazo em dias deve ser maior que zero")
        if userId is not None and userId <= 0:
            raise ValueError("usuário do plano de leitura é inválido")

        dailyGoal = math.ceil(totalPages / deadlineDays)
        isOverloaded = dailyGoal > 30
        createdAt = self.nowProvider().isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO reading_plans (
                user_id,
                total_pages,
                deadline_days,
                daily_goal,
                is_overloaded,
                remaining_pages,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (userId, totalPages, deadlineDays, dailyGoal, int(isOverloaded), totalPages, createdAt),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def listReadingPlans(self, userId: int | None = None) -> list[dict[str, int | bool | str]]:
        if userId is None:
            rows = self.connection.execute(
                """
                SELECT
                    id,
                    total_pages,
                    deadline_days,
                    daily_goal,
                    is_overloaded,
                    remaining_pages,
                    created_at
                FROM reading_plans
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        else:
            if userId <= 0:
                raise ValueError("usuário do plano de leitura é inválido")
            rows = self.connection.execute(
                """
                SELECT
                    id,
                    total_pages,
                    deadline_days,
                    daily_goal,
                    is_overloaded,
                    remaining_pages,
                    created_at
                FROM reading_plans
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (userId,),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "totalPages": int(row["total_pages"]),
                "deadlineDays": int(row["deadline_days"]),
                "dailyGoal": int(row["daily_goal"]),
                "isOverloaded": bool(row["is_overloaded"]),
                "remainingPages": int(row["remaining_pages"]),
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]

    def advanceReadingPlan(
        self,
        planId: int,
        pagesRead: int,
        userId: int | None = None,
    ) -> dict[str, int | bool]:
        if pagesRead <= 0:
            raise ValueError("páginas lidas deve ser maior que zero")
        if userId is not None and userId <= 0:
            raise ValueError("usuário do plano de leitura é inválido")

        if userId is None:
            row = self.connection.execute(
                """
                SELECT id, remaining_pages
                FROM reading_plans
                WHERE id = ?
                """,
                (planId,),
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT id, remaining_pages
                FROM reading_plans
                WHERE id = ? AND user_id = ?
                """,
                (planId, userId),
            ).fetchone()
        if row is None:
            raise LookupError("plano de leitura não encontrado")

        remainingPages = int(row["remaining_pages"])
        updatedRemainingPages = max(remainingPages - pagesRead, 0)

        if userId is None:
            self.connection.execute(
                """
                UPDATE reading_plans
                SET remaining_pages = ?
                WHERE id = ?
                """,
                (updatedRemainingPages, planId),
            )
        else:
            self.connection.execute(
                """
                UPDATE reading_plans
                SET remaining_pages = ?
                WHERE id = ? AND user_id = ?
                """,
                (updatedRemainingPages, planId, userId),
            )
        self.connection.commit()

        return {
            "id": int(planId),
            "remainingPages": updatedRemainingPages,
            "isCompleted": updatedRemainingPages == 0,
        }
