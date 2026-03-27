from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from gtd_backend.http import createApp


def _autenticarUsuario(client: TestClient, app, email: str) -> dict[str, str]:
    try:
        app.state.authService.register_user(email, "SenhaForte123")
    except (ValueError, sqlite3.IntegrityError):
        pass
    respostaLogin = client.post(
        "/auth/login",
        json={"email": email, "password": "SenhaForte123"},
    )
    token = respostaLogin.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_create_app_deve_persistir_dados_em_sqlite_compartilhado_entre_instancias(tmp_path: Path) -> None:
    databaseFile = tmp_path / "gtd-shared.db"
    databaseUrl = f"sqlite:///{databaseFile}"

    appPrimeiraInstancia = createApp(databaseUrl=databaseUrl)
    clientPrimeiraInstancia = TestClient(appPrimeiraInstancia)
    headersPrimeiraInstancia = _autenticarUsuario(
        client=clientPrimeiraInstancia,
        app=appPrimeiraInstancia,
        email="aluna@unioeste.br",
    )
    respostaCriacao = clientPrimeiraInstancia.post(
        "/rf01/professors",
        json={"name": "Professora Ana", "email": "ana@unioeste.br"},
        headers=headersPrimeiraInstancia,
    )
    assert respostaCriacao.status_code == 201

    appSegundaInstancia = createApp(databaseUrl=databaseUrl)
    clientSegundaInstancia = TestClient(appSegundaInstancia)
    headersSegundaInstancia = _autenticarUsuario(
        client=clientSegundaInstancia,
        app=appSegundaInstancia,
        email="aluna@unioeste.br",
    )
    respostaListagem = clientSegundaInstancia.get("/rf01/professors", headers=headersSegundaInstancia)

    assert respostaListagem.status_code == 200
    assert respostaListagem.json() == [
        {"id": 1, "name": "Professora Ana", "email": "ana@unioeste.br"}
    ]
