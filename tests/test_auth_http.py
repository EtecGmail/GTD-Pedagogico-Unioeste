import logging

from fastapi.testclient import TestClient

from gtd_backend.auth import CREDENCIAIS_INVALIDAS
from gtd_backend.http import MemoryRateLimiter, createApp


def test_rate_limiter_em_memoria_deve_bloquear_apos_limite_na_janela() -> None:
    rateLimiter = MemoryRateLimiter(maxAttempts=2, windowSeconds=60)

    permitidoPrimeira = rateLimiter.allow(key="ip:127.0.0.1|email:hash1", now=10)
    permitidoSegunda = rateLimiter.allow(key="ip:127.0.0.1|email:hash1", now=20)
    permitidoTerceira = rateLimiter.allow(key="ip:127.0.0.1|email:hash1", now=30)

    assert permitidoPrimeira is True
    assert permitidoSegunda is True
    assert permitidoTerceira is False


def test_rate_limiter_em_memoria_deve_resetar_contador_apos_janela() -> None:
    rateLimiter = MemoryRateLimiter(maxAttempts=1, windowSeconds=10)

    assert rateLimiter.allow(key="ip:127.0.0.1|email:hash1", now=100) is True
    assert rateLimiter.allow(key="ip:127.0.0.1|email:hash1", now=105) is False
    assert rateLimiter.allow(key="ip:127.0.0.1|email:hash1", now=111) is True


def test_login_http_deve_retornar_429_quando_rate_limit_excedido() -> None:
    app = createApp()
    client = TestClient(app)

    for _ in range(5):
        resposta = client.post(
            "/auth/login",
            json={"email": "naoexiste@unioeste.br", "password": "SenhaQualquer123"},
        )
        assert resposta.status_code == 401

    respostaBloqueio = client.post(
        "/auth/login",
        json={"email": "naoexiste@unioeste.br", "password": "SenhaQualquer123"},
    )

    assert respostaBloqueio.status_code == 429
    assert respostaBloqueio.json() == {
        "success": False,
        "message": "muitas tentativas; tente novamente mais tarde",
    }


def test_login_http_deve_retornar_mesma_resposta_para_usuario_inexistente_e_senha_incorreta() -> None:
    app = createApp()
    client = TestClient(app)

    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    respostaUsuarioInexistente = client.post(
        "/auth/login",
        json={"email": "naoexiste@unioeste.br", "password": "SenhaQualquer123"},
    )
    respostaSenhaIncorreta = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "senha-invalida"},
    )

    assert respostaUsuarioInexistente.status_code == 401
    assert respostaSenhaIncorreta.status_code == 401
    assert respostaUsuarioInexistente.json() == respostaSenhaIncorreta.json() == {
        "success": False,
        "message": CREDENCIAIS_INVALIDAS,
    }


def test_login_http_deve_retornar_sucesso_para_credenciais_validas() -> None:
    app = createApp()
    client = TestClient(app)

    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    resposta = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "success": True,
        "message": "login realizado com sucesso",
    }


def test_login_http_deve_validar_entradas_invalidas() -> None:
    app = createApp()
    client = TestClient(app)

    resposta = client.post(
        "/auth/login",
        json={"email": "invalido", "password": ""},
    )

    assert resposta.status_code == 422
    corpoResposta = resposta.json()
    assert "detail" in corpoResposta


def test_login_http_deve_logar_eventos_sem_dados_sensiveis(caplog) -> None:
    app = createApp()
    client = TestClient(app)

    caplog.set_level(logging.INFO)

    client.post(
        "/auth/login",
        json={"email": "naoexiste@unioeste.br", "password": "SenhaSuperSecreta"},
    )

    mensagens = " ".join(registro.getMessage() for registro in caplog.records)
    assert "evento=auth_login_fail" in mensagens
    assert "SenhaSuperSecreta" not in mensagens
    assert "naoexiste@unioeste.br" not in mensagens


def test_rf07_request_http_deve_enfileirar_email_apenas_quando_conta_existe() -> None:
    app = createApp()
    client = TestClient(app)

    respostaSemConta = client.post(
        "/rf07/password-reset/request",
        json={"email": "inexistente@unioeste.br"},
    )
    assert respostaSemConta.status_code == 200
    assert app.state.rf07EmailSender.queuedMessages == []

    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    respostaComConta = client.post(
        "/rf07/password-reset/request",
        json={"email": "aluna@unioeste.br"},
    )
    assert respostaComConta.status_code == 200
    assert len(app.state.rf07EmailSender.queuedMessages) == 1


def test_rf07_request_http_nao_deve_expor_token_na_resposta() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    resposta = client.post(
        "/rf07/password-reset/request",
        json={"email": "aluna@unioeste.br"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo == {
        "success": True,
        "message": "se a conta existir, enviaremos instruções por e-mail",
    }
    assert "token" not in str(corpo).lower()


def test_rf07_request_http_nao_deve_logar_senha_ou_token(caplog) -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    caplog.set_level(logging.INFO)
    client.post("/rf07/password-reset/request", json={"email": "aluna@unioeste.br"})

    mensagens = " ".join(registro.getMessage() for registro in caplog.records)
    token = app.state.rf07EmailSender.queuedMessages[0]["resetToken"]
    assert "evento=rf07_password_reset_requested" in mensagens
    assert "SenhaForte123" not in mensagens
    assert token not in mensagens
    assert "aluna@unioeste.br" not in mensagens
