import os
from base64 import b64encode
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf04 import (
    EncryptionConfigurationError,
    HmacXorContentCipher,
    InMemoryCertificateStorage,
    RF04Service,
    buildCertificateCipherFromEnvironment,
)


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
    assert saved["metadata"]["storageVersion"] == 2
    assert saved["metadata"]["encryptedAtRest"] is True


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


def test_rf04_service_deve_validar_magic_bytes_e_rejeitar_disfarce_de_tipo() -> None:
    service = RF04Service(storage=InMemoryCertificateStorage())

    service.uploadCertificate(
        originalName="certificado.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7\nconteudo",
        hours=4,
    )
    service.uploadCertificate(
        originalName="certificado.png",
        contentType="image/png",
        content=b"\x89PNG\r\n\x1a\nconteudo",
        hours=1,
    )
    service.uploadCertificate(
        originalName="certificado.jpg",
        contentType="image/jpeg",
        content=b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01imagem",
        hours=2,
    )

    cenariosInvalidos = [
        ("image/png", b"nao-e-png", "assinatura real do arquivo não corresponde ao tipo declarado"),
        ("application/pdf", b"texto livre", "assinatura real do arquivo não corresponde ao tipo declarado"),
        (
            "application/pdf",
            b"\x89PNG\r\n\x1a\nmas-declarado-como-pdf",
            "assinatura real do arquivo não corresponde ao tipo declarado",
        ),
    ]

    for contentType, content, expectedError in cenariosInvalidos:
        try:
            service.uploadCertificate(
                originalName="suspeito.bin",
                contentType=contentType,
                content=content,
            )
            assert False, "esperava ValueError para assinatura inválida"
        except ValueError as error:
            assert str(error) == expectedError


def test_rf04_service_deve_gerar_storage_key_unica_para_evitar_colisoes() -> None:
    service = RF04Service(storage=InMemoryCertificateStorage())

    firstId = service.uploadCertificate(
        originalName="certificado.jpg",
        contentType="image/jpeg",
        content=b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01imagem-1",
        hours=2,
    )
    secondId = service.uploadCertificate(
        originalName="certificado.jpg",
        contentType="image/jpeg",
        content=b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01imagem-1",
        hours=3,
    )

    listed = service.listCertificates()
    assert firstId != secondId
    assert listed[0]["storageKey"] != listed[1]["storageKey"]


def test_rf04_service_deve_listar_certificados_por_usuario() -> None:
    service = RF04Service(storage=InMemoryCertificateStorage())
    service.uploadCertificate(
        originalName="a.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 a",
        hours=1,
        userId=1,
    )
    service.uploadCertificate(
        originalName="b.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 b",
        hours=2,
        userId=2,
    )

    certificadosUser1 = service.listCertificates(userId=1)
    assert len(certificadosUser1) == 1
    assert certificadosUser1[0]["hours"] == 1


def test_rf04_service_deve_armazenar_conteudo_criptografado_em_repouso_e_recuperar_original() -> None:
    storage = InMemoryCertificateStorage()
    service = RF04Service(storage=storage)
    content = b"%PDF-1.7 payload sigiloso"

    certificateId = service.uploadCertificate(
        originalName="sigiloso.pdf",
        contentType="application/pdf",
        content=content,
        hours=1,
        userId=10,
    )
    certificate = service.listCertificates(userId=10)[0]
    rawStored = storage._files[certificate["storageKey"]]  # type: ignore[attr-defined]

    assert certificateId > 0
    assert rawStored != content
    assert b"payload sigiloso" not in rawStored

    restored = service.getCertificateContent(certificateId=certificateId, userId=10)
    assert restored == content


def test_rf04_service_deve_persistir_key_version_em_metadados_e_aceitar_keyring_ativo() -> None:
    storage = InMemoryCertificateStorage()
    cipher = HmacXorContentCipher(
        activeKeyVersion=2,
        keyring={2: b"chave-ativa-segura", 1: b"chave-legada-antiga"},
    )
    service = RF04Service(storage=storage, contentCipher=cipher)

    certificateId = service.uploadCertificate(
        originalName="versionado.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 versao",
        userId=1,
    )

    certificate = service.listCertificates(userId=1)[0]
    assert certificateId > 0
    assert certificate["metadata"]["storageVersion"] == 2
    assert certificate["metadata"]["keyVersion"] == 2


