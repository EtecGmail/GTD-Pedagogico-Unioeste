from gtd_backend.rf04 import RF04Service


class RF05Service:
    def __init__(self, rf04Service: RF04Service, defaultTargetHours: int = 200) -> None:
        self.rf04Service = rf04Service
        self.defaultTargetHours = defaultTargetHours
        self._validateTargetHours(self.defaultTargetHours)

    def _validateTargetHours(self, targetHours: int) -> None:
        if targetHours <= 0:
            raise ValueError("meta de horas deve ser maior que zero")

    def getAccHoursProgress(
        self,
        targetHours: int | None = None,
        userId: int | None = None,
    ) -> dict[str, int | float | bool]:
        resolvedTargetHours = targetHours if targetHours is not None else self.defaultTargetHours
        self._validateTargetHours(resolvedTargetHours)

        certificates = self.rf04Service.listCertificates(userId=userId)
        totalHours = sum(
            int(certificate["hours"])
            for certificate in certificates
            if certificate["hours"] is not None
        )
        remainingHours = max(resolvedTargetHours - totalHours, 0)
        percentage = min((totalHours / resolvedTargetHours) * 100, 100)

        return {
            "totalHours": totalHours,
            "targetHours": resolvedTargetHours,
            "remainingHours": remainingHours,
            "percentage": round(percentage, 2),
            "isCompleted": totalHours >= resolvedTargetHours,
        }
