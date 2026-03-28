import hashlib
import hmac
import json
import os
import re
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from gtd_backend.persistence import applyMigrations

MAX_CERTIFICATE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class CertificateStorage:
    def save(self, storageKey: str, content: bytes) -> None:
        raise NotImplementedError

    def load(self, storageKey: str) -> bytes:
        raise NotImplementedError

    def exists(self, storageKey: str) -> bool:
        raise NotImplementedError


class InMemoryCertificateStorage(CertificateStorage):
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def save(self, storageKey: str, content: bytes) -> None:
        self._files[storageKey] = content

    def load(self, storageKey: str) -> bytes:
        if storageKey not in self._files:
            raise LookupError("arquivo não encontrado no cofre")
        return self._files[storageKey]

    def exists(self, storageKey: str) -> bool:
        return storageKey in self._files


class ContentCipher:
    def encrypt(self, plainContent: bytes) -> bytes:
        raise NotImplementedError

    def decrypt(self, cipherContent: bytes, keyVersion: int | None = None) -> bytes:
        raise NotImplementedError

    def getActiveKeyVersion(self) -> int:
        raise NotImplementedError


class EncryptionConfigurationError(ValueError):
    pass


class HmacXorContentCipher(ContentCipher):
    def __init__(
        self,
        encryptionKey: bytes | None = None,
        activeKeyVersion: int = 1,
        keyring: dict[int, bytes] | None = None,
    ) -> None:
        if keyring is None:
            defaultKey = encryptionKey or os.environ.get("CERTIFICATE_STORAGE_KEY", "").encode("utf-8")
            if not defaultKey:
                defaultKey = b"gtd-pedagogico-unioeste-dev-key"
            keyring = {activeKeyVersion: defaultKey}
        if activeKeyVersion not in keyring:
            raise EncryptionConfigurationError("versão de chave ativa inválida")

        self.activeKeyVersion = activeKeyVersion
        self.keyring = {version: hashlib.sha256(value).digest() for version, value in keyring.items()}

    def encrypt(self, plainContent: bytes) -> bytes:
        nonce = os.urandom(16)
        encryptionKey = self._resolveKeyByVersion(self.activeKeyVersion)
        stream = self._buildStream(len(plainContent), nonce, encryptionKey)
        encryptedBody = bytes([plainByte ^ streamByte for plainByte, streamByte in zip(plainContent, stream)])
        signature = hmac.new(encryptionKey, nonce + encryptedBody, digestmod=hashlib.sha256).digest()
        return b"GTD1" + nonce + signature + encryptedBody

    def decrypt(self, cipherContent: bytes, keyVersion: int | None = None) -> bytes:
        if len(cipherContent) < 52 or not cipherContent.startswith(b"GTD1"):
            raise ValueError("payload criptografado inválido")
        nonce = cipherContent[4:20]
        expectedSignature = cipherContent[20:52]
        encryptedBody = cipherContent[52:]

        if keyVersion is None:
            versionsToTry = [self.activeKeyVersion] + [
                version for version in self.keyring if version != self.activeKeyVersion
            ]
        else:
            versionsToTry = [keyVersion]

        for version in versionsToTry:
            if version not in self.keyring:
                continue
            decryptionKey = self._resolveKeyByVersion(version)
            computedSignature = hmac.new(decryptionKey, nonce + encryptedBody, digestmod=hashlib.sha256).digest()
            if not hmac.compare_digest(expectedSignature, computedSignature):
                continue
            stream = self._buildStream(len(encryptedBody), nonce, decryptionKey)
            return bytes([encryptedByte ^ streamByte for encryptedByte, streamByte in zip(encryptedBody, stream)])

        if keyVersion is not None and keyVersion not in self.keyring:
            raise ValueError("versão de chave desconhecida")
        raise ValueError("assinatura criptográfica inválida")

    def getActiveKeyVersion(self) -> int:
        return self.activeKeyVersion

    def _resolveKeyByVersion(self, keyVersion: int) -> bytes:
        key = self.keyring.get(keyVersion)
        if key is None:
            raise ValueError("versão de chave desconhecida")
        return key

    def _buildStream(self, size: int, nonce: bytes, encryptionKey: bytes) -> bytes:
        output = bytearray()
        counter = 0
        while len(output) < size:
            block = hashlib.sha256(encryptionKey + nonce + counter.to_bytes(8, "big")).digest()
            output.extend(block)
            counter += 1
        return bytes(output[:size])


