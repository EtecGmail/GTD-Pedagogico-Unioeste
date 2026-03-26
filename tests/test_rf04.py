from base64 import b64encode
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf04 import InMemoryCertificateStorage, RF04Service


def _toBase64(content: bytes) -> str:
    return b64encode(content).decode("utf-8")


def test_rf04_service_deve_salvar_certificado_com_identificador_unico_e_metadados_minimos() -> None:
    storage = InMemoryCertificateStorage()
    service = RF04Service(
        storage=storage,
        nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC),
    )

    certificateId = service.uploadCertificate(
        originalName=" certificado_acc_final .pdf ",
        contentType="application/pdf",
        content=b"%PDF-1.7 conteudo",
        hours=12,
    )

    certificates = service.listCertificates()
    assert certificateId > 0
    assert len(certificates) == 1
    saved = certificates[0]
    assert saved["id"] == certificateId
    assert saved["originalName"].endswith(".pdf")
    assert saved["contentType"] == "application/pdf"
    assert saved["sizeBytes"] == len(b"%PDF-1.7 conteudo")
    assert saved["hours"] == 12
    assert saved["createdAt"] == "2026-03-26T12:00:00+00:00"
    assert isinstance(saved["fileIdentifier"], str)
    assert len(saved["fileIdentifier"]) >= 32
    assert isinstance(saved["metadata"], dict)
    assert saved["metadata"]["storageVersion"] == 1


def test_rf04_service_deve_rejeitar_tipo_nao_permitido_tamanho_acima_de_5mb_e_payload_invalido() -> None:
    service = RF04Service(storage=InMemoryCertificateStorage())

    casos = [
        ("certificado.txt", "text/plain", b"abc", None, "tipo de arquivo não permitido"),
        (
            "certificado.pdf",
            "application/pdf",
            b"a" * (5 * 1024 * 1024 + 1),
            None,
            "arquivo excede o limite de 5 MB",
        ),
        (" ", "application/pdf", b"abc", None, "nome original do arquivo é obrigatório"),
        ("certificado.pdf", "application/pdf", b"", None, "conteúdo do arquivo é obrigatório"),
        ("certificado.pdf", "application/pdf", b"abc", -1, "horas devem ser zero ou positivas"),
    ]

    for originalName, contentType, content, hours, expectedError in casos:
        try:
            service.uploadCertificate(
                originalName=originalName,
                contentType=contentType,
                content=content,
                hours=hours,
            )
            assert False, "esperava ValueError para upload inválido"
        except ValueError as error:
            assert str(error) == expectedError


def test_rf04_service_deve_gerar_storage_key_unica_para_evitar_colisoes() -> None:
    service = RF04Service(storage=InMemoryCertificateStorage())

    firstId = service.uploadCertificate(
        originalName="certificado.jpg",
        contentType="image/jpeg",
        content=b"imagem-1",
        hours=2,
    )
    secondId = service.uploadCertificate(
        originalName="certificado.jpg",
        contentType="image/jpeg",
        content=b"imagem-1",
        hours=3,
    )

    listed = service.listCertificates()
    assert firstId != secondId
    assert listed[0]["storageKey"] != listed[1]["storageKey"]


def test_rf04_http_deve_realizar_upload_e_listar_certificados() -> None:
    app = createApp()
    client = TestClient(app)

    responseUpload = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.png",
            "contentType": "image/png",
            "contentBase64": _toBase64(b"conteudo-png"),
            "hours": 20,
        },
    )

    assert responseUpload.status_code == 201
    certificateId = responseUpload.json()["id"]

    responseList = client.get("/rf04/certificates")
    assert responseList.status_code == 200

    certificates = responseList.json()
    assert len(certificates) == 1
    assert certificates[0]["id"] == certificateId
    assert certificates[0]["contentType"] == "image/png"
    assert certificates[0]["hours"] == 20
    assert "fileIdentifier" in certificates[0]


def test_rf04_http_deve_rejeitar_payload_invalido_arquivo_maior_que_5mb_ou_tipo_nao_suportado() -> None:
    app = createApp()
    client = TestClient(app)

    missingField = client.post(
        "/rf04/certificates",
        json={"originalName": "x.pdf", "contentType": "application/pdf"},
    )
    assert missingField.status_code == 422

    invalidHours = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"conteudo"),
            "hours": -10,
        },
    )
    assert invalidHours.status_code == 422

    invalidBase64 = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": "***nao-base64***",
        },
    )
    assert invalidBase64.status_code == 400
    assert invalidBase64.json()["message"] == "payload de arquivo inválido"

    invalidType = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.gif",
            "contentType": "image/gif",
            "contentBase64": _toBase64(b"gif"),
        },
    )
    assert invalidType.status_code == 400
    assert invalidType.json()["message"] == "tipo de arquivo não permitido"

    oversized = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"a" * (5 * 1024 * 1024 + 1)),
        },
    )
    assert oversized.status_code == 400
    assert oversized.json()["message"] == "arquivo excede o limite de 5 MB"