def test_rf04_service_deve_suportar_leitura_com_chave_legada_apos_rotacao() -> None:
    storage = InMemoryCertificateStorage()
    cipherV1 = HmacXorContentCipher(activeKeyVersion=1, keyring={1: b"k1-chave-legada"})
    serviceV1 = RF04Service(storage=storage, contentCipher=cipherV1)
    certIdV1 = serviceV1.uploadCertificate(
        originalName="antigo.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 legado",
        userId=1,
    )

    cipherV2 = HmacXorContentCipher(
        activeKeyVersion=2,
        keyring={2: b"k2-chave-ativa", 1: b"k1-chave-legada"},
    )
    serviceV2 = RF04Service(storage=storage, contentCipher=cipherV2, connection=serviceV1.connection)
    certIdV2 = serviceV2.uploadCertificate(
        originalName="novo.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 novo",
        userId=1,
    )

    restoredV1 = serviceV2.getCertificateContent(certificateId=certIdV1, userId=1)
    restoredV2 = serviceV2.getCertificateContent(certificateId=certIdV2, userId=1)
    assert restoredV1 == b"%PDF-1.7 legado"
    assert restoredV2 == b"%PDF-1.7 novo"


def test_rf04_service_deve_manter_compatibilidade_com_metadado_legado_sem_key_version() -> None:
    storage = InMemoryCertificateStorage()
    legacyCipher = HmacXorContentCipher(activeKeyVersion=1, keyring={1: b"chave-legada"})
    service = RF04Service(storage=storage, contentCipher=legacyCipher)
    certificateId = service.uploadCertificate(
        originalName="legacy.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 conteudo legado",
        userId=8,
    )
    service.connection.execute(
        "UPDATE acc_certificates SET metadata = ? WHERE id = ?",
        ('{"storageVersion":2,"encryptedAtRest":true}', certificateId),
    )
    service.connection.commit()

    rotatedCipher = HmacXorContentCipher(
        activeKeyVersion=2,
        keyring={2: b"chave-nova", 1: b"chave-legada"},
    )
    rotatedService = RF04Service(storage=storage, contentCipher=rotatedCipher, connection=service.connection)
    restored = rotatedService.getCertificateContent(certificateId=certificateId, userId=8)
    assert restored == b"%PDF-1.7 conteudo legado"


def test_rf04_config_deve_falhar_sem_chave_em_producao_sem_vazamento() -> None:
    oldEnv = os.environ.copy()
    try:
        os.environ.pop("CERTIFICATE_KEY_ACTIVE_VERSION", None)
        os.environ.pop("CERTIFICATE_KEY_1", None)
        os.environ.pop("CERTIFICATE_KEY_LEGACY_VERSIONS", None)
        try:
            buildCertificateCipherFromEnvironment(environmentName="production")
            assert False, "esperava falha por ausência de chave em produção"
        except EncryptionConfigurationError as error:
            message = str(error)
            assert "chave de criptografia" in message
            assert "CERTIFICATE_KEY_" not in message
    finally:
        os.environ.clear()
        os.environ.update(oldEnv)


def test_rf04_config_deve_falhar_com_key_version_desconhecida_sem_expor_material_sensivel() -> None:
    oldEnv = os.environ.copy()
    try:
        os.environ["CERTIFICATE_KEY_ACTIVE_VERSION"] = "2"
        os.environ["CERTIFICATE_KEY_1"] = "apenas-legada"
        os.environ["CERTIFICATE_KEY_LEGACY_VERSIONS"] = "1"
        try:
            buildCertificateCipherFromEnvironment(environmentName="production")
            assert False, "esperava falha por chave ativa incompatível"
        except EncryptionConfigurationError as error:
            message = str(error)
            assert "versão de chave ativa inválida" in message
            assert "apenas-legada" not in message
    finally:
        os.environ.clear()
        os.environ.update(oldEnv)


def test_rf04_service_deve_tratar_falha_de_decrypt_e_lookup_com_segurança() -> None:
    storage = InMemoryCertificateStorage()
    service = RF04Service(storage=storage)
    certificateId = service.uploadCertificate(
        originalName="ok.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 arquivo",
        userId=1,
    )

    try:
        service.getCertificateContent(certificateId=999, userId=1)
        assert False, "esperava LookupError para certificado inexistente"
    except LookupError as error:
        assert str(error) == "certificado não encontrado"

    certificate = service.listCertificates(userId=1)[0]
    storage._files[certificate["storageKey"]] = b"dado-corrompido"  # type: ignore[attr-defined]
    try:
        service.getCertificateContent(certificateId=certificateId, userId=1)
        assert False, "esperava ValueError para falha de decrypt"
    except ValueError as error:
        assert str(error) == "falha ao recuperar certificado"


