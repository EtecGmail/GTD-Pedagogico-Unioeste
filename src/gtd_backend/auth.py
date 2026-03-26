from dataclasses import dataclass
import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

CREDENCIAIS_INVALIDAS = "credenciais inválidas"


@dataclass(frozen=True)
class AuthResult:
    success: bool
    message: str


class AuthService:
    """Serviço de autenticação com login blindado e Argon2id."""

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.passwordHasher = PasswordHasher()
        self.dummyHash = self.passwordHasher.hash("senha-falsa-para-timing-attack")
        self._setup_schema()

    def _setup_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def _verifyPasswordHash(self, passwordHash: str, plainPassword: str) -> bool:
        try:
            verifyResult = self.passwordHasher.verify(passwordHash, plainPassword)
            return bool(verifyResult)
        except (VerifyMismatchError, VerificationError):
            return False

    def register_user(self, email: str, plain_password: str) -> int:
        passwordHash = self.passwordHasher.hash(plain_password)
        cursor = self.connection.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email.lower().strip(), passwordHash),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def login(self, email: str, plain_password: str) -> AuthResult:
        normalizedEmail = email.lower().strip()
        row = self.connection.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (normalizedEmail,),
        ).fetchone()

        passwordHash = str(row["password_hash"]) if row else self.dummyHash
        if not self._verifyPasswordHash(passwordHash, plain_password):
            return AuthResult(success=False, message=CREDENCIAIS_INVALIDAS)

        if row is None:
            return AuthResult(success=False, message=CREDENCIAIS_INVALIDAS)

        return AuthResult(success=True, message="login realizado com sucesso")

    def get_password_hash(self, user_id: int) -> str:
        row = self.connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError("usuário não encontrado")
        return str(row["password_hash"])
