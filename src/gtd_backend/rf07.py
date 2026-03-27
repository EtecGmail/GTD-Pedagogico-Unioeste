from datetime import datetime, timedelta
import hashlib
import secrets
import sqlite3
from typing import Protocol

from gtd_backend.auth import AuthService, CREDENCIAIS_INVALIDAS


class PasswordResetEmailSender(Protocol):
    def sendPasswordResetEmail(self, toEmail: str, resetToken: str, expiresAt: str) -> None:
        ...


class InMemoryPasswordResetEmailSender:
    def __init__(self) -> None:
        self.queuedMessages: list[dict[str, str]] = []

    def sendPasswordResetEmail(self, toEmail: str, resetToken: str, expiresAt: str) -> None:
        self.queuedMessages.append(
            {
                "toEmail": toEmail,
                "resetToken": resetToken,
                "expiresAt": expiresAt,
            }
        )


class RF07Service:
    def __init__(
        self,
        authService: AuthService,
        emailSender: PasswordResetEmailSender,
        nowProvider: callable,
        tokenTtlHours: int = 1,
    ) -> None:
        self.authService = authService
        self.emailSender = emailSender
        self.nowProvider = nowProvider
        self.tokenTtlHours = tokenTtlHours
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)"
        )
        self.connection.commit()

    def _normalizeEmail(self, email: str) -> str:
        normalizedEmail = email.lower().strip()
        if "@" not in normalizedEmail or normalizedEmail.startswith("@") or normalizedEmail.endswith("@"):
            raise ValueError("e-mail inválido")
        localPart, domainPart = normalizedEmail.split("@", 1)
        if not localPart or not domainPart or "." not in domainPart:
            raise ValueError("e-mail inválido")
        return normalizedEmail

    def _validateToken(self, token: str) -> None:
        if not token or len(token.strip()) < 20:
            raise ValueError("credenciais inválidas")

    def _validateNewPassword(self, newPassword: str) -> None:
        if not newPassword or len(newPassword.strip()) < 8:
            raise ValueError("credenciais inválidas")

    def _hashToken(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def requestPasswordReset(self, email: str) -> None:
        normalizedEmail = self._normalizeEmail(email)
        user = self.authService.findUserByEmail(normalizedEmail)
        if user is None:
            return

        rawToken = secrets.token_urlsafe(32)
        now = self.nowProvider()
        expiresAt = now + timedelta(hours=self.tokenTtlHours)
        tokenHash = self._hashToken(rawToken)

        self.connection.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used_at, created_at)
            VALUES (?, ?, ?, NULL, ?)
            """,
            (
                int(user["id"]),
                tokenHash,
                expiresAt.isoformat(),
                now.isoformat(),
            ),
        )
        self.connection.commit()
        self.emailSender.sendPasswordResetEmail(
            toEmail=str(user["email"]),
            resetToken=rawToken,
            expiresAt=expiresAt.isoformat(),
        )

    def confirmPasswordReset(self, token: str, newPassword: str) -> None:
        self._validateToken(token)
        self._validateNewPassword(newPassword)

        now = self.nowProvider()
        tokenHash = self._hashToken(token.strip())
        row = self.connection.execute(
            """
            SELECT id, user_id, expires_at, used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (tokenHash,),
        ).fetchone()

        if row is None:
            raise ValueError(CREDENCIAIS_INVALIDAS)

        expiresAt = datetime.fromisoformat(str(row["expires_at"]))
        if row["used_at"] is not None or now >= expiresAt:
            raise ValueError(CREDENCIAIS_INVALIDAS)

        passwordHash = self.authService.passwordHasher.hash(newPassword.strip())
        self.authService.updateUserPasswordHash(int(row["user_id"]), passwordHash)

        self.connection.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
            (now.isoformat(), int(row["id"])),
        )
        self.connection.commit()
