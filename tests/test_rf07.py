from datetime import UTC, datetime, timedelta
import hashlib

from fastapi.testclient import TestClient

from gtd_backend.auth import AuthService, CREDENCIAIS_INVALIDAS
from gtd_backend.http import createApp
from gtd_backend.rf07 import InMemoryPasswordResetEmailSender, RF07Service


class MutableNowProvider:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current



def _buildService(
    now: datetime | None = None,
) -> tuple[RF07Service, AuthService, InMemoryPasswordResetEmailSender, MutableNowProvider]:
    authService = AuthService()
    emailSender = InMemoryPasswordResetEmailSender()
    fixedNow = now if now is not None else datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    mutableNowProvider = MutableNowProvider(current=fixedNow)
    service = RF07Service(
        authService=authService,
        emailSender=emailSender,
        nowProvider=mutableNowProvider.now,
    )
    return service, authService, emailSender, mutableNowProvider



def _buildHttpClient(
    now: datetime | None = None,
) -> tuple[TestClient, InMemoryPasswordResetEmailSender, MutableNowProvider]:
    app = createApp()
    fixedNow = now if now is not None else datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    mutableNowProvider = MutableNowProvider(current=fixedNow)
    app.state.rf07EmailSender = InMemoryPasswordResetEmailSender()
    app.state.rf07Service = RF07Service(
        authService=app.state.authService,
        emailSender=app.state.rf07EmailSender,
        nowProvider=mutableNowProvider.now,
    )
    return TestClient(app), app.state.rf07EmailSender, mutableNowProvider


# Bloco: testes de serviço (RF07)
def test_rf07_servico_solicitacao_nao_revela_existencia_da_conta() -> None:
    service, authService, emailSender, _ = _buildService()
    authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("inexistente@unioeste.br")
    respostaContaExistente = service.requestPasswordReset("aluna@unioeste.br")

    totalTokens = service.connection.execute(
        "SELECT COUNT(*) AS total FROM password_reset_tokens"
    ).fetchone()
    assert respostaContaExistente is None
    assert int(totalTokens["total"]) == 1
    assert len(emailSender.queuedMessages) == 1



def test_rf07_servico_token_gerado_com_expiracao() -> None:
    fixedNow = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    service, authService, emailSender, _ = _buildService(now=fixedNow)
    userId = authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("  ALUNA@unioeste.br ")

    sent = emailSender.queuedMessages[0]
    row = service.connection.execute(
        "SELECT user_id, token_hash, expires_at, created_at FROM password_reset_tokens"
    ).fetchone()

    assert row is not None
    assert int(row["user_id"]) == userId
    assert str(row["token_hash"]) == hashlib.sha256(sent["resetToken"].encode("utf-8")).hexdigest()
    assert datetime.fromisoformat(str(row["created_at"])) == fixedNow
    assert datetime.fromisoformat(str(row["expires_at"])) == fixedNow + timedelta(hours=1)



def test_rf07_servico_rejeita_token_invalido() -> None:
    service, _, _, _ = _buildService()

    try:
        service.confirmPasswordReset("token-inexistente-super-seguro", "NovaSenha123")
        assert False, "esperava erro para token inválido"
    except ValueError as error:
        assert str(error) == CREDENCIAIS_INVALIDAS



def test_rf07_servico_rejeita_token_expirado() -> None:
    fixedNow = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    service, authService, emailSender, mutableNowProvider = _buildService(now=fixedNow)
    authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("aluna@unioeste.br")
    token = emailSender.queuedMessages[0]["resetToken"]

    mutableNowProvider.current = fixedNow + timedelta(hours=2)

    try:
        service.confirmPasswordReset(token, "NovaSenha123")
        assert False, "esperava erro para token expirado"
    except ValueError as error:
        assert str(error) == CREDENCIAIS_INVALIDAS



