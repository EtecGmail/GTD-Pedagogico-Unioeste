from __future__ import annotations

import os
from base64 import b64encode
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.persistence import applyMigrations, createDatabaseConnection


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.skipif(
    not os.environ.get("POSTGRES_STAGING_DATABASE_URL"),
    reason="POSTGRES_STAGING_DATABASE_URL não configurada para teste real",
)
def test_smoke_staging_postgresql_real() -> None:
    databaseUrl = os.environ["POSTGRES_STAGING_DATABASE_URL"]

    connection = createDatabaseConnection(
        databaseUrl=databaseUrl,
        environmentName="production",
    )
    applyMigrations(connection=connection, databaseUrl=databaseUrl)
    applyMigrations(connection=connection, databaseUrl=databaseUrl)

    app = createApp(databaseUrl=databaseUrl, environmentName="production")
    client = TestClient(app)

    sufixo = uuid4().hex[:8]
    alunoEmail = f"aluno.staging.{sufixo}@unioeste.br"
    adminEmail = f"admin.staging.{sufixo}@unioeste.br"
    senha = "SenhaForte123"

    app.state.authService.register_user(alunoEmail, senha, role="aluno")
    app.state.authService.register_user(adminEmail, senha, role="admin")

    loginAluno = client.post("/auth/login", json={"email": alunoEmail, "password": senha})
    assert loginAluno.status_code == 200
    assert loginAluno.json()["role"] == "aluno"
    alunoHeaders = {"Authorization": f"Bearer {loginAluno.json()['accessToken']}"}

    loginAdmin = client.post("/auth/login", json={"email": adminEmail, "password": senha})
    assert loginAdmin.status_code == 200
    assert loginAdmin.json()["role"] == "admin"
    adminHeaders = {"Authorization": f"Bearer {loginAdmin.json()['accessToken']}"}

    respostaRf09Aluno = client.get("/rf09/security-events", headers=alunoHeaders)
    assert respostaRf09Aluno.status_code == 403
    respostaRf09Admin = client.get("/rf09/security-events", headers=adminHeaders)
    assert respostaRf09Admin.status_code == 200

    inboxCriado = client.post(
        "/rf02/inbox-items",
        json={"content": f"Revisar leitura {sufixo}"},
        headers=alunoHeaders,
    )
    assert inboxCriado.status_code == 201
    itemId = int(inboxCriado.json()["id"])

    rf06Atualizado = client.patch(
        f"/rf06/inbox-items/{itemId}/status",
        json={"status": "next_action"},
        headers=alunoHeaders,
    )
    assert rf06Atualizado.status_code == 200

    planoCriado = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 120, "deadlineDays": 10},
        headers=alunoHeaders,
    )
    assert planoCriado.status_code == 201
    planId = int(planoCriado.json()["id"])

    rf08Avanco = client.patch(
        f"/rf08/reading-plans/{planId}/advance",
        json={"pagesRead": 15},
        headers=alunoHeaders,
    )
    assert rf08Avanco.status_code == 200

    pdfMinimo = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    certificado = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado-staging.pdf",
            "contentType": "application/pdf",
            "contentBase64": b64encode(pdfMinimo).decode("utf-8"),
            "hours": 12,
        },
        headers=alunoHeaders,
    )
    assert certificado.status_code == 201

    progresso = client.get("/rf05/acc-progress?targetHours=200", headers=alunoHeaders)
    assert progresso.status_code == 200
    assert progresso.json()["totalHours"] >= 12

    dashboard = client.get("/rf08/dashboard", headers=alunoHeaders)
    assert dashboard.status_code == 200

    recuperacao = client.post(
        "/auth/password-reset/request",
        json={"email": alunoEmail},
    )
    assert recuperacao.status_code == 200

    usoStorage = client.get("/rf10/storage-usage", headers=alunoHeaders)
    assert usoStorage.status_code == 200

    logout = client.post("/auth/logout", headers=alunoHeaders)
    assert logout.status_code == 200

    aposLogout = client.get("/rf02/inbox-items", headers=alunoHeaders)
    assert aposLogout.status_code == 401
