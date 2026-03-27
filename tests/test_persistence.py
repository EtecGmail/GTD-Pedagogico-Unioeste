from pathlib import Path

from fastapi.testclient import TestClient

from gtd_backend.http import createApp


def test_create_app_deve_persistir_dados_em_sqlite_compartilhado_entre_instancias(tmp_path: Path) -> None:
    databaseFile = tmp_path / "gtd-shared.db"
    databaseUrl = f"sqlite:///{databaseFile}"

    appPrimeiraInstancia = createApp(databaseUrl=databaseUrl)
    clientPrimeiraInstancia = TestClient(appPrimeiraInstancia)
    respostaCriacao = clientPrimeiraInstancia.post(
        "/rf01/professors",
        json={"name": "Professora Ana", "email": "ana@unioeste.br"},
    )
    assert respostaCriacao.status_code == 201

    appSegundaInstancia = createApp(databaseUrl=databaseUrl)
    clientSegundaInstancia = TestClient(appSegundaInstancia)
    respostaListagem = clientSegundaInstancia.get("/rf01/professors")

    assert respostaListagem.status_code == 200
    assert respostaListagem.json() == [
        {"id": 1, "name": "Professora Ana", "email": "ana@unioeste.br"}
    ]
