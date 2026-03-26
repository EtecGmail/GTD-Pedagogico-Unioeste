from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from gtd_backend.auth import AuthService


class LoginRequest(BaseModel):
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


def createApp() -> FastAPI:
    app = FastAPI(title="GTD Pedagógico Unioeste")
    app.state.authService = AuthService()

    @app.post("/auth/login", response_model=LoginResponse)
    def login(loginRequest: LoginRequest):
        authResult = app.state.authService.login(
            loginRequest.email,
            loginRequest.password,
        )

        if not authResult.success:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": authResult.message},
            )

        return LoginResponse(success=True, message=authResult.message)

    return app
