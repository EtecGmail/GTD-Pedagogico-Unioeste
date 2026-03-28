from base64 import b64encode

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf02 import RF02Service
from gtd_backend.rf03 import RF03Service
from gtd_backend.rf04 import InMemoryCertificateStorage, RF04Service
from gtd_backend.rf05 import RF05Service
from gtd_backend.rf06 import RF06Service
from gtd_backend.rf08 import RF08Service


def _toBase64(content: bytes) -> str:
    return b64encode(content).decode("utf-8")

def _fakePdfContent(size: int = 32) -> bytes:
    if size < 5:
        size = 5
    return b"%PDF-" + (b"x" * (size - 5))


def _autenticarUsuario(client: TestClient, app, email: str) -> dict[str, str]:
    app.state.authService.register_user(email, "SenhaForte123")
    respostaLogin = client.post(
        "/auth/login",
        json={"email": email, "password": "SenhaForte123"},
    )
    token = respostaLogin.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_rf08_service_deve_agregar_metricas_minimas_do_dashboard() -> None:
    rf02Service = RF02Service()
    rf03Service = RF03Service()
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf05Service = RF05Service(rf04Service=rf04Service, defaultTargetHours=200)
    rf06Service = RF06Service(rf02Service=rf02Service)

    inboxId = rf02Service.captureInboxItem(content="Revisar plano de aula", userId=1)
    nextActionId = rf02Service.captureInboxItem(content="Preparar seminário", userId=1)
    waitingId = rf02Service.captureInboxItem(content="Aguardar feedback", userId=1)
    rf06Service.changeInboxItemStatus(itemId=nextActionId, targetStatus="next_action", userId=1)
    rf06Service.changeInboxItemStatus(itemId=waitingId, targetStatus="waiting", userId=1)

    readingPlanId = rf03Service.createReadingPlan(totalPages=120, deadlineDays=10, userId=1)
    rf03Service.advanceReadingPlan(planId=readingPlanId, pagesRead=30, userId=1)

    rf04Service.uploadCertificate(
        originalName="acc.pdf",
        contentType="application/pdf",
        content=_fakePdfContent(30),
        hours=40,
        userId=1,
    )

    rf08Service = RF08Service(
        rf03Service=rf03Service,
        rf05Service=rf05Service,
        rf06Service=rf06Service,
    )

    dashboard = rf08Service.getStudentDashboard(userId=1)

    assert dashboard["statusCounts"] == {
        "inbox": 1,
        "nextAction": 1,
        "waiting": 1,
    }
    assert dashboard["accProgress"] == {
        "totalHours": 40,
        "targetHours": 200,
        "remainingHours": 160,
        "percentage": 20.0,
        "isCompleted": False,
    }
    assert dashboard["readingSummary"] == {
        "totalPlans": 1,
        "overloadedPlans": 0,
        "completedPlans": 0,
        "totalPages": 120,
        "remainingPages": 90,
        "averageCompletionPercentage": 25.0,
    }
    assert inboxId > 0


def test_rf08_service_deve_responder_com_zeros_quando_nao_houver_dados() -> None:
    rf08Service = RF08Service(
        rf03Service=RF03Service(),
        rf05Service=RF05Service(
            rf04Service=RF04Service(storage=InMemoryCertificateStorage()),
            defaultTargetHours=200,
        ),
        rf06Service=RF06Service(rf02Service=RF02Service()),
    )

    dashboard = rf08Service.getStudentDashboard(userId=1)

    assert dashboard["statusCounts"] == {
        "inbox": 0,
        "nextAction": 0,
        "waiting": 0,
    }
    assert dashboard["accProgress"] == {
        "totalHours": 0,
        "targetHours": 200,
        "remainingHours": 200,
        "percentage": 0.0,
        "isCompleted": False,
    }
    assert dashboard["readingSummary"] == {
        "totalPlans": 0,
        "overloadedPlans": 0,
        "completedPlans": 0,
        "totalPages": 0,
        "remainingPages": 0,
        "averageCompletionPercentage": 0.0,
    }


