from gtd_backend.rf02 import RF02Service


class RF06Service:
    def __init__(self, rf02Service: RF02Service) -> None:
        self.rf02Service = rf02Service

    def changeInboxItemStatus(self, itemId: int, targetStatus: str) -> dict[str, int | str]:
        return self.rf02Service.changeInboxItemStatus(itemId=itemId, targetStatus=targetStatus)

    def listInboxItems(self, status: str | None = None) -> list[dict[str, int | str]]:
        return self.rf02Service.listInboxItems(status=status)