def test_rf04_service_deve_falhar_com_seguranca_para_key_version_desconhecida() -> None:
    storage = InMemoryCertificateStorage()
    cipher = HmacXorContentCipher(activeKeyVersion=1, keyring={1: b"chave-v1"})
    service = RF04Service(storage=storage, contentCipher=cipher)
    certificateId = service.uploadCertificate(
        originalName="desconhecida.pdf",
        contentType="application/pdf",
        content=b"%PDF-1.7 payload",
        userId=1,
    )
    service.connection.execute(
        "UPDATE acc_certificates SET metadata = ? WHERE id = ?",
        ('{"storageVersion":2,"encryptedAtRest":true,"keyVersion":99}', certificateId),
    )
    service.connection.commit()

    try:
        service.getCertificateContent(certificateId=certificateId, userId=1)
        assert False, "esperava falha para keyVersion desconhecida"
    except ValueError as error:
        assert str(error) == "falha ao recuperar certificado"


def test_rf04_http_deve_realizar_upload_e_listar_certificados() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    token = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    responseUpload = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.png",
            "contentType": "image/png",
            "contentBase64": _toBase64(b"\x89PNG\r\n\x1a\nconteudo-png"),
            "hours": 20,
        },
        headers=headers,
    )

    assert responseUpload.status_code == 201
    certificateId = responseUpload.json()["id"]

    responseList = client.get("/rf04/certificates", headers=headers)
    assert responseList.status_code == 200

    certificates = responseList.json()
    assert len(certificates) == 1
    assert certificates[0]["id"] == certificateId
    assert certificates[0]["contentType"] == "image/png"
    assert certificates[0]["hours"] == 20
    assert "fileIdentifier" in certificates[0]
    assert certificates[0]["metadata"]["encryptedAtRest"] is True


def test_rf04_http_deve_rejeitar_payload_invalido_arquivo_maior_que_5mb_ou_tipo_nao_suportado() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    token = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    missingField = client.post(
        "/rf04/certificates",
        json={"originalName": "x.pdf", "contentType": "application/pdf"},
        headers=headers,
    )
    assert missingField.status_code == 422

    invalidHours = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"%PDF-1.7 conteudo"),
            "hours": -10,
        },
        headers=headers,
    )
    assert invalidHours.status_code == 422

    invalidBase64 = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": "***nao-base64***",
        },
        headers=headers,
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
        headers=headers,
    )
    assert invalidType.status_code == 400
    assert invalidType.json()["message"] == "tipo de arquivo não permitido"

    oversized = client.post(
        "/rf04/certificates",
        json={
            "originalName": "certificado.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"%PDF-" + b"a" * (5 * 1024 * 1024)),
        },
        headers=headers,
    )
    assert oversized.status_code == 400
    assert oversized.json()["message"] == "arquivo excede o limite de 5 MB"

    mismatchMime = client.post(
        "/rf04/certificates",
        json={
            "originalName": "mismatch.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"\x89PNG\r\n\x1a\nconteudo"),
        },
        headers=headers,
    )
    assert mismatchMime.status_code == 400
    assert mismatchMime.json()["message"] == "assinatura real do arquivo não corresponde ao tipo declarado"


def test_rf04_http_deve_rejeitar_sem_autenticacao_e_restringir_ownership() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("a@unioeste.br", "SenhaForte123")
    app.state.authService.register_user("b@unioeste.br", "SenhaForte123")
    tokenA = client.post(
        "/auth/login",
        json={"email": "a@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    tokenB = client.post(
        "/auth/login",
        json={"email": "b@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    headersA = {"Authorization": f"Bearer {tokenA}"}
    headersB = {"Authorization": f"Bearer {tokenB}"}

    respostaSemToken = client.get("/rf04/certificates")
    assert respostaSemToken.status_code == 401

    client.post(
        "/rf04/certificates",
        json={
            "originalName": "a.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"%PDF-1.7 a"),
            "hours": 5,
        },
        headers=headersA,
    )
    client.post(
        "/rf04/certificates",
        json={
            "originalName": "b.pdf",
            "contentType": "application/pdf",
            "contentBase64": _toBase64(b"%PDF-1.7 b"),
            "hours": 7,
        },
        headers=headersB,
    )

    respostaA = client.get("/rf04/certificates", headers=headersA)
    respostaB = client.get("/rf04/certificates", headers=headersB)
    assert [item["hours"] for item in respostaA.json()] == [5]
    assert [item["hours"] for item in respostaB.json()] == [7]
