from fastapi.testclient import TestClient

from gtd_backend.auth import CREDENCIAIS_INVALIDAS
from gtd_backend.http import createApp


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["accessToken"])


def test_rf09_deve_registrar_login_com_sucesso() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    response = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    )

    assert response.status_code == 200
    events = app.state.rf09Service.listEvents(limit=10)
    assert events[0]["eventType"] == "auth_login"
    assert events[0]["result"] == "success"
    assert events[0]["userId"] is not None


def test_rf09_deve_registrar_login_invalido_sem_vazar_dados_sensiveis() -> None:
    app = createApp()
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"email": "naoexiste@unioeste.br", "password": "SenhaSuperSecreta"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == CREDENCIAIS_INVALIDAS

    events = app.state.rf09Service.listEvents(limit=10)
    event = events[0]
    assert event["eventType"] == "auth_login"
    assert event["result"] == "failure"
    eventDump = str(event)
    assert "SenhaSuperSecreta" not in eventDump
    assert "naoexiste@unioeste.br" not in eventDump


def test_rf09_deve_registrar_bloqueio_por_rate_limit() -> None:
    app = createApp()
    client = TestClient(app)

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": "naoexiste@unioeste.br", "password": "SenhaQualquer123"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        json={"email": "naoexiste@unioeste.br", "password": "SenhaQualquer123"},
    )

    assert blocked.status_code == 429
    events = app.state.rf09Service.listEvents(limit=30)
    assert any(
        event["eventType"] == "auth_login_rate_limit" and event["result"] == "blocked"
        for event in events
    )


def test_rf09_deve_registrar_solicitacao_e_confirmacao_de_reset() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")

    requestResponse = client.post(
        "/auth/password-reset/request",
        json={"email": "aluna@unioeste.br"},
    )
    assert requestResponse.status_code == 200

    token = app.state.rf07EmailSender.queuedMessages[0]["resetToken"]
    confirmResponse = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "newPassword": "SenhaNovaForte123"},
    )
    assert confirmResponse.status_code == 200

    events = app.state.rf09Service.listEvents(limit=20)
    assert any(event["eventType"] == "password_reset_request" and event["result"] == "success" for event in events)
    assert any(event["eventType"] == "password_reset_confirm" and event["result"] == "success" for event in events)


def test_rf09_deve_registrar_acesso_negado_por_ownership() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("a1@unioeste.br", "SenhaForte123")
    app.state.authService.register_user("a2@unioeste.br", "SenhaForte123")

    token1 = _login(client, "a1@unioeste.br", "SenhaForte123")
    token2 = _login(client, "a2@unioeste.br", "SenhaForte123")

    created = client.post(
        "/rf02/inbox-items",
        json={"content": "Revisar capítulo 3"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert created.status_code == 201
    itemId = created.json()["id"]

    denied = client.patch(
        f"/rf06/inbox-items/{itemId}/status",
        json={"status": "next_action"},
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert denied.status_code == 404
    events = app.state.rf09Service.listEvents(limit=20)
    assert any(event["eventType"] == "authorization_denied" and event["result"] == "denied" for event in events)


def test_rf09_deve_registrar_upload_invalido_sem_vazar_content_base64() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    token = _login(client, "aluna@unioeste.br", "SenhaForte123")

    response = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.exe",
            "contentType": "application/octet-stream",
            "contentBase64": "QUJDRA==",
            "hours": 10,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    events = app.state.rf09Service.listEvents(limit=20)
    event = next(event for event in events if event["eventType"] == "certificate_upload_rejected")
    assert event["result"] == "rejected"
    assert "QUJDRA==" not in str(event)


def test_rf09_endpoint_admin_deve_exigir_role_admin() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123", role="aluno")
    app.state.authService.register_user("admin@unioeste.br", "SenhaForte123", role="admin")

    tokenAluno = _login(client, "aluna@unioeste.br", "SenhaForte123")
    tokenAdmin = _login(client, "admin@unioeste.br", "SenhaForte123")

    denied = client.get(
        "/rf09/security-events",
        headers={"Authorization": f"Bearer {tokenAluno}"},
    )
    assert denied.status_code == 403
    assert denied.json() == {"detail": "acesso negado"}

    allowed = client.get(
        "/rf09/security-events?limit=5",
        headers={"Authorization": f"Bearer {tokenAdmin}"},
    )
    assert allowed.status_code == 200
    assert isinstance(allowed.json(), list)