def test_rf08_http_deve_expor_dashboard_e_endpoint_de_avanco_de_leitura() -> None:
    app = createApp()
    client = TestClient(app)
    headers = _autenticarUsuario(client=client, app=app, email="aluna@unioeste.br")

    inboxId = client.post(
        "/rf02/inbox-items",
        json={"content": "Organizar referências"},
        headers=headers,
    ).json()["id"]
    nextActionId = client.post(
        "/rf02/inbox-items",
        json={"content": "Ler capítulo 2"},
        headers=headers,
    ).json()["id"]
    waitingId = client.post(
        "/rf02/inbox-items",
        json={"content": "Aguardar retorno docente"},
        headers=headers,
    ).json()["id"]

    client.patch(
        f"/rf06/inbox-items/{nextActionId}/status",
        json={"status": "next_action"},
        headers=headers,
    )
    client.patch(
        f"/rf06/inbox-items/{waitingId}/status",
        json={"status": "waiting"},
        headers=headers,
    )

    createPlanResponse = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 80, "deadlineDays": 8},
        headers=headers,
    )
    planId = createPlanResponse.json()["id"]

    advanceResponse = client.patch(
        f"/rf08/reading-plans/{planId}/advance",
        json={"pagesRead": 20},
        headers=headers,
    )
    assert advanceResponse.status_code == 200
    assert advanceResponse.json() == {
        "id": planId,
        "remainingPages": 60,
        "isCompleted": False,
    }

    certificateResponse = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(_fakePdfContent(28)),
            "hours": 30,
        },
        headers=headers,
    )
    assert certificateResponse.status_code == 201

    dashboardResponse = client.get("/rf08/dashboard", headers=headers)
    assert dashboardResponse.status_code == 200
    assert dashboardResponse.json() == {
        "statusCounts": {
            "inbox": 1,
            "nextAction": 1,
            "waiting": 1,
        },
        "accProgress": {
            "totalHours": 30,
            "targetHours": 200,
            "remainingHours": 170,
            "percentage": 15.0,
            "isCompleted": False,
        },
        "readingSummary": {
            "totalPlans": 1,
            "overloadedPlans": 0,
            "completedPlans": 0,
            "totalPages": 80,
            "remainingPages": 60,
            "averageCompletionPercentage": 25.0,
        },
    }
    assert inboxId > 0


def test_rf08_http_deve_validar_payload_de_avanco_e_rejeitar_plano_inexistente() -> None:
    app = createApp()
    client = TestClient(app)
    headers = _autenticarUsuario(client=client, app=app, email="aluna@unioeste.br")

    responsePlanoInexistente = client.patch(
        "/rf08/reading-plans/999/advance",
        json={"pagesRead": 5},
        headers=headers,
    )
    assert responsePlanoInexistente.status_code == 404
    assert responsePlanoInexistente.json() == {
        "success": False,
        "message": "plano de leitura não encontrado",
    }

    createPlanResponse = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 40, "deadlineDays": 4},
        headers=headers,
    )
    planId = createPlanResponse.json()["id"]

    payloadInvalido = client.patch(
        f"/rf08/reading-plans/{planId}/advance",
        json={"pagesRead": 0, "extra": True},
        headers=headers,
    )
    payloadIncompleto = client.patch(
        f"/rf08/reading-plans/{planId}/advance",
        json={},
        headers=headers,
    )

    assert payloadInvalido.status_code == 422
    assert payloadIncompleto.status_code == 422


def test_rf08_http_deve_rejeitar_sem_autenticacao_e_isolar_dashboard_por_usuario() -> None:
    app = createApp()
    client = TestClient(app)
    headersUserA = _autenticarUsuario(client=client, app=app, email="a@unioeste.br")
    headersUserB = _autenticarUsuario(client=client, app=app, email="b@unioeste.br")

    semTokenDashboard = client.get("/rf08/dashboard")
    assert semTokenDashboard.status_code == 401

    planoA = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 50, "deadlineDays": 5},
        headers=headersUserA,
    ).json()["id"]
    client.patch(
        f"/rf08/reading-plans/{planoA}/advance",
        json={"pagesRead": 10},
        headers=headersUserA,
    )
    client.post(
        "/rf04/certificates",
        json={
            "originalName": "a.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(_fakePdfContent(26)),
            "hours": 12,
        },
        headers=headersUserA,
    )
    client.post(
        "/rf02/inbox-items",
        json={"content": "Item da usuária A"},
        headers=headersUserA,
    )

    client.post(
        "/rf03/reading-plans",
        json={"totalPages": 30, "deadlineDays": 3},
        headers=headersUserB,
    )
    client.post(
        "/rf04/certificates",
        json={
            "originalName": "b.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(_fakePdfContent(27)),
            "hours": 5,
        },
        headers=headersUserB,
    )

    dashboardA = client.get("/rf08/dashboard", headers=headersUserA)
    dashboardB = client.get("/rf08/dashboard", headers=headersUserB)
    assert dashboardA.status_code == 200
    assert dashboardB.status_code == 200
    assert dashboardA.json()["accProgress"]["totalHours"] == 12
    assert dashboardB.json()["accProgress"]["totalHours"] == 5

    tentativaCruzarOwnership = client.patch(
        f"/rf08/reading-plans/{planoA}/advance",
        json={"pagesRead": 2},
        headers=headersUserB,
    )
    assert tentativaCruzarOwnership.status_code == 404
    assert tentativaCruzarOwnership.json() == {
        "success": False,
        "message": "plano de leitura não encontrado",
    }