def buildCertificateCipherFromEnvironment(environmentName: str | None = None) -> HmacXorContentCipher:
    normalizedEnvironment = (environmentName or os.environ.get("APP_ENV", "development")).strip().lower()
    isProduction = normalizedEnvironment in {"prod", "production"}
    activeVersionRaw = os.environ.get("CERTIFICATE_KEY_ACTIVE_VERSION", "").strip()

    if not activeVersionRaw:
        if isProduction:
            raise EncryptionConfigurationError("chave de criptografia do cofre não configurada")
        return HmacXorContentCipher()

    if not activeVersionRaw.isdigit() or int(activeVersionRaw) <= 0:
        raise EncryptionConfigurationError("versão de chave ativa inválida")

    activeKeyVersion = int(activeVersionRaw)
    keyring: dict[int, bytes] = {}

    activeKeyValue = os.environ.get(f"CERTIFICATE_KEY_{activeKeyVersion}", "").strip()
    if not activeKeyValue:
        raise EncryptionConfigurationError("versão de chave ativa inválida")
    keyring[activeKeyVersion] = activeKeyValue.encode("utf-8")

    legacyVersionsRaw = os.environ.get("CERTIFICATE_KEY_LEGACY_VERSIONS", "").strip()
    if legacyVersionsRaw:
        for rawValue in legacyVersionsRaw.split(","):
            normalizedValue = rawValue.strip()
            if not normalizedValue:
                continue
            if not normalizedValue.isdigit() or int(normalizedValue) <= 0:
                raise EncryptionConfigurationError("versão legada inválida")
            legacyVersion = int(normalizedValue)
            if legacyVersion == activeKeyVersion:
                continue
            legacyKeyValue = os.environ.get(f"CERTIFICATE_KEY_{legacyVersion}", "").strip()
            if not legacyKeyValue:
                raise EncryptionConfigurationError("configuração de chave legada incompleta")
            keyring[legacyVersion] = legacyKeyValue.encode("utf-8")

    return HmacXorContentCipher(activeKeyVersion=activeKeyVersion, keyring=keyring)


def _sanitizeOriginalName(originalName: str) -> str:
    normalizedName = " ".join(originalName.strip().split())
    if not normalizedName:
        raise ValueError("nome original do arquivo é obrigatório")

    fileName = normalizedName.split("/")[-1].split("\\")[-1]
    sanitized = re.sub(r"[^a-zA-Z0-9._ -]", "_", fileName)
    sanitized = sanitized.strip(" .")
    if not sanitized:
        raise ValueError("nome original do arquivo é obrigatório")
    return sanitized


