import math
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime


class RF03Service:
    def __init__(self, nowProvider: Callable[[], datetime] | None = None) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reading_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_pages INTEGER NOT NULL,
                deadline_days INTEGER NOT NULL,
                daily_goal INTEGER NOT NULL,
                is_overloaded INTEGER NOT NULL,
                remaining_pages INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def createReadingPlan(self, totalPages: int, deadlineDays: int) -> int:
        if totalPages <= 0:
            raise ValueError("total de páginas deve ser maior que zero")
        if deadlineDays <= 0:
            raise ValueError("prazo em dias deve ser maior que zero")

        dailyGoal = math.ceil(totalPages / deadlineDays)
        isOverloaded = dailyGoal > 30
        createdAt = self.nowProvider().isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO reading_plans (
                total_pages,
                deadline_days,
                daily_goal,
                is_overloaded,
                remaining_pages,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (totalPages, deadlineDays, dailyGoal, int(isOverloaded), totalPages, createdAt),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def listReadingPlans(self) -> list[dict[str, int | bool | str]]:
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

    def advanceReadingPlan(self, planId: int, pagesRead: int) -> dict[str, int | bool]:
        if pagesRead <= 0:
            raise ValueError("páginas lidas deve ser maior que zero")

        row = self.connection.execute(
            """
            SELECT id, remaining_pages
            FROM reading_plans
            WHERE id = ?
            """,
            (planId,),
        ).fetchone()
        if row is None:
            raise LookupError("plano de leitura não encontrado")

        remainingPages = int(row["remaining_pages"])
        updatedRemainingPages = max(remainingPages - pagesRead, 0)

        self.connection.execute(
            """
            UPDATE reading_plans
            SET remaining_pages = ?
            WHERE id = ?
            """,
            (updatedRemainingPages, planId),
        )
        self.connection.commit()

        return {
            "id": int(planId),
            "remainingPages": updatedRemainingPages,
            "isCompleted": updatedRemainingPages == 0,
        }
