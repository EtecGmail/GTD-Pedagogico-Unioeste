import hashlib
import logging
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from base64 import b64decode

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gtd_backend.auth import ALLOWED_USER_ROLES, AuthService
from gtd_backend.persistence import DEFAULT_DATABASE_URL, createSqliteConnection
from gtd_backend.rf01 import RF01Service
from gtd_backend.rf02 import RF02Service
from gtd_backend.rf03 import RF03Service
from gtd_backend.rf04 import (
    ContentCipher,
    RF04Service,
    InMemoryCertificateStorage,
    buildCertificateCipherFromEnvironment,
)
from gtd_backend.rf05 import RF05Service
from gtd_backend.rf06 import RF06Service
from gtd_backend.rf07 import InMemoryPasswordResetEmailSender, RF07Service
from gtd_backend.rf08 import RF08Service
from gtd_backend.rf09 import SecurityEventService
from gtd_backend.rf10 import RF10Service

logger = logging.getLogger("gtd_backend.auth_http")

RATE_LIMIT_EXCEDIDO = "muitas tentativas; tente novamente mais tarde"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def validateEmail(cls, email: str) -> str:
        normalizedEmail = email.strip().lower()
        if "@" not in normalizedEmail:
            raise ValueError("email inválido")
        return normalizedEmail


class LoginResponse(BaseModel):
    success: bool
    message: str
    accessToken: str | None = None
    tokenType: str | None = None
    role: str | None = None


class ErrorResponse(BaseModel):
    success: bool
    message: str


class RequestPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def validateEmail(cls, email: str) -> str:
        normalizedEmail = email.strip().lower()
        if "@" not in normalizedEmail:
            raise ValueError("email inválido")
        return normalizedEmail


class RequestPasswordResetResponse(BaseModel):
    success: bool
    message: str


class ConfirmPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=255)
    newPassword: str = Field(min_length=8, max_length=255)

    @field_validator("token")
    @classmethod
    def validateToken(cls, token: str) -> str:
        normalizedToken = token.strip()
        if len(normalizedToken) < 20:
            raise ValueError("credenciais inválidas")
        return normalizedToken

    @field_validator("newPassword")
    @classmethod
    def validateNewPassword(cls, newPassword: str) -> str:
        normalizedPassword = newPassword.strip()
        if len(normalizedPassword) < 8:
            raise ValueError("credenciais inválidas")
        return normalizedPassword


class ConfirmPasswordResetResponse(BaseModel):
    success: bool
    message: str


class CreateProfessorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    email: str = Field(min_length=3, max_length=255)

    @field_validator("name")
    @classmethod
    def validateName(cls, name: str) -> str:
        normalizedName = " ".join(name.strip().split())
        if len(normalizedName) < 3:
            raise ValueError("nome do professor inválido")
        return normalizedName

    @field_validator("email")
    @classmethod
    def validateProfessorEmail(cls, email: str) -> str:
        normalizedEmail = email.strip().lower()
        if "@" not in normalizedEmail:
            raise ValueError("email do professor inválido")
        return normalizedEmail


class CreateProfessorResponse(BaseModel):
    id: int


class ProfessorListItem(BaseModel):
    id: int
    name: str
    email: str


class CreateDisciplineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    code: str = Field(min_length=2, max_length=30)
    professorIds: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validateDisciplineName(cls, name: str) -> str:
        normalizedName = " ".join(name.strip().split())
        if len(normalizedName) < 3:
            raise ValueError("nome da disciplina inválido")
        return normalizedName

    @field_validator("code")
    @classmethod
    def validateDisciplineCode(cls, code: str) -> str:
        normalizedCode = code.strip().upper()
        if len(normalizedCode) < 2:
            raise ValueError("código da disciplina inválido")
        return normalizedCode


class CreateDisciplineResponse(BaseModel):
    id: int


class DisciplineListItem(BaseModel):
    id: int
    name: str
    code: str
    professorIds: list[int]


class CreateInboxItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=500)

    @field_validator("content")
    @classmethod
    def validateContent(cls, content: str) -> str:
        normalizedContent = " ".join(content.strip().split())
        if not normalizedContent:
            raise ValueError("conteúdo da captura é obrigatório")
        return normalizedContent


class CreateInboxItemResponse(BaseModel):
    id: int


