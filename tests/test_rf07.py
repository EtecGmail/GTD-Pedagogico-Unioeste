from datetime import UTC, datetime, timedelta
import hashlib

from gtd_backend.auth import AuthService, CREDENCIAIS_INVALIDAS
from gtd_backend.rf07 import InMemoryPasswordResetEmailSender, RF07Service


def _buildService(
    now: datetime | None = None,
) -> tuple[RF07Service, AuthService, InMemoryPasswordResetEmailSender]:
    authService = AuthService()
    emailSender = InMemoryPasswordResetEmailSender()
    fixedNow = now if now is not None else datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    service = RF07Service(
        authService=authService,
        emailSender=emailSender,
        nowProvider=lambda: fixedNow,
    )
    return service, authService, emailSender


def test_rf07_deve_criar_schema_com_indices_minimos() -> None:
    service, _, _ = _buildService()

    tableRow = service.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'password_reset_tokens'"
    ).fetchone()
    tokenHashIndex = service.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_password_reset_tokens_token_hash'"
    ).fetchone()
    userIdIndex = service.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_password_reset_tokens_user_id'"
    ).fetchone()

    assert tableRow is not None
    assert tokenHashIndex is not None
    assert userIdIndex is not None


def test_rf07_request_password_reset_deve_ser_cego_para_usuario_inexistente() -> None:
    service, _, emailSender = _buildService()

    service.requestPasswordReset("inexistente@unioeste.br")

    totalTokens = service.connection.execute(
        "SELECT COUNT(*) AS total FROM password_reset_tokens"
    ).fetchone()
    assert int(totalTokens["total"]) == 0
    assert emailSender.queuedMessages == []


def test_rf07_request_password_reset_deve_persistir_apenas_hash_e_enviar_email_quando_usuario_existe() -> None:
    fixedNow = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    service, authService, emailSender = _buildService(now=fixedNow)
    userId = authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("  ALUNA@unioeste.br ")

    assert len(emailSender.queuedMessages) == 1
    sent = emailSender.queuedMessages[0]
    assert sent["toEmail"] == "aluna@unioeste.br"
    assert "senha" not in str(sent).lower()

    row = service.connection.execute(
        """
        SELECT user_id, token_hash, expires_at, used_at, created_at
        FROM password_reset_tokens
        """
    ).fetchone()

    assert row is not None
    assert int(row["user_id"]) == userId
    assert str(row["token_hash"]) == hashlib.sha256(sent["resetToken"].encode("utf-8")).hexdigest()
    assert row["used_at"] is None
    assert datetime.fromisoformat(str(row["created_at"])) == fixedNow
    assert datetime.fromisoformat(str(row["expires_at"])) == fixedNow + timedelta(hours=1)


def test_rf07_confirm_password_reset_deve_rejeitar_token_invalido_com_mensagem_generica() -> None:
    service, _, _ = _buildService()

    try:
        service.confirmPasswordReset("token-inexistente-super-seguro", "NovaSenha123")
        assert False, "esperava erro para token inválido"
    except ValueError as error:
        assert str(error) == CREDENCIAIS_INVALIDAS


def test_rf07_confirm_password_reset_deve_rejeitar_token_expirado_ou_ja_usado() -> None:
    fixedNow = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    service, authService, emailSender = _buildService(now=fixedNow)
    authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("aluna@unioeste.br")
    firstToken = emailSender.queuedMessages[0]["resetToken"]

    service.nowProvider = lambda: fixedNow + timedelta(hours=2)

    try:
        service.confirmPasswordReset(firstToken, "NovaSenha123")
        assert False, "esperava erro para token expirado"
    except ValueError as error:
        assert str(error) == CREDENCIAIS_INVALIDAS

    service.nowProvider = lambda: fixedNow
    service.requestPasswordReset("aluna@unioeste.br")
    secondToken = emailSender.queuedMessages[1]["resetToken"]

    service.confirmPasswordReset(secondToken, "NovaSenhaForte123")

    try:
        service.confirmPasswordReset(secondToken, "OutraSenha123")
        assert False, "esperava erro para token já usado"
    except ValueError as error:
        assert str(error) == CREDENCIAIS_INVALIDAS


def test_rf07_confirm_password_reset_deve_atualizar_senha_com_argon2id_e_marcar_token_como_usado() -> None:
    fixedNow = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    service, authService, emailSender = _buildService(now=fixedNow)
    authService.register_user("aluna@unioeste.br", "SenhaAntiga123")

    service.requestPasswordReset("aluna@unioeste.br")
    token = emailSender.queuedMessages[0]["resetToken"]

    service.confirmPasswordReset(token, "NovaSenhaForte123")

    loginAntigo = authService.login("aluna@unioeste.br", "SenhaAntiga123")
    loginNovo = authService.login("aluna@unioeste.br", "NovaSenhaForte123")

    row = service.connection.execute(
        "SELECT used_at, token_hash FROM password_reset_tokens"
    ).fetchone()

    assert loginAntigo.success is False
    assert loginNovo.success is True
    assert str(authService.get_password_hash(1)).startswith("$argon2id$")
    assert datetime.fromisoformat(str(row["used_at"])) == fixedNow
    assert str(row["token_hash"]) != token
