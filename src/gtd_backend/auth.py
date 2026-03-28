from dataclasses import dataclass
import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from gtd_backend.persistence import applyMigrations

CREDENCIAIS_INVALIDAS = "credenciais inválidas"
EMAIL_JA_CADASTRADO = "e-mail já cadastrado"
PAPEL_USUARIO_INVALIDO = "papel de usuário inválido"
DEFAULT_USER_ROLE = "aluno"
ALLOWED_USER_ROLES = {"aluno", "admin"}


class DomainError(Exception):
    """Erro de domínio para regras de autenticação."""


class DuplicateEmailError(DomainError):
    """Erro de domínio para tentativa de cadastro com e-mail já existente."""


@dataclass(frozen=True)
class AuthResult:
    success: bool
    message: str


class AuthService:
    """Serviço de autenticação com login blindado e Argon2id."""

    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        ownsConnection = connection is None
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        if ownsConnection:
            applyMigrations(connection=self.connection)
        self.passwordHasher = PasswordHasher()
        self.dummyHash = self.passwordHasher.hash("senha-falsa-para-timing-attack")

    def _verifyPasswordHash(self, passwordHash: str, plainPassword: str) -> bool:
        try:
            verifyResult = self.passwordHasher.verify(passwordHash, plainPassword)
            return bool(verifyResult)
        except (VerifyMismatchError, VerificationError):
            return False

    def _validatePasswordPolicy(self, plainPassword: str) -> str:
        normalizedPassword = plainPassword.strip()
        if len(normalizedPassword) < 8:
            raise ValueError(CREDENCIAIS_INVALIDAS)
        return normalizedPassword

    def _normalizeRole(self, role: str) -> str:
        normalizedRole = role.strip().lower()
        if normalizedRole not in ALLOWED_USER_ROLES:
            raise ValueError(PAPEL_USUARIO_INVALIDO)
        return normalizedRole

    def register_user(self, email: str, plain_password: str, role: str = DEFAULT_USER_ROLE) -> int:
        normalizedRole = self._normalizeRole(role)
        passwordHash = self.passwordHasher.hash(plain_password)
        try:
            cursor = self.connection.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                (email.lower().strip(), passwordHash, normalizedRole),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateEmailError(EMAIL_JA_CADASTRADO) from error
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


    def findUserByEmail(self, email: str) -> dict[str, int | str] | None:
        normalizedEmail = email.lower().strip()
        row = self.connection.execute(
            "SELECT id, email, role FROM users WHERE email = ?",
            (normalizedEmail,),
        ).fetchone()
        if row is None:
            return None
        return {"id": int(row["id"]), "email": str(row["email"]), "role": str(row["role"])}

    def updateUserPasswordHash(self, userId: int, passwordHash: str) -> None:
        cursor = self.connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (passwordHash, userId),
        )
        if cursor.rowcount == 0:
            raise ValueError("usuário não encontrado")
        self.connection.commit()

    def updatePassword(self, userId: int, newPlainPassword: str) -> None:
        validatedPassword = self._validatePasswordPolicy(newPlainPassword)
        newPasswordHash = self.passwordHasher.hash(validatedPassword)
        self.updateUserPasswordHash(userId, newPasswordHash)

    def get_password_hash(self, user_id: int) -> str:
        row = self.connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError("usuário não encontrado")
        return str(row["password_hash"])
