import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gtd_backend.auth import AuthService

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


def _minimizeEmailIdentifier(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]


def _buildRateLimitKey(clientIp: str, email: str) -> str:
    minimizedEmail = _minimizeEmailIdentifier(email)
    return f"ip:{clientIp}|email:{minimizedEmail}"


def createApp(
    rateLimiter: RateLimiter | None = None,
    nowProvider: Callable[[], float] | None = None,
) -> FastAPI:
    app = FastAPI(title="GTD Pedagógico Unioeste")
    app.state.authService = AuthService()
    app.state.rateLimiter = rateLimiter or MemoryRateLimiter(maxAttempts=5, windowSeconds=60)
    app.state.nowProvider = nowProvider or time.time

    @app.post("/auth/login", response_model=LoginResponse)
    def login(loginRequest: LoginRequest, request: Request):
        clientIp = request.client.host if request.client else "unknown"
        rateLimitKey = _buildRateLimitKey(clientIp=clientIp, email=loginRequest.email)
        now = app.state.nowProvider()

        if not app.state.rateLimiter.allow(key=rateLimitKey, now=now):
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
        return LoginResponse(success=True, message=authResult.message)

    return app
