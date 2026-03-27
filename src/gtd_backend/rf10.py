from typing import TypedDict

from gtd_backend.rf04 import RF04Service
from gtd_backend.rf09 import SecurityEventService


class StorageUsageSummary(TypedDict):
    totalBytesUsed: int
    quotaBytes: int
    percentageUsed: float
    isNearLimit: bool
    isOverLimit: bool


class RF10Service:
    def __init__(
        self,
        rf04Service: RF04Service,
        quotaBytes: int,
        rf09Service: SecurityEventService | None = None,
    ) -> None:
        if quotaBytes <= 0:
            raise ValueError("quota de armazenamento deve ser maior que zero")

        self.rf04Service = rf04Service
        self.quotaBytes = quotaBytes
        self.rf09Service = rf09Service
        self._usersAlreadyWarned: set[int] = set()

    def getStorageUsageSummary(self, userId: int) -> StorageUsageSummary:
        if userId <= 0:
            raise ValueError("usuário inválido")

        certificates = self.rf04Service.listCertificates(userId=userId)
        totalBytesUsed = sum(int(certificate["sizeBytes"]) for certificate in certificates)
        percentageUsed = round((totalBytesUsed / self.quotaBytes) * 100, 2)
        isNearLimit = percentageUsed >= 90
        isOverLimit = totalBytesUsed > self.quotaBytes

        summary: StorageUsageSummary = {
            "totalBytesUsed": totalBytesUsed,
            "quotaBytes": self.quotaBytes,
            "percentageUsed": percentageUsed,
            "isNearLimit": isNearLimit,
            "isOverLimit": isOverLimit,
        }

        self._recordNearLimitEventIfNeeded(userId=userId, summary=summary)
        return summary

    def _recordNearLimitEventIfNeeded(self, userId: int, summary: StorageUsageSummary) -> None:
        if self.rf09Service is None:
            return

        if summary["isNearLimit"]:
            if userId in self._usersAlreadyWarned:
                return

            self.rf09Service.recordEvent(
                eventType="storage_quota_near_limit",
                result="warning",
                userId=userId,
                metadata={
                    "percentageUsed": summary["percentageUsed"],
                    "totalBytesUsed": summary["totalBytesUsed"],
                    "quotaBytes": summary["quotaBytes"],
                    "isOverLimit": summary["isOverLimit"],
                },
            )
            self._usersAlreadyWarned.add(userId)
            return

        self._usersAlreadyWarned.discard(userId)
