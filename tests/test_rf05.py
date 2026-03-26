from base64 import b64encode

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf04 import InMemoryCertificateStorage, RF04Service
from gtd_backend.rf05 import RF05Service


def _toBase64(content: bytes) -> str:
    return b64encode(content).decode("utf-8")


def _uploadCertificate(
    client: TestClient,
    *,
    originalName: str,
    contentType: str,
    content: bytes,
    hours: int | None,
) -> None:
    payload = {
        "originalName": originalName,
        "contentType": contentType,
        "contentBase64": _toBase64(content),
    }
    if hours is not None:
        payload["hours"] = hours

    response = client.post("/rf04/certificates", json=payload)
    assert response.status_code == 201


def test_rf05_service_deve_calcular_progresso_com_base_nas_horas_dos_certificados() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf04Service.uploadCertificate(
        originalName="a.pdf",
        contentType="application/pdf",
        content=b"a",
        hours=20,
    )
    rf04Service.uploadCertificate(
        originalName="b.pdf",
        contentType="application/pdf",
        content=b"b",
        hours=15,
    )
    rf04Service.uploadCertificate(
        originalName="c.pdf",
        contentType="application/pdf",
        content=b"c",
        hours=None,
    )

    service = RF05Service(rf04Service=rf04Service, defaultTargetHours=200)
    progress = service.getAccHoursProgress()

    assert progress["totalHours"] == 35
    assert progress["targetHours"] == 200
    assert progress["remainingHours"] == 165
    assert progress["percentage"] == 17.5
    assert progress["isCompleted"] is False


def test_rf05_service_deve_tratar_sem_certificados_e_meta_ultrapassada() -> None:
    emptyService = RF05Service(
        rf04Service=RF04Service(storage=InMemoryCertificateStorage()),
        defaultTargetHours=200,
    )
    emptyProgress = emptyService.getAccHoursProgress()

    assert emptyProgress["totalHours"] == 0
    assert emptyProgress["remainingHours"] == 200
    assert emptyProgress["percentage"] == 0.0
    assert emptyProgress["isCompleted"] is False

    rf04Service = RF04Service(storage=InMemoryCertificateStorage())
    rf04Service.uploadCertificate(
        originalName="x.pdf",
        contentType="application/pdf",
        content=b"x",
        hours=250,
    )
    completedService = RF05Service(rf04Service=rf04Service, defaultTargetHours=200)
    completedProgress = completedService.getAccHoursProgress()

    assert completedProgress["totalHours"] == 250
    assert completedProgress["targetHours"] == 200
    assert completedProgress["remainingHours"] == 0
    assert completedProgress["percentage"] == 100.0
    assert completedProgress["isCompleted"] is True


def test_rf05_service_deve_validar_meta_invalida() -> None:
    rf04Service = RF04Service(storage=InMemoryCertificateStorage())

    try:
        RF05Service(rf04Service=rf04Service, defaultTargetHours=0)
        assert False, "esperava erro para defaultTargetHours inválida"
    except ValueError as error:
        assert str(error) == "meta de horas deve ser maior que zero"

    service = RF05Service(rf04Service=rf04Service, defaultTargetHours=200)
    for invalidTarget in [0, -1]:
        try:
            service.getAccHoursProgress(targetHours=invalidTarget)
            assert False, "esperava erro para targetHours inválida"
        except ValueError as error:
            assert str(error) == "meta de horas deve ser maior que zero"


def test_rf05_http_deve_expor_endpoint_de_progresso_com_meta_padrao_e_personalizada() -> None:
    app = createApp()
    client = TestClient(app)

    _uploadCertificate(
        client,
        originalName="acc-1.pdf",
        contentType="application/pdf",
        content=b"conteudo-1",
        hours=30,
    )
    _uploadCertificate(
        client,
        originalName="acc-2.pdf",
        contentType="application/pdf",
        content=b"conteudo-2",
        hours=20,
    )

    defaultResponse = client.get("/rf05/acc-progress")
    assert defaultResponse.status_code == 200
    assert defaultResponse.json() == {
        "totalHours": 50,
        "targetHours": 200,
        "remainingHours": 150,
        "percentage": 25.0,
        "isCompleted": False,
    }

    customResponse = client.get("/rf05/acc-progress", params={"targetHours": 40})
    assert customResponse.status_code == 200
    assert customResponse.json() == {
        "totalHours": 50,
        "targetHours": 40,
        "remainingHours": 0,
        "percentage": 100.0,
        "isCompleted": True,
    }


def test_rf05_http_deve_rejeitar_target_hours_invalido() -> None:
    app = createApp()
    client = TestClient(app)

    invalidTargetResponse = client.get("/rf05/acc-progress", params={"targetHours": 0})
    assert invalidTargetResponse.status_code == 422