class InboxItemListResponse(BaseModel):
    id: int
    content: str
    status: str
    createdAt: str


class UpdateInboxItemStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=30)

    @field_validator("status")
    @classmethod
    def validateStatus(cls, status: str) -> str:
        normalizedStatus = status.strip().lower()
        if normalizedStatus not in {"next_action", "waiting"}:
            raise ValueError("status de destino inválido")
        return normalizedStatus


class UpdateInboxItemStatusResponse(BaseModel):
    id: int
    status: str


class CreateReadingPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totalPages: int = Field(gt=0, le=100000)
    deadlineDays: int = Field(gt=0, le=3650)


class CreateReadingPlanResponse(BaseModel):
    id: int


class ReadingPlanListResponse(BaseModel):
    id: int
    totalPages: int
    deadlineDays: int
    dailyGoal: int
    isOverloaded: bool
    remainingPages: int
    createdAt: str




class CreateCertificateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    originalName: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=100)
    contentBase64: str = Field(min_length=1)
    hours: int | None = Field(default=None, ge=0, le=200)


class CreateCertificateResponse(BaseModel):
    id: int


class CertificateListItem(BaseModel):
    id: int
    fileIdentifier: str
    originalName: str
    contentType: str
    sizeBytes: int
    hours: int | None
    storageKey: str
    metadata: dict[str, int | bool]
    createdAt: str


class AccHoursProgressResponse(BaseModel):
    totalHours: int
    targetHours: int
    remainingHours: int
    percentage: float
    isCompleted: bool


class DashboardStatusCountsResponse(BaseModel):
    inbox: int
    nextAction: int
    waiting: int


class DashboardReadingSummaryResponse(BaseModel):
    totalPlans: int
    overloadedPlans: int
    completedPlans: int
    totalPages: int
    remainingPages: int
    averageCompletionPercentage: float


class StudentDashboardResponse(BaseModel):
    statusCounts: DashboardStatusCountsResponse
    accProgress: AccHoursProgressResponse
    readingSummary: DashboardReadingSummaryResponse


class StorageUsageResponse(BaseModel):
    totalBytesUsed: int
    quotaBytes: int
    percentageUsed: float
    isNearLimit: bool
    isOverLimit: bool


class AdvanceReadingPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pagesRead: int = Field(gt=0, le=100000)


class AdvanceReadingPlanResponse(BaseModel):
    id: int
    remainingPages: int
    isCompleted: bool


class RateLimiter:
    def allow(self, key: str, now: float | None = None) -> bool:
        raise NotImplementedError


@dataclass
class _RateLimitState:
    attempts: int
    windowStart: float


class MemoryRateLimiter(RateLimiter):
    def __init__(self, maxAttempts: int, windowSeconds: int) -> None:
        self.maxAttempts = maxAttempts
        self.windowSeconds = windowSeconds
        self._states: dict[str, _RateLimitState] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        currentTime = now if now is not None else time.time()
        state = self._states.get(key)

        if state is None or currentTime - state.windowStart >= self.windowSeconds:
            self._states[key] = _RateLimitState(attempts=1, windowStart=currentTime)
            return True

        if state.attempts >= self.maxAttempts:
            return False

        state.attempts += 1
        return True


class SessionStore:
    def createSession(self, userId: int, role: str, now: float | None = None) -> str:
        raise NotImplementedError

    def resolveSession(self, accessToken: str, now: float | None = None) -> dict[str, int | str] | None:
        raise NotImplementedError

    def revokeSession(self, accessToken: str, now: float | None = None) -> bool:
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._tokenToUser: dict[str, dict[str, int | str]] = {}

    def createSession(self, userId: int, role: str, now: float | None = None) -> str:
        if userId <= 0:
            raise ValueError("usuário inválido")
        normalizedRole = role.strip().lower()
        if normalizedRole not in ALLOWED_USER_ROLES:
            raise ValueError("papel de sessão inválido")
        accessToken = secrets.token_urlsafe(32)
        self._tokenToUser[accessToken] = {"userId": userId, "role": normalizedRole}
        return accessToken

    def resolveSession(self, accessToken: str, now: float | None = None) -> dict[str, int | str] | None:
        return self._tokenToUser.get(accessToken)

    def revokeSession(self, accessToken: str, now: float | None = None) -> bool:
        return self._tokenToUser.pop(accessToken, None) is not None


