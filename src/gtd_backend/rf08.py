from gtd_backend.rf03 import RF03Service
from gtd_backend.rf05 import RF05Service
from gtd_backend.rf06 import RF06Service


class RF08Service:
    def __init__(
        self,
        rf03Service: RF03Service,
        rf05Service: RF05Service,
        rf06Service: RF06Service,
    ) -> None:
        self.rf03Service = rf03Service
        self.rf05Service = rf05Service
        self.rf06Service = rf06Service

    def _buildStatusCounts(self) -> dict[str, int]:
        inboxItems = self.rf06Service.listInboxItems(status="inbox")
        nextActionItems = self.rf06Service.listInboxItems(status="next_action")
        waitingItems = self.rf06Service.listInboxItems(status="waiting")

        return {
            "inbox": len(inboxItems),
            "nextAction": len(nextActionItems),
            "waiting": len(waitingItems),
        }

    def _buildReadingSummary(self) -> dict[str, int | float]:
        plans = self.rf03Service.listReadingPlans()
        if not plans:
            return {
                "totalPlans": 0,
                "overloadedPlans": 0,
                "completedPlans": 0,
                "totalPages": 0,
                "remainingPages": 0,
                "averageCompletionPercentage": 0.0,
            }

        totalPlans = len(plans)
        overloadedPlans = sum(1 for plan in plans if bool(plan["isOverloaded"]))
        completedPlans = sum(1 for plan in plans if int(plan["remainingPages"]) == 0)
        totalPages = sum(int(plan["totalPages"]) for plan in plans)
        remainingPages = sum(int(plan["remainingPages"]) for plan in plans)
        readPages = totalPages - remainingPages
        averageCompletionPercentage = round((readPages / totalPages) * 100, 2) if totalPages > 0 else 0.0

        return {
            "totalPlans": totalPlans,
            "overloadedPlans": overloadedPlans,
            "completedPlans": completedPlans,
            "totalPages": totalPages,
            "remainingPages": remainingPages,
            "averageCompletionPercentage": averageCompletionPercentage,
        }

    def getStudentDashboard(self, targetHours: int | None = None) -> dict[str, dict]:
        return {
            "statusCounts": self._buildStatusCounts(),
            "accProgress": self.rf05Service.getAccHoursProgress(targetHours=targetHours),
            "readingSummary": self._buildReadingSummary(),
        }
