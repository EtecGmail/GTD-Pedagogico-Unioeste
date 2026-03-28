import hashlib
import hmac
import os
import re
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

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

    def decrypt(self, cipherContent: bytes) -> bytes:
        raise NotImplementedError


class HmacXorContentCipher(ContentCipher):
    def __init__(self, encryptionKey: bytes | None = None) -> None:
        configuredKey = encryptionKey or os.environ.get("CERTIFICATE_STORAGE_KEY", "").encode("utf-8")
        if configuredKey:
            self.encryptionKey = hashlib.sha256(configuredKey).digest()
        else:
            self.encryptionKey = hashlib.sha256(b"gtd-pedagogico-unioeste-dev-key").digest()

    def encrypt(self, plainContent: bytes) -> bytes:
        nonce = os.urandom(16)
        stream = self._buildStream(len(plainContent), nonce)
        encryptedBody = bytes([plainByte ^ streamByte for plainByte, streamByte in zip(plainContent, stream)])
        signature = hmac.new(self.encryptionKey, nonce + encryptedBody, digestmod=hashlib.sha256).digest()
        return b"GTD1" + nonce + signature + encryptedBody

    def decrypt(self, cipherContent: bytes) -> bytes:
        if len(cipherContent) < 52 or not cipherContent.startswith(b"GTD1"):
            raise ValueError("payload criptografado inválido")
        nonce = cipherContent[4:20]
        expectedSignature = cipherContent[20:52]
        encryptedBody = cipherContent[52:]
        computedSignature = hmac.new(self.encryptionKey, nonce + encryptedBody, digestmod=hashlib.sha256).digest()
        if not hmac.compare_digest(expectedSignature, computedSignature):
            raise ValueError("assinatura criptográfica inválida")
        stream = self._buildStream(len(encryptedBody), nonce)
        return bytes([encryptedByte ^ streamByte for encryptedByte, streamByte in zip(encryptedBody, stream)])

    def _buildStream(self, size: int, nonce: bytes) -> bytes:
        output = bytearray()
        counter = 0
        while len(output) < size:
            block = hashlib.sha256(self.encryptionKey + nonce + counter.to_bytes(8, "big")).digest()
            output.extend(block)
            counter += 1
        return bytes(output[:size])


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
        self.connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.storage = storage
        self.contentCipher = contentCipher or HmacXorContentCipher()
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS acc_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_identifier TEXT NOT NULL UNIQUE,
                original_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                hours INTEGER,
                storage_key TEXT NOT NULL UNIQUE,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = self.connection.execute("PRAGMA table_info(acc_certificates)").fetchall()
        existingColumns = {str(column["name"]) for column in columns}
        if "user_id" not in existingColumns:
            self.connection.execute("ALTER TABLE acc_certificates ADD COLUMN user_id INTEGER")
        self.connection.commit()

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
        metadata = '{"storageVersion":2,"encryptedAtRest":true}'

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
                "SELECT storage_key FROM acc_certificates WHERE id = ?",
                (certificateId,),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT storage_key FROM acc_certificates WHERE id = ? AND user_id = ?",
                (certificateId, userId),
            ).fetchone()
        if row is None:
            raise LookupError("certificado não encontrado")
        storageKey = str(row["storage_key"])

        try:
            encryptedContent = self.storage.load(storageKey=storageKey)
            return self.contentCipher.decrypt(encryptedContent)
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
                "metadata": {"storageVersion": 2, "encryptedAtRest": True},
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]

    def _detectContentType(self, content: bytes) -> str | None:
        if content.startswith(b"%PDF-"):
            return "application/pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        return None