class SqliteSessionStore(SessionStore):
    def __init__(self, connection: sqlite3.Connection, sessionTtlSeconds: int = 12 * 60 * 60) -> None:
        if sessionTtlSeconds <= 0:
            raise ValueError("ttl da sessão deve ser positivo")
        self.connection = connection
        self.sessionTtlSeconds = sessionTtlSeconds
        self._createTableIfNotExists()

    def _createTableIfNotExists(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked_at REAL
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at)"
        )
        self.connection.commit()

    def _hashToken(self, accessToken: str) -> str:
        return hashlib.sha256(accessToken.encode("utf-8")).hexdigest()

    def createSession(self, userId: int, role: str, now: float | None = None) -> str:
        if userId <= 0:
            raise ValueError("usuário inválido")
        normalizedRole = role.strip().lower()
        if normalizedRole not in ALLOWED_USER_ROLES:
            raise ValueError("papel de sessão inválido")
        nowValue = now if now is not None else time.time()
        accessToken = secrets.token_urlsafe(32)
        self.connection.execute(
            """
            INSERT INTO auth_sessions (token_hash, user_id, role, created_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (
                self._hashToken(accessToken),
                userId,
                normalizedRole,
                nowValue,
                nowValue + float(self.sessionTtlSeconds),
            ),
        )
        self.connection.commit()
        return accessToken

    def resolveSession(self, accessToken: str, now: float | None = None) -> dict[str, int | str] | None:
        nowValue = now if now is not None else time.time()
        row = self.connection.execute(
            """
            SELECT user_id, role, expires_at, revoked_at
            FROM auth_sessions
            WHERE token_hash = ?
            """,
            (self._hashToken(accessToken),),
        ).fetchone()
        if row is None:
            return None
        if row["revoked_at"] is not None:
            return None
        if float(row["expires_at"]) <= nowValue:
            return None
        return {"userId": int(row["user_id"]), "role": str(row["role"])}

    def revokeSession(self, accessToken: str, now: float | None = None) -> bool:
        nowValue = now if now is not None else time.time()
        cursor = self.connection.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (nowValue, self._hashToken(accessToken)),
        )
        self.connection.commit()
        return cursor.rowcount > 0


@dataclass(frozen=True)
class CurrentUser:
    userId: int
    role: str


def _minimizeEmailIdentifier(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]


def _buildRateLimitKey(clientIp: str, email: str, scope: str = "default") -> str:
    minimizedEmail = _minimizeEmailIdentifier(email)
    return f"scope:{scope}|ip:{clientIp}|email:{minimizedEmail}"


def _minimizeIpIdentifier(clientIp: str) -> str:
    return hashlib.sha256(clientIp.encode("utf-8")).hexdigest()[:12]


def createApp(
    rateLimiter: RateLimiter | None = None,
    nowProvider: Callable[[], float] | None = None,
    databaseUrl: str = DEFAULT_DATABASE_URL,
    sessionTtlSeconds: int = 12 * 60 * 60,
    environmentName: str | None = None,
    certificateCipher: ContentCipher | None = None,
) -> FastAPI:
    app = FastAPI(title="GTD Pedagógico Unioeste")
    app.state.databaseUrl = databaseUrl
    app.state.dbConnection = createSqliteConnection(databaseUrl=databaseUrl)
    app.state.authService = AuthService(connection=app.state.dbConnection)
    app.state.rf01Service = RF01Service(connection=app.state.dbConnection)
    app.state.rf02Service = RF02Service(connection=app.state.dbConnection)
    app.state.rf03Service = RF03Service(connection=app.state.dbConnection)
    resolvedCertificateCipher = certificateCipher or buildCertificateCipherFromEnvironment(
        environmentName=environmentName
    )
    app.state.rf04Service = RF04Service(
        storage=InMemoryCertificateStorage(),
        contentCipher=resolvedCertificateCipher,
        connection=app.state.dbConnection,
    )
    app.state.rf05Service = RF05Service(rf04Service=app.state.rf04Service, defaultTargetHours=200)
    app.state.rf06Service = RF06Service(rf02Service=app.state.rf02Service)
    app.state.rf08Service = RF08Service(
        rf03Service=app.state.rf03Service,
        rf05Service=app.state.rf05Service,
        rf06Service=app.state.rf06Service,
    )
    app.state.rf07EmailSender = InMemoryPasswordResetEmailSender()
    app.state.rf07Service = RF07Service(
        authService=app.state.authService,
        emailSender=app.state.rf07EmailSender,
        nowProvider=lambda: datetime.now().astimezone(),
        connection=app.state.dbConnection,
    )
    app.state.rf09Service = SecurityEventService(connection=app.state.dbConnection)
    app.state.rf10Service = RF10Service(
        rf04Service=app.state.rf04Service,
        quotaBytes=5 * 1024 * 1024,
        rf09Service=app.state.rf09Service,
    )
    app.state.rateLimiter = rateLimiter or MemoryRateLimiter(maxAttempts=5, windowSeconds=60)
    app.state.nowProvider = nowProvider or time.time
    app.state.sessionStore = SqliteSessionStore(
        connection=app.state.dbConnection,
        sessionTtlSeconds=sessionTtlSeconds,
    )

    def _extractBearerToken(authorizationHeader: str | None) -> str | None:
        if authorizationHeader is None:
            return None
        headerParts = authorizationHeader.strip().split(" ", 1)
        if len(headerParts) != 2:
            return None
        authScheme, accessToken = headerParts
        if authScheme.lower() != "bearer":
            return None
        normalizedToken = accessToken.strip()
        if len(normalizedToken) < 20:
            return None
        return normalizedToken

    def getCurrentUser(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> CurrentUser:
        accessToken = _extractBearerToken(authorization)
        if accessToken is None:
            clientIp = request.client.host if request.client else "unknown"
            app.state.rf09Service.recordEvent(
                eventType="authorization_denied",
                result="denied",
                metadata={"reason": "missing_or_invalid_token", "ipHash": _minimizeIpIdentifier(clientIp)},
            )
            raise HTTPException(status_code=401, detail="não autenticado")
        session = app.state.sessionStore.resolveSession(accessToken=accessToken, now=app.state.nowProvider())
        if session is None:
            clientIp = request.client.host if request.client else "unknown"
            app.state.rf09Service.recordEvent(
                eventType="authorization_denied",
                result="denied",
                metadata={"reason": "invalid_session", "ipHash": _minimizeIpIdentifier(clientIp)},
            )
            raise HTTPException(status_code=401, detail="não autenticado")
        role = str(session.get("role", "")).strip().lower()
        userId = int(session.get("userId", 0))
        if role not in ALLOWED_USER_ROLES or userId <= 0:
            clientIp = request.client.host if request.client else "unknown"
            app.state.rf09Service.recordEvent(
                eventType="authorization_denied",
                result="denied",
                metadata={"reason": "invalid_role_session", "ipHash": _minimizeIpIdentifier(clientIp)},
            )
            raise HTTPException(status_code=401, detail="não autenticado")
        return CurrentUser(userId=userId, role=role)

    def requireAdmin(currentUser: CurrentUser = Depends(getCurrentUser)) -> CurrentUser:
        if currentUser.role != "admin":
            app.state.rf09Service.recordEvent(
                eventType="authorization_denied",
                result="denied",
                userId=currentUser.userId,
                metadata={"reason": "admin_role_required", "resource": "rf09_security_events"},
            )
            raise HTTPException(status_code=403, detail="acesso negado")
        return currentUser

    @app.post("/auth/login", response_model=LoginResponse)
    def login(loginRequest: LoginRequest, request: Request):
        clientIp = request.client.host if request.client else "unknown"
        rateLimitKey = _buildRateLimitKey(
            clientIp=clientIp,
            email=loginRequest.email,
            scope="auth_login",
        )
        now = app.state.nowProvider()

        if not app.state.rateLimiter.allow(key=rateLimitKey, now=now):
            app.state.rf09Service.recordEvent(
                eventType="auth_login_rate_limit",
                result="blocked",
                metadata={
                    "emailHash": _minimizeEmailIdentifier(loginRequest.email),
                    "ipHash": _minimizeIpIdentifier(clientIp),
                    "scope": "auth_login",
                },
            )
            logger.warning(
                "evento=auth_login_rate_limited ip=%s email_hash=%s",
                clientIp,
                _minimizeEmailIdentifier(loginRequest.email),
            )
            return JSONResponse(
                status_code=429,
                content={"success": False, "message": RATE_LIMIT_EXCEDIDO},
            )

        authResult = app.state.authService.login(
            loginRequest.email,
            loginRequest.password,
        )

        if not authResult.success:
            app.state.rf09Service.recordEvent(
                eventType="auth_login",
                result="failure",
                metadata={
                    "emailHash": _minimizeEmailIdentifier(loginRequest.email),
                    "ipHash": _minimizeIpIdentifier(clientIp),
                },
            )
            logger.info(
                "evento=auth_login_fail ip=%s email_hash=%s",
                clientIp,
                _minimizeEmailIdentifier(loginRequest.email),
            )
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": authResult.message},
            )

        logger.info(
            "evento=auth_login_success ip=%s email_hash=%s",
            clientIp,
            _minimizeEmailIdentifier(loginRequest.email),
        )
        user = app.state.authService.findUserByEmail(loginRequest.email)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "credenciais inválidas"},
            )
        app.state.rf09Service.recordEvent(
            eventType="auth_login",
            result="success",
            userId=int(user["id"]),
            metadata={
                "emailHash": _minimizeEmailIdentifier(loginRequest.email),
                "ipHash": _minimizeIpIdentifier(clientIp),
            },
        )
        resolvedRole = str(user.get("role", "")).strip().lower()
        if resolvedRole not in ALLOWED_USER_ROLES:
            app.state.rf09Service.recordEvent(
                eventType="auth_login",
                result="failure",
                metadata={"reason": "invalid_user_role"},
            )
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "credenciais inválidas"},
            )
        accessToken = app.state.sessionStore.createSession(
            userId=int(user["id"]),
            role=resolvedRole,
            now=app.state.nowProvider(),
        )
        return LoginResponse(
            success=True,
            message=authResult.message,
            accessToken=accessToken,
            tokenType="Bearer",
            role=resolvedRole,
        )

    @app.post("/auth/logout")
    def logout(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ):
        accessToken = _extractBearerToken(authorization)
        if accessToken is None:
            raise HTTPException(status_code=401, detail="não autenticado")

        session = app.state.sessionStore.resolveSession(accessToken=accessToken, now=app.state.nowProvider())
        if session is None:
            raise HTTPException(status_code=401, detail="não autenticado")

        currentUserId = int(session.get("userId", 0))
        wasRevoked = app.state.sessionStore.revokeSession(accessToken=accessToken, now=app.state.nowProvider())
        if wasRevoked:
            app.state.rf09Service.recordEvent(
                eventType="auth_logout",
                result="success",
                userId=currentUserId if currentUserId > 0 else None,
                metadata={
                    "ipHash": _minimizeIpIdentifier(request.client.host if request.client else "unknown"),
                },
            )
        return {"success": True, "message": "logout realizado com sucesso"}

    @app.post(
        "/auth/password-reset/request",
        response_model=RequestPasswordResetResponse,
        responses={429: {"model": ErrorResponse}},
    )
    def requestPasswordReset(requestBody: RequestPasswordResetRequest, request: Request):
        clientIp = request.client.host if request.client else "unknown"
        rateLimitKey = _buildRateLimitKey(
            clientIp=clientIp,
            email=requestBody.email,
            scope="auth_password_reset_request",
        )
        now = app.state.nowProvider()

        if not app.state.rateLimiter.allow(key=rateLimitKey, now=now):
            app.state.rf09Service.recordEvent(
                eventType="password_reset_request_rate_limit",
                result="blocked",
                metadata={
                    "emailHash": _minimizeEmailIdentifier(requestBody.email),
                    "ipHash": _minimizeIpIdentifier(clientIp),
                },
            )
            logger.warning(
                "evento=rf07_password_reset_rate_limited ip=%s email_hash=%s",
                clientIp,
                _minimizeEmailIdentifier(requestBody.email),
            )
            return JSONResponse(
                status_code=429,
                content={"success": False, "message": RATE_LIMIT_EXCEDIDO},
            )

        app.state.rf07Service.requestPasswordReset(requestBody.email)
        user = app.state.authService.findUserByEmail(requestBody.email)
        app.state.rf09Service.recordEvent(
            eventType="password_reset_request",
            result="success",
            userId=int(user["id"]) if user is not None else None,
            metadata={
                "emailHash": _minimizeEmailIdentifier(requestBody.email),
                "ipHash": _minimizeIpIdentifier(clientIp),
            },
        )
        logger.info(
            "evento=rf07_password_reset_requested ip=%s email_hash=%s",
            clientIp,
            _minimizeEmailIdentifier(requestBody.email),
        )
        return RequestPasswordResetResponse(
            success=True,
            message="se a conta existir, enviaremos instruções por e-mail",
        )

    @app.post(
        "/auth/password-reset/confirm",
        response_model=ConfirmPasswordResetResponse,
        responses={400: {"model": ErrorResponse}},
    )
    def confirmPasswordReset(requestBody: ConfirmPasswordResetRequest, request: Request):
        clientIp = request.client.host if request.client else "unknown"
        try:
            app.state.rf07Service.confirmPasswordReset(
                token=requestBody.token,
                newPassword=requestBody.newPassword,
            )
        except ValueError:
            app.state.rf09Service.recordEvent(
                eventType="password_reset_confirm",
                result="failure",
                metadata={"ipHash": _minimizeIpIdentifier(clientIp)},
            )
            logger.warning(
                "evento=rf07_password_reset_confirm_fail ip=%s",
                clientIp,
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "credenciais inválidas"},
            )

        logger.info("evento=rf07_password_reset_confirm_success ip=%s", clientIp)
        app.state.rf09Service.recordEvent(
            eventType="password_reset_confirm",
            result="success",
            metadata={"ipHash": _minimizeIpIdentifier(clientIp)},
        )
        return ConfirmPasswordResetResponse(
            success=True,
            message="senha redefinida com sucesso",
        )

    @app.post(
        "/rf01/professors",
        response_model=CreateProfessorResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def createProfessor(
        request: CreateProfessorRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            professorId = app.state.rf01Service.createProfessor(
                name=request.name,
                email=request.email,
                userId=currentUser.userId,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateProfessorResponse(id=professorId)

    @app.get("/rf01/professors", response_model=list[ProfessorListItem])
    def listProfessors(currentUser: CurrentUser = Depends(getCurrentUser)):
        return app.state.rf01Service.listProfessors(userId=currentUser.userId)

    @app.post(
        "/rf01/disciplines",
        response_model=CreateDisciplineResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def createDiscipline(
        request: CreateDisciplineRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            disciplineId = app.state.rf01Service.createDiscipline(
                name=request.name,
                code=request.code,
                professorIds=request.professorIds,
                userId=currentUser.userId,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateDisciplineResponse(id=disciplineId)

    @app.get("/rf01/disciplines", response_model=list[DisciplineListItem])
    def listDisciplines(currentUser: CurrentUser = Depends(getCurrentUser)):
        return app.state.rf01Service.listDisciplines(userId=currentUser.userId)

    @app.post(
        "/rf02/inbox-items",
        response_model=CreateInboxItemResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def captureInboxItem(
        request: CreateInboxItemRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            inboxItemId = app.state.rf02Service.captureInboxItem(
                content=request.content,
                userId=currentUser.userId,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateInboxItemResponse(id=inboxItemId)

    @app.get(
        "/rf02/inbox-items",
        response_model=list[InboxItemListResponse],
        responses={401: {"model": ErrorResponse}},
    )
    def listInboxItems(currentUser: CurrentUser = Depends(getCurrentUser)):
        return app.state.rf02Service.listInboxItems(userId=currentUser.userId)


    @app.patch(
        "/rf06/inbox-items/{itemId}/status",
        response_model=UpdateInboxItemStatusResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    def changeInboxItemStatus(
        itemId: int,
        request: UpdateInboxItemStatusRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            updatedItem = app.state.rf06Service.changeInboxItemStatus(
                itemId=itemId,
                targetStatus=request.status,
                userId=currentUser.userId,
            )
        except LookupError as error:
            app.state.rf09Service.recordEvent(
                eventType="authorization_denied",
                result="denied",
                userId=currentUser.userId,
                metadata={
                    "resource": "rf06_inbox_item_status",
                    "itemId": itemId,
                },
            )
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": str(error)},
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return UpdateInboxItemStatusResponse(**updatedItem)

    @app.get(
        "/rf06/inbox-items",
        response_model=list[InboxItemListResponse],
        responses={401: {"model": ErrorResponse}},
    )
    def listInboxItemsByStatus(
        status: str = Query(default="inbox"),
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            return app.state.rf06Service.listInboxItems(
                status=status,
                userId=currentUser.userId,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )

    @app.post(
        "/rf03/reading-plans",
        response_model=CreateReadingPlanResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def createReadingPlan(
        request: CreateReadingPlanRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            readingPlanId = app.state.rf03Service.createReadingPlan(
                totalPages=request.totalPages,
                deadlineDays=request.deadlineDays,
                userId=currentUser.userId,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateReadingPlanResponse(id=readingPlanId)

    @app.get("/rf03/reading-plans", response_model=list[ReadingPlanListResponse])
    def listReadingPlans(currentUser: CurrentUser = Depends(getCurrentUser)):
        return app.state.rf03Service.listReadingPlans(userId=currentUser.userId)



    @app.post(
        "/rf04/certificates",
        response_model=CreateCertificateResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def uploadCertificate(
        request: CreateCertificateRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            fileContent = b64decode(request.contentBase64, validate=True)
        except Exception:
            app.state.rf09Service.recordEvent(
                eventType="certificate_upload_rejected",
                result="rejected",
                userId=currentUser.userId,
                metadata={"reason": "invalid_base64_payload"},
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "payload de arquivo inválido"},
            )

        try:
            certificateId = app.state.rf04Service.uploadCertificate(
                originalName=request.originalName,
                contentType=request.contentType,
                content=fileContent,
                hours=request.hours,
                userId=currentUser.userId,
            )
        except ValueError as error:
            app.state.rf09Service.recordEvent(
                eventType="certificate_upload_rejected",
                result="rejected",
                userId=currentUser.userId,
                metadata={
                    "reason": str(error),
                    "contentType": request.contentType,
                    "originalName": request.originalName,
                },
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateCertificateResponse(id=certificateId)

    @app.get("/rf04/certificates", response_model=list[CertificateListItem])
    def listCertificates(currentUser: CurrentUser = Depends(getCurrentUser)):
        return app.state.rf04Service.listCertificates(userId=currentUser.userId)

    @app.get("/rf05/acc-progress", response_model=AccHoursProgressResponse)
    def getAccHoursProgress(
        targetHours: int | None = Query(default=None, gt=0, le=10000),
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            progress = app.state.rf05Service.getAccHoursProgress(
                targetHours=targetHours,
                userId=currentUser.userId,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return AccHoursProgressResponse(**progress)

    @app.get("/rf10/storage-usage", response_model=StorageUsageResponse)
    def getStorageUsage(currentUser: CurrentUser = Depends(getCurrentUser)):
        try:
            usageSummary = app.state.rf10Service.getStorageUsageSummary(userId=currentUser.userId)
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return StorageUsageResponse(**usageSummary)

    @app.get("/rf09/security-events")
    def listSecurityEvents(
        limit: int = Query(default=100, ge=1, le=500),
        currentUser: CurrentUser = Depends(requireAdmin),
    ):
        return app.state.rf09Service.listEvents(limit=limit)

    @app.get("/rf08/dashboard", response_model=StudentDashboardResponse)
    def getStudentDashboard(
        targetHours: int | None = Query(default=None, gt=0, le=10000),
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        dashboard = app.state.rf08Service.getStudentDashboard(
            userId=currentUser.userId,
            targetHours=targetHours,
        )
        return StudentDashboardResponse(**dashboard)

    @app.patch(
        "/rf08/reading-plans/{planId}/advance",
        response_model=AdvanceReadingPlanResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    def advanceReadingPlan(
        planId: int,
        request: AdvanceReadingPlanRequest,
        currentUser: CurrentUser = Depends(getCurrentUser),
    ):
        try:
            updatedReadingPlan = app.state.rf03Service.advanceReadingPlan(
                planId=planId,
                pagesRead=request.pagesRead,
                userId=currentUser.userId,
            )
        except LookupError as error:
            app.state.rf09Service.recordEvent(
                eventType="authorization_denied",
                result="denied",
                userId=currentUser.userId,
                metadata={
                    "resource": "rf08_reading_plan_advance",
                    "planId": planId,
                },
            )
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": str(error)},
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return AdvanceReadingPlanResponse(**updatedReadingPlan)

    return app
