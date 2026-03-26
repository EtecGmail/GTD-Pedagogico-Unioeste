from fastapi.testclient import TestClient

from gtd_backend.auth import CREDENCIAIS_INVALIDAS
from gtd_backend.http import createApp


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
