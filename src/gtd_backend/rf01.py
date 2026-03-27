import sqlite3
from collections.abc import Sequence


class RF01Service:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS professors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS disciplines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                code TEXT NOT NULL,
                normalized_code TEXT NOT NULL,
                UNIQUE(normalized_name, normalized_code)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS discipline_professor (
                discipline_id INTEGER NOT NULL,
                professor_id INTEGER NOT NULL,
                PRIMARY KEY (discipline_id, professor_id),
                FOREIGN KEY (discipline_id) REFERENCES disciplines(id),
                FOREIGN KEY (professor_id) REFERENCES professors(id)
            )
            """
        )
        self.connection.commit()

    def _normalizeText(self, value: str) -> str:
        return " ".join(value.strip().split())

    def createProfessor(self, name: str, email: str) -> int:
        normalizedName = self._normalizeText(name)
        normalizedEmail = email.strip().lower()

        if not normalizedName:
            raise ValueError("nome do professor é obrigatório")
        if "@" not in normalizedEmail:
            raise ValueError("email do professor inválido")

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO professors (name, normalized_name, email)
                VALUES (?, ?, ?)
                """,
                (normalizedName, normalizedName.lower(), normalizedEmail),
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
    ) -> int:
        normalizedName = self._normalizeText(name)
        normalizedCode = code.strip().upper()

        if not normalizedName:
            raise ValueError("nome da disciplina é obrigatório")
        if not normalizedCode:
            raise ValueError("código da disciplina é obrigatório")

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO disciplines (name, normalized_name, code, normalized_code)
                VALUES (?, ?, ?, ?)
                """,
                (normalizedName, normalizedName.lower(), normalizedCode, normalizedCode),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("disciplina já cadastrada") from error

        disciplineId = int(cursor.lastrowid)

        if professorIds:
            self._bindProfessorsToDiscipline(disciplineId=disciplineId, professorIds=professorIds)

        self.connection.commit()
        return disciplineId

    def _bindProfessorsToDiscipline(self, disciplineId: int, professorIds: Sequence[int]) -> None:
        uniqueProfessorIds = sorted(set(professorIds))

        rows = self.connection.execute(
            "SELECT id FROM professors WHERE id IN ({})".format(
                ",".join(["?"] * len(uniqueProfessorIds))
            ),
            tuple(uniqueProfessorIds),
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

    def listProfessors(self) -> list[dict[str, int | str]]:
        rows = self.connection.execute(
            "SELECT id, name, email FROM professors ORDER BY id ASC"
        ).fetchall()

        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "email": str(row["email"]),
            }
            for row in rows
        ]

    def listDisciplines(self) -> list[dict[str, int | str | list[int]]]:
        rows = self.connection.execute(
            "SELECT id, name, code FROM disciplines ORDER BY id ASC"
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