def test_rf07_servico_reset_com_token_valido_atualiza_hash_argon2id() -> None:
    service, authService, emailSender, _ = _buildService()
    userId = authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("aluna@unioeste.br")
    token = emailSender.queuedMessages[0]["resetToken"]

    service.confirmPasswordReset(token, "NovaSenhaForte123")

    assert authService.login("aluna@unioeste.br", "SenhaAntiga123").success is False
    assert authService.login("aluna@unioeste.br", "NovaSenhaForte123").success is True
    assert authService.get_password_hash(userId).startswith("$argon2id$")



def test_rf07_servico_token_torna_se_inutilizavel_apos_uso() -> None:
    service, authService, emailSender, _ = _buildService()
    authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("aluna@unioeste.br")
    token = emailSender.queuedMessages[0]["resetToken"]

    service.confirmPasswordReset(token, "NovaSenhaForte123")

    try:
        service.confirmPasswordReset(token, "OutraSenha123")
        assert False, "esperava erro para token já utilizado"
    except ValueError as error:
        assert str(error) == CREDENCIAIS_INVALIDAS



def test_rf07_servico_rejeicao_de_payloads_invalidos() -> None:
    service, authService, _, _ = _buildService()
    authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    invalidPayloads = [
        ("token-curto", "NovaSenha123"),
        ("token-inexistente-super-seguro", "1234567"),
    ]

    for token, newPassword in invalidPayloads:
        try:
            service.confirmPasswordReset(token, newPassword)
            assert False, "esperava erro para payload inválido"
        except ValueError:
            pass


# Bloco: testes HTTP (RF07)
def test_rf07_http_request_mesma_resposta_para_emails_existentes_e_inexistentes() -> None:
    client, emailSender, _ = _buildHttpClient()

    responseInexistente = client.post(
        "/auth/password-reset/request",
        json={"email": "inexistente@unioeste.br"},
    )

    client.app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    responseExistente = client.post(
        "/auth/password-reset/request",
        json={"email": "aluna@unioeste.br"},
    )

    expectedBody = {
        "success": True,
        "message": "se a conta existir, enviaremos instruções por e-mail",
    }
    assert responseInexistente.status_code == 200
    assert responseExistente.status_code == 200
    assert responseInexistente.json() == responseExistente.json() == expectedBody
    assert len(emailSender.queuedMessages) == 1



def test_rf07_http_confirm_sucesso_e_erro() -> None:
    client, emailSender, _ = _buildHttpClient()
    client.app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    client.post("/auth/password-reset/request", json={"email": "aluna@unioeste.br"})
    tokenValido = emailSender.queuedMessages[0]["resetToken"]

    responseSucesso = client.post(
        "/auth/password-reset/confirm",
        json={"token": tokenValido, "newPassword": "SenhaNovaForte123"},
    )
    responseErro = client.post(
        "/auth/password-reset/confirm",
        json={"token": tokenValido, "newPassword": "SenhaMaisNova123"},
    )

    assert responseSucesso.status_code == 200
    assert responseSucesso.json() == {
        "success": True,
        "message": "senha redefinida com sucesso",
    }
    assert responseErro.status_code == 400
    assert responseErro.json() == {
        "success": False,
        "message": CREDENCIAIS_INVALIDAS,
    }



def test_rf07_http_rejeita_payload_incompleto_e_campos_extras_com_422() -> None:
    client, _, _ = _buildHttpClient()

    requestPayloadIncompleto = client.post("/auth/password-reset/request", json={})
    requestPayloadExtra = client.post(
        "/auth/password-reset/request",
        json={"email": "aluna@unioeste.br", "extra": "indevido"},
    )
    confirmPayloadIncompleto = client.post("/auth/password-reset/confirm", json={})
    confirmPayloadExtra = client.post(
        "/auth/password-reset/confirm",
        json={
            "token": "token-inexistente-super-seguro",
            "newPassword": "SenhaNovaForte123",
            "extra": "indevido",
        },
    )

    assert requestPayloadIncompleto.status_code == 422
    assert requestPayloadExtra.status_code == 422
    assert confirmPayloadIncompleto.status_code == 422
    assert confirmPayloadExtra.status_code == 422
