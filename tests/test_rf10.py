from base64 import b64encode

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf04 import InMemoryCertificateStorage, RF04Service
from gtd_backend.rf09 import SecurityEventService
from gtd_backend.rf10 import RF10Service


def _toBase64(content: bytes) -> str:
    return b64encode(content).decode("utf-8")

def _fakePdfContent(size: int) -> bytes:
    if size < 5:
        size = 5
    return b"%PDF-" + (b"z" * (size - 5))


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["accessToken"])


def test_rf10_service_deve_retornar_uso_zero_quando_usuario_nao_tem_certificados() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    service = RF10Service(rf04Service=rf04Service, quotaBytes=1_000)

    summary = service.getStorageUsageSummary(userId=1)

    assert summary["totalBytesUsed"] == 0
    assert summary["quotaBytes"] == 1_000
    assert summary["percentageUsed"] == 0.0
    assert summary["isNearLimit"] is False
    assert summary["isOverLimit"] is False


def test_rf10_service_deve_somar_apenas_certificados_do_usuario_e_ativar_alerta_em_90_por_cento() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf04Service.uploadCertificate(
        originalName="u1-a.pdf",
        contentType="application/pdf",
        content=_fakePdfContent(450),
        userId=1,
    )
    rf04Service.uploadCertificate(
        originalName="u1-b.pdf",
        contentType="application/pdf",
        content=_fakePdfContent(450),
        userId=1,
    )
    rf04Service.uploadCertificate(
        originalName="u2.pdf",
        contentType="application/pdf",
        content=_fakePdfContent(900),
        userId=2,
    )

    service = RF10Service(rf04Service=rf04Service, quotaBytes=1_000)

    user1 = service.getStorageUsageSummary(userId=1)
    user2 = service.getStorageUsageSummary(userId=2)

    assert user1["totalBytesUsed"] == 900
    assert user1["percentageUsed"] == 90.0
    assert user1["isNearLimit"] is True
    assert user1["isOverLimit"] is False

    assert user2["totalBytesUsed"] == 900
    assert user2["percentageUsed"] == 90.0
    assert user2["isNearLimit"] is True
    assert user2["isOverLimit"] is False


def test_rf10_service_deve_sinalizar_quando_ultrapassar_cota() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf04Service.uploadCertificate(
        originalName="u1.pdf",
        contentType="application/pdf",
        content=_fakePdfContent(1_001),
        userId=1,
    )
    service = RF10Service(rf04Service=rf04Service, quotaBytes=1_000)

    summary = service.getStorageUsageSummary(userId=1)

    assert summary["totalBytesUsed"] == 1_001
    assert summary["percentageUsed"] == 100.1
    assert summary["isNearLimit"] is True
    assert summary["isOverLimit"] is True


def test_rf10_service_deve_tratar_configuracao_invalida_de_quota() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())

    try:
        RF10Service(rf04Service=rf04Service, quotaBytes=0)
        assert False, "esperava ValueError para quota inválida"
    except ValueError as error:
        assert str(error) == "quota de armazenamento deve ser maior que zero"


def test_rf10_http_deve_expor_resumo_de_cota_para_usuario_autenticado_com_isolamento() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("a@unioeste.br", "SenhaForte123")
    app.state.authService.register_user("b@unioeste.br", "SenhaForte123")
    tokenA = _login(client, "a@unioeste.br", "SenhaForte123")
    tokenB = _login(client, "b@unioeste.br", "SenhaForte123")

    client.post(
        "/rf04/certificates",
        json={
            "originalName": "a.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(_fakePdfContent(900)),
        },
        headers={"Authorization": f"Bearer {tokenA}"},
    )
    client.post(
        "/rf04/certificates",
        json={
            "originalName": "b.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(_fakePdfContent(300)),
        },
        headers={"Authorization": f"Bearer {tokenB}"},
    )

    responseA = client.get("/rf10/storage-usage", headers={"Authorization": f"Bearer {tokenA}"})
    responseB = client.get("/rf10/storage-usage", headers={"Authorization": f"Bearer {tokenB}"})

    assert responseA.status_code == 200
    assert responseA.json()["totalBytesUsed"] == 900
    assert responseB.status_code == 200
    assert responseB.json()["totalBytesUsed"] == 300


def test_rf10_http_deve_rejeitar_sem_autenticacao() -> None:
    app = createApp()
    client = TestClient(app)

    response = client.get("/rf10/storage-usage")

    assert response.status_code == 401


def test_rf10_service_deve_registrar_evento_uma_vez_ao_entrar_na_faixa_de_alerta() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf09Service = SecurityEventService()
    service = RF10Service(rf04Service=rf04Service, quotaBytes=1_000, rf09Service=rf09Service)

    rf04Service.uploadCertificate(
        originalName="u1.pdf",
        contentType="application/pdf",
        content=_fakePdfContent(900),
        userId=1,
    )

    firstSummary = service.getStorageUsageSummary(userId=1)
    secondSummary = service.getStorageUsageSummary(userId=1)

    assert firstSummary["isNearLimit"] is True
    assert secondSummary["isNearLimit"] is True
    events = rf09Service.listEvents(limit=10)
    quotaEvents = [event for event in events if event["eventType"] == "storage_quota_near_limit"]
    assert len(quotaEvents) == 1
    assert quotaEvents[0]["result"] == "warning"
    assert quotaEvents[0]["userId"] == 1
