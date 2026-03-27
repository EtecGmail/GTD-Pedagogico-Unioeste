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


def test_rf08_service_deve_agregar_metricas_minimas_do_dashboard() -> None:
    rf02Service = RF02Service()
    rf03Service = RF03Service()
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf05Service = RF05Service(rf04Service=rf04Service, defaultTargetHours=200)
    rf06Service = RF06Service(rf02Service=rf02Service)

    inboxId = rf02Service.captureInboxItem(content="Revisar plano de aula")
    nextActionId = rf02Service.captureInboxItem(content="Preparar seminário")
    waitingId = rf02Service.captureInboxItem(content="Aguardar feedback")
    rf06Service.changeInboxItemStatus(itemId=nextActionId, targetStatus="next_action")
    rf06Service.changeInboxItemStatus(itemId=waitingId, targetStatus="waiting")

    readingPlanId = rf03Service.createReadingPlan(totalPages=120, deadlineDays=10)
    rf03Service.advanceReadingPlan(planId=readingPlanId, pagesRead=30)

    rf04Service.uploadCertificate(
        originalName="acc.pdf",
        contentType="application/pdf",
        content=b"acc-content",
        hours=40,
    )

    rf08Service = RF08Service(
        rf03Service=rf03Service,
        rf05Service=rf05Service,
        rf06Service=rf06Service,
    )

    dashboard = rf08Service.getStudentDashboard()

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

    dashboard = rf08Service.getStudentDashboard()

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

    inboxId = client.post("/rf02/inbox-items", json={"content": "Organizar referências"}).json()["id"]
    nextActionId = client.post("/rf02/inbox-items", json={"content": "Ler capítulo 2"}).json()["id"]
    waitingId = client.post("/rf02/inbox-items", json={"content": "Aguardar retorno docente"}).json()["id"]

    client.patch(f"/rf06/inbox-items/{nextActionId}/status", json={"status": "next_action"})
    client.patch(f"/rf06/inbox-items/{waitingId}/status", json={"status": "waiting"})

    createPlanResponse = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 80, "deadlineDays": 8},
    )
    planId = createPlanResponse.json()["id"]

    advanceResponse = client.patch(
        f"/rf08/reading-plans/{planId}/advance",
        json={"pagesRead": 20},
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
            "contentBase64": _toBase64(b"acc"),
            "hours": 30,
        },
    )
    assert certificateResponse.status_code == 201

    dashboardResponse = client.get("/rf08/dashboard")
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

    responsePlanoInexistente = client.patch(
        "/rf08/reading-plans/999/advance",
        json={"pagesRead": 5},
    )
    assert responsePlanoInexistente.status_code == 404
    assert responsePlanoInexistente.json() == {
        "success": False,
        "message": "plano de leitura não encontrado",
    }

    createPlanResponse = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 40, "deadlineDays": 4},
    )
    planId = createPlanResponse.json()["id"]

    payloadInvalido = client.patch(
        f"/rf08/reading-plans/{planId}/advance",
        json={"pagesRead": 0, "extra": True},
    )
    payloadIncompleto = client.patch(f"/rf08/reading-plans/{planId}/advance", json={})

    assert payloadInvalido.status_code == 422
    assert payloadIncompleto.status_code == 422