class RF04Service:
    def __init__(
        self,
        storage: CertificateStorage,
        contentCipher: ContentCipher | None = None,
        nowProvider: Callable[[], datetime] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        ownsConnection = connection is None
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        if ownsConnection:
            applyMigrations(connection=self.connection)
        self.storage = storage
        self.contentCipher = contentCipher or HmacXorContentCipher()
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))

    def uploadCertificate(
        self,
        originalName: str,
        contentType: str,
        content: bytes,
        hours: int | None = None,
        userId: int | None = None,
    ) -> int:
        safeOriginalName = _sanitizeOriginalName(originalName)

        if contentType not in ALLOWED_CONTENT_TYPES:
            raise ValueError("tipo de arquivo não permitido")
        if len(content) == 0:
            raise ValueError("conteúdo do arquivo é obrigatório")
        if len(content) > MAX_CERTIFICATE_SIZE_BYTES:
            raise ValueError("arquivo excede o limite de 5 MB")
        if hours is not None and hours < 0:
            raise ValueError("horas devem ser zero ou positivas")
        if userId is not None and userId <= 0:
            raise ValueError("usuário do certificado é inválido")
        detectedContentType = self._detectContentType(content)
        if detectedContentType != contentType:
            raise ValueError("assinatura real do arquivo não corresponde ao tipo declarado")

        fileIdentifier = uuid.uuid4().hex
        storageKey = self._buildUniqueStorageKey(content=content, contentType=contentType)
        createdAt = self.nowProvider().isoformat()
        metadataDict = {
            "storageVersion": 2,
            "encryptedAtRest": True,
            "keyVersion": self.contentCipher.getActiveKeyVersion(),
        }
        metadata = json.dumps(metadataDict, separators=(",", ":"))

        cursor = self.connection.execute(
            """
            INSERT INTO acc_certificates (
                user_id,
                file_identifier,
                original_name,
                content_type,
                size_bytes,
                hours,
                storage_key,
                metadata,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                userId,
                fileIdentifier,
                safeOriginalName,
                contentType,
                len(content),
                hours,
                storageKey,
                metadata,
                createdAt,
            ),
        )
        encryptedContent = self.contentCipher.encrypt(content)
        self.storage.save(storageKey=storageKey, content=encryptedContent)
        self.connection.commit()
        return int(cursor.lastrowid)

    def getCertificateContent(self, certificateId: int, userId: int | None = None) -> bytes:
        if certificateId <= 0:
            raise ValueError("certificado inválido")
        if userId is not None and userId <= 0:
            raise ValueError("usuário do certificado é inválido")

        if userId is None:
            row = self.connection.execute(
                "SELECT storage_key, metadata FROM acc_certificates WHERE id = ?",
                (certificateId,),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT storage_key, metadata FROM acc_certificates WHERE id = ? AND user_id = ?",
                (certificateId, userId),
            ).fetchone()
        if row is None:
            raise LookupError("certificado não encontrado")
        storageKey = str(row["storage_key"])
        metadata = self._parseMetadata(str(row["metadata"]))
        keyVersion = metadata.get("keyVersion")
        if not isinstance(keyVersion, int):
            keyVersion = None

        try:
            encryptedContent = self.storage.load(storageKey=storageKey)
            return self.contentCipher.decrypt(encryptedContent, keyVersion=keyVersion)
        except LookupError:
            raise
        except Exception as error:
            raise ValueError("falha ao recuperar certificado") from error

    def _buildUniqueStorageKey(self, content: bytes, contentType: str) -> str:
        extension = ALLOWED_CONTENT_TYPES[contentType]

        for _ in range(5):
            nonce = uuid.uuid4().hex
            contentHash = hashlib.sha256(content + nonce.encode("utf-8")).hexdigest()
            storageKey = f"acc/{contentHash}.{extension}"
            if not self.storage.exists(storageKey):
                return storageKey

        raise ValueError("falha ao gerar identificador único para armazenamento")

    def listCertificates(
        self,
        userId: int | None = None,
    ) -> list[dict[str, int | str | None | dict[str, int | bool]]]:
        if userId is None:
            rows = self.connection.execute(
                """
                SELECT
                    id,
                    file_identifier,
                    original_name,
                    content_type,
                    size_bytes,
                    hours,
                    storage_key,
                    metadata,
                    created_at
                FROM acc_certificates
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        else:
            if userId <= 0:
                raise ValueError("usuário do certificado é inválido")
            rows = self.connection.execute(
                """
                SELECT
                    id,
                    file_identifier,
                    original_name,
                    content_type,
                    size_bytes,
                    hours,
                    storage_key,
                    metadata,
                    created_at
                FROM acc_certificates
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (userId,),
            ).fetchall()

        return [
            {
                "id": int(row["id"]),
                "fileIdentifier": str(row["file_identifier"]),
                "originalName": str(row["original_name"]),
                "contentType": str(row["content_type"]),
                "sizeBytes": int(row["size_bytes"]),
                "hours": int(row["hours"]) if row["hours"] is not None else None,
                "storageKey": str(row["storage_key"]),
                "metadata": self._parseMetadata(str(row["metadata"])),
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]

    def _parseMetadata(self, metadataValue: str) -> dict[str, int | bool]:
        try:
            loadedMetadata = json.loads(metadataValue)
        except Exception:
            return {"storageVersion": 2, "encryptedAtRest": True}
        if not isinstance(loadedMetadata, dict):
            return {"storageVersion": 2, "encryptedAtRest": True}
        normalizedMetadata: dict[str, int | bool] = {
            "storageVersion": int(loadedMetadata.get("storageVersion", 2)),
            "encryptedAtRest": bool(loadedMetadata.get("encryptedAtRest", True)),
        }
        if "keyVersion" in loadedMetadata and isinstance(loadedMetadata["keyVersion"], int):
            normalizedMetadata["keyVersion"] = int(loadedMetadata["keyVersion"])
        return normalizedMetadata

    def _detectContentType(self, content: bytes) -> str | None:
        if content.startswith(b"%PDF-"):
            return "application/pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        return None
