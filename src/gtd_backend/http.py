import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from base64 import b64decode

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gtd_backend.auth import AuthService
from gtd_backend.rf01 import RF01Service
from gtd_backend.rf02 import RF02Service
from gtd_backend.rf03 import RF03Service
from gtd_backend.rf04 import RF04Service, InMemoryCertificateStorage
from gtd_backend.rf05 import RF05Service
from gtd_backend.rf06 import RF06Service

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


class ErrorResponse(BaseModel):
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
    app.state.rf01Service = RF01Service()
    app.state.rf02Service = RF02Service()
    app.state.rf03Service = RF03Service()
    app.state.rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    app.state.rf05Service = RF05Service(rf04Service=app.state.rf04Service, defaultTargetHours=200)
    app.state.rf06Service = RF06Service(rf02Service=app.state.rf02Service)
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

    @app.post(
        "/rf01/professors",
        response_model=CreateProfessorResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def createProfessor(request: CreateProfessorRequest):
        try:
            professorId = app.state.rf01Service.createProfessor(
                name=request.name,
                email=request.email,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateProfessorResponse(id=professorId)

    @app.get("/rf01/professors", response_model=list[ProfessorListItem])
    def listProfessors():
        return app.state.rf01Service.listProfessors()

    @app.post(
        "/rf01/disciplines",
        response_model=CreateDisciplineResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def createDiscipline(request: CreateDisciplineRequest):
        try:
            disciplineId = app.state.rf01Service.createDiscipline(
                name=request.name,
                code=request.code,
                professorIds=request.professorIds,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateDisciplineResponse(id=disciplineId)

    @app.get("/rf01/disciplines", response_model=list[DisciplineListItem])
    def listDisciplines():
        return app.state.rf01Service.listDisciplines()

    @app.post(
        "/rf02/inbox-items",
        response_model=CreateInboxItemResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def captureInboxItem(request: CreateInboxItemRequest):
        try:
            inboxItemId = app.state.rf02Service.captureInboxItem(content=request.content)
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateInboxItemResponse(id=inboxItemId)

    @app.get("/rf02/inbox-items", response_model=list[InboxItemListResponse])
    def listInboxItems():
        return app.state.rf02Service.listInboxItems()


    @app.patch(
        "/rf06/inbox-items/{itemId}/status",
        response_model=UpdateInboxItemStatusResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    def changeInboxItemStatus(itemId: int, request: UpdateInboxItemStatusRequest):
        try:
            updatedItem = app.state.rf06Service.changeInboxItemStatus(
                itemId=itemId,
                targetStatus=request.status,
            )
        except LookupError as error:
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

    @app.get("/rf06/inbox-items", response_model=list[InboxItemListResponse])
    def listInboxItemsByStatus(status: str = Query(default="inbox")):
        try:
            return app.state.rf06Service.listInboxItems(status=status)
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
    def createReadingPlan(request: CreateReadingPlanRequest):
        try:
            readingPlanId = app.state.rf03Service.createReadingPlan(
                totalPages=request.totalPages,
                deadlineDays=request.deadlineDays,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateReadingPlanResponse(id=readingPlanId)

    @app.get("/rf03/reading-plans", response_model=list[ReadingPlanListResponse])
    def listReadingPlans():
        return app.state.rf03Service.listReadingPlans()



    @app.post(
        "/rf04/certificates",
        response_model=CreateCertificateResponse,
        status_code=201,
        responses={400: {"model": ErrorResponse}},
    )
    def uploadCertificate(request: CreateCertificateRequest):
        try:
            fileContent = b64decode(request.contentBase64, validate=True)
        except Exception:
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
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return CreateCertificateResponse(id=certificateId)

    @app.get("/rf04/certificates", response_model=list[CertificateListItem])
    def listCertificates():
        return app.state.rf04Service.listCertificates()

    @app.get("/rf05/acc-progress", response_model=AccHoursProgressResponse)
    def getAccHoursProgress(targetHours: int | None = Query(default=None, gt=0, le=10000)):
        try:
            progress = app.state.rf05Service.getAccHoursProgress(targetHours=targetHours)
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(error)},
            )
        return AccHoursProgressResponse(**progress)

    return app
