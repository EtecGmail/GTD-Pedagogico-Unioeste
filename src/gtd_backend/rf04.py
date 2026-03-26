import hashlib
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

    def exists(self, storageKey: str) -> bool:
        raise NotImplementedError


class InMemoryCertificateStorage(CertificateStorage):
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def save(self, storageKey: str, content: bytes) -> None:
        self._files[storageKey] = content

    def exists(self, storageKey: str) -> bool:
        return storageKey in self._files


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
        nowProvider: Callable[[], datetime] | None = None,
    ) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.storage = storage
        self.nowProvider = nowProvider or (lambda: datetime.now(tz=UTC))
        self._setupSchema()

    def _setupSchema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS acc_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        self.connection.commit()

    def uploadCertificate(
        self,
        originalName: str,
        contentType: str,
        content: bytes,
        hours: int | None = None,
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

        fileIdentifier = uuid.uuid4().hex
        storageKey = self._buildUniqueStorageKey(content=content, contentType=contentType)
        createdAt = self.nowProvider().isoformat()
        metadata = '{"storageVersion":1,"encryptedAtRest":false}'

        cursor = self.connection.execute(
            """
            INSERT INTO acc_certificates (
                file_identifier,
                original_name,
                content_type,
                size_bytes,
                hours,
                storage_key,
                metadata,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
        self.storage.save(storageKey=storageKey, content=content)
        self.connection.commit()
        return int(cursor.lastrowid)

    def _buildUniqueStorageKey(self, content: bytes, contentType: str) -> str:
        extension = ALLOWED_CONTENT_TYPES[contentType]

        for _ in range(5):
            nonce = uuid.uuid4().hex
            contentHash = hashlib.sha256(content + nonce.encode("utf-8")).hexdigest()
            storageKey = f"acc/{contentHash}.{extension}"
            if not self.storage.exists(storageKey):
                return storageKey

        raise ValueError("falha ao gerar identificador único para armazenamento")

    def listCertificates(self) -> list[dict[str, int | str | None | dict[str, int | bool]]]:
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

        return [
            {
                "id": int(row["id"]),
                "fileIdentifier": str(row["file_identifier"]),
                "originalName": str(row["original_name"]),
                "contentType": str(row["content_type"]),
                "sizeBytes": int(row["size_bytes"]),
                "hours": int(row["hours"]) if row["hours"] is not None else None,
                "storageKey": str(row["storage_key"]),
                "metadata": {"storageVersion": 1, "encryptedAtRest": False},
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]
