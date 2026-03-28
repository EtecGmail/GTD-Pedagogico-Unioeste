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
    corpoResposta = resposta.json()
    assert corpoResposta["success"] is True
    assert corpoResposta["message"] == "login realizado com sucesso"
    assert isinstance(corpoResposta["accessToken"], str)
    assert len(corpoResposta["accessToken"]) >= 20
    assert corpoResposta["tokenType"] == "Bearer"
    assert corpoResposta["role"] == "aluno"


def test_login_http_deve_retornar_role_admin_para_usuario_admin() -> None:
    app = createApp()
    client = TestClient(app)

    app.state.authService.register_user("admin@unioeste.br", "SenhaForte123", role="admin")

    resposta = client.post(
        "/auth/login",
        json={"email": "admin@unioeste.br", "password": "SenhaForte123"},
    )

    assert resposta.status_code == 200
    corpoResposta = resposta.json()
    assert corpoResposta["success"] is True
    assert corpoResposta["role"] == "admin"


def test_login_http_deve_emitir_credencial_que_autentica_requisicao_protegida() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    respostaLogin = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    )
    token = respostaLogin.json()["accessToken"]

    respostaCaptura = client.post(
        "/rf02/inbox-items",
        json={"content": "Ler artigo de alfabetização"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respostaCaptura.status_code == 201

    respostaListagem = client.get(
        "/rf02/inbox-items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respostaListagem.status_code == 200
    assert len(respostaListagem.json()) == 1


def test_rf02_http_deve_rejeitar_requisicao_sem_autenticacao() -> None:
    app = createApp()
    client = TestClient(app)

    respostaSemToken = client.get("/rf02/inbox-items")
    assert respostaSemToken.status_code == 401
    assert respostaSemToken.json() == {"detail": "não autenticado"}


def test_rf09_http_deve_restringir_endpoint_admin_para_papel_admin() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123", role="aluno")
    app.state.authService.register_user("admin@unioeste.br", "SenhaForte123", role="admin")

    tokenAluno = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    tokenAdmin = client.post(
        "/auth/login",
        json={"email": "admin@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]

    respostaAluno = client.get(
        "/rf09/security-events",
        headers={"Authorization": f"Bearer {tokenAluno}"},
    )
    assert respostaAluno.status_code == 403
    assert respostaAluno.json() == {"detail": "acesso negado"}

    respostaAdmin = client.get(
        "/rf09/security-events",
        headers={"Authorization": f"Bearer {tokenAdmin}"},
    )
    assert respostaAdmin.status_code == 200
    assert isinstance(respostaAdmin.json(), list)


def test_get_current_user_deve_rejeitar_role_ausente_ou_invalido_na_sessao() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("admin@unioeste.br", "SenhaForte123", role="admin")
    token = client.post(
        "/auth/login",
        json={"email": "admin@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]

    app.state.sessionStore._tokenToUser["token-invalido"] = {"userId": 1, "role": "gestor"}  # type: ignore[attr-defined]
    respostaRoleInvalido = client.get(
        "/rf02/inbox-items",
        headers={"Authorization": "Bearer token-invalido"},
    )
    assert respostaRoleInvalido.status_code == 401
    assert respostaRoleInvalido.json() == {"detail": "não autenticado"}

    app.state.sessionStore._tokenToUser[token] = {"userId": 1, "role": ""}  # type: ignore[attr-defined]
    respostaRoleAusente = client.get(
        "/rf02/inbox-items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respostaRoleAusente.status_code == 401
    assert respostaRoleAusente.json() == {"detail": "não autenticado"}


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


def test_auth_password_reset_request_http_deve_enfileirar_email_apenas_quando_conta_existe() -> None:
    app = createApp()
    client = TestClient(app)

    respostaSemConta = client.post(
        "/auth/password-reset/request",
        json={"email": "inexistente@unioeste.br"},
    )
    assert respostaSemConta.status_code == 200
    assert app.state.rf07EmailSender.queuedMessages == []

    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    respostaComConta = client.post(
        "/auth/password-reset/request",
        json={"email": "aluna@unioeste.br"},
    )
    assert respostaComConta.status_code == 200
    assert len(app.state.rf07EmailSender.queuedMessages) == 1


def test_auth_password_reset_request_http_nao_deve_expor_token_na_resposta() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    resposta = client.post(
        "/auth/password-reset/request",
        json={"email": "aluna@unioeste.br"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo == {
        "success": True,
        "message": "se a conta existir, enviaremos instruções por e-mail",
    }
    assert "token" not in str(corpo).lower()


def test_auth_password_reset_request_http_deve_aplicar_rate_limit() -> None:
    app = createApp()
    client = TestClient(app)

    for _ in range(5):
        resposta = client.post(
            "/auth/password-reset/request",
            json={"email": "naoexiste@unioeste.br"},
        )
        assert resposta.status_code == 200

    respostaBloqueio = client.post(
        "/auth/password-reset/request",
        json={"email": "naoexiste@unioeste.br"},
    )

    assert respostaBloqueio.status_code == 429
    assert respostaBloqueio.json() == {
        "success": False,
        "message": "muitas tentativas; tente novamente mais tarde",
    }


def test_auth_password_reset_request_http_nao_deve_logar_senha_ou_token_ou_email_bruto(caplog) -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    caplog.set_level(logging.INFO)
    client.post("/auth/password-reset/request", json={"email": "aluna@unioeste.br"})

    mensagens = " ".join(registro.getMessage() for registro in caplog.records)
    token = app.state.rf07EmailSender.queuedMessages[0]["resetToken"]
    assert "evento=rf07_password_reset_requested" in mensagens
    assert "SenhaForte123" not in mensagens
    assert token not in mensagens
    assert "aluna@unioeste.br" not in mensagens


def test_auth_password_reset_confirm_http_deve_retornar_sucesso_quando_token_for_valido() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    client.post("/auth/password-reset/request", json={"email": "aluna@unioeste.br"})
    token = app.state.rf07EmailSender.queuedMessages[0]["resetToken"]

    resposta = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "newPassword": "SenhaNovaForte123"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "success": True,
        "message": "senha redefinida com sucesso",
    }


def test_auth_password_reset_confirm_http_deve_retornar_400_generico_para_token_invalido_expirado_ou_usado() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    respostaInvalido = client.post(
        "/auth/password-reset/confirm",
        json={"token": "token-inexistente-super-seguro", "newPassword": "SenhaNovaForte123"},
    )
    assert respostaInvalido.status_code == 400
    assert respostaInvalido.json() == {"success": False, "message": CREDENCIAIS_INVALIDAS}

    client.post("/auth/password-reset/request", json={"email": "aluna@unioeste.br"})
    tokenValido = app.state.rf07EmailSender.queuedMessages[0]["resetToken"]

    respostaPrimeiroUso = client.post(
        "/auth/password-reset/confirm",
        json={"token": tokenValido, "newPassword": "SenhaNovaForte123"},
    )
    assert respostaPrimeiroUso.status_code == 200

    respostaTokenUsado = client.post(
        "/auth/password-reset/confirm",
        json={"token": tokenValido, "newPassword": "SenhaMaisNova123"},
    )
    assert respostaTokenUsado.status_code == 400
    assert respostaTokenUsado.json() == {"success": False, "message": CREDENCIAIS_INVALIDAS}


def test_auth_password_reset_endpoints_devem_rejeitar_campos_extras() -> None:
    app = createApp()
    client = TestClient(app)

    respostaRequestComExtra = client.post(
        "/auth/password-reset/request",
        json={"email": "aluna@unioeste.br", "extra": "indevido"},
    )
    respostaConfirmComExtra = client.post(
        "/auth/password-reset/confirm",
        json={
            "token": "token-inexistente-super-seguro",
            "newPassword": "SenhaNovaForte123",
            "extra": "indevido",
        },
    )

    assert respostaRequestComExtra.status_code == 422
    assert respostaConfirmComExtra.status_code == 422
