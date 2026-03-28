import sqlite3
from collections.abc import Sequence
from gtd_backend.persistence import applyMigrations


class RF01Service:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        ownsConnection = connection is None
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        if ownsConnection:
            applyMigrations(connection=self.connection)

    def _normalizeText(self, value: str) -> str:
        return " ".join(value.strip().split())

    def _validateUserId(self, userId: int | None) -> None:
        if userId is not None and userId <= 0:
            raise ValueError("usuário inválido")

    def createProfessor(self, name: str, email: str, userId: int | None = None) -> int:
        normalizedName = self._normalizeText(name)
        normalizedEmail = email.strip().lower()
        self._validateUserId(userId)

        if not normalizedName:
            raise ValueError("nome do professor é obrigatório")
        if "@" not in normalizedEmail:
            raise ValueError("email do professor inválido")

        if userId is None:
            existingRow = self.connection.execute(
                """
                SELECT id
                FROM professors
                WHERE user_id IS NULL AND (normalized_name = ? OR email = ?)
                """,
                (normalizedName.lower(), normalizedEmail),
            ).fetchone()
        else:
            existingRow = self.connection.execute(
                """
                SELECT id
                FROM professors
                WHERE user_id = ? AND (normalized_name = ? OR email = ?)
                """,
                (userId, normalizedName.lower(), normalizedEmail),
            ).fetchone()
        if existingRow is not None:
            raise ValueError("professor já cadastrado")

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO professors (user_id, name, normalized_name, email)
                VALUES (?, ?, ?, ?)
                """,
                (userId, normalizedName, normalizedName.lower(), normalizedEmail),
            )
            self.connection.commit()
            return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("professor já cadastrado") from error

    def createDiscipline(
        self,
        name: str,
        code: str,
        professorIds: Sequence[int] | None = None,
        userId: int | None = None,
    ) -> int:
        normalizedName = self._normalizeText(name)
        normalizedCode = code.strip().upper()
        self._validateUserId(userId)

        if not normalizedName:
            raise ValueError("nome da disciplina é obrigatório")
        if not normalizedCode:
            raise ValueError("código da disciplina é obrigatório")

        if userId is None:
            existingRow = self.connection.execute(
                """
                SELECT id
                FROM disciplines
                WHERE user_id IS NULL AND normalized_name = ? AND normalized_code = ?
                """,
                (normalizedName.lower(), normalizedCode),
            ).fetchone()
        else:
            existingRow = self.connection.execute(
                """
                SELECT id
                FROM disciplines
                WHERE user_id = ? AND normalized_name = ? AND normalized_code = ?
                """,
                (userId, normalizedName.lower(), normalizedCode),
            ).fetchone()
        if existingRow is not None:
            raise ValueError("disciplina já cadastrada")

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO disciplines (user_id, name, normalized_name, code, normalized_code)
                VALUES (?, ?, ?, ?, ?)
                """,
                (userId, normalizedName, normalizedName.lower(), normalizedCode, normalizedCode),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("disciplina já cadastrada") from error

        disciplineId = int(cursor.lastrowid)

        if professorIds:
            self._bindProfessorsToDiscipline(
                disciplineId=disciplineId,
                professorIds=professorIds,
                userId=userId,
            )

        self.connection.commit()
        return disciplineId

    def _bindProfessorsToDiscipline(
        self,
        disciplineId: int,
        professorIds: Sequence[int],
        userId: int | None = None,
    ) -> None:
        uniqueProfessorIds = sorted(set(professorIds))

        if userId is None:
            rows = self.connection.execute(
                "SELECT id FROM professors WHERE user_id IS NULL AND id IN ({})".format(
                    ",".join(["?"] * len(uniqueProfessorIds))
                ),
                tuple(uniqueProfessorIds),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id FROM professors WHERE user_id = ? AND id IN ({})".format(
                    ",".join(["?"] * len(uniqueProfessorIds))
                ),
                (userId, *uniqueProfessorIds),
            ).fetchall()

        foundProfessorIds = {int(row["id"]) for row in rows}
        if foundProfessorIds != set(uniqueProfessorIds):
            raise ValueError("professor informado não existe")

        for professorId in uniqueProfessorIds:
            self.connection.execute(
                """
                INSERT INTO discipline_professor (discipline_id, professor_id)
                VALUES (?, ?)
                """,
                (disciplineId, professorId),
            )

    def listProfessors(self, userId: int | None = None) -> list[dict[str, int | str]]:
        self._validateUserId(userId)
        if userId is None:
            rows = self.connection.execute(
                "SELECT id, name, email FROM professors WHERE user_id IS NULL ORDER BY id ASC"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id, name, email FROM professors WHERE user_id = ? ORDER BY id ASC",
                (userId,),
            ).fetchall()

        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "email": str(row["email"]),
            }
            for row in rows
        ]

    def listDisciplines(self, userId: int | None = None) -> list[dict[str, int | str | list[int]]]:
        self._validateUserId(userId)
        if userId is None:
            rows = self.connection.execute(
                "SELECT id, name, code FROM disciplines WHERE user_id IS NULL ORDER BY id ASC"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id, name, code FROM disciplines WHERE user_id = ? ORDER BY id ASC",
                (userId,),
            ).fetchall()

        disciplines: list[dict[str, int | str | list[int]]] = []
        for row in rows:
            disciplineId = int(row["id"])
            professorRows = self.connection.execute(
                """
                SELECT professor_id
                FROM discipline_professor
                WHERE discipline_id = ?
                ORDER BY professor_id ASC
                """,
                (disciplineId,),
            ).fetchall()
            disciplines.append(
                {
                    "id": disciplineId,
                    "name": str(row["name"]),
                    "code": str(row["code"]),
                    "professorIds": [int(professorRow["professor_id"]) for professorRow in professorRows],
                }
            )

        return disciplines
