from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf02 import RF02Service
from gtd_backend.rf06 import RF06Service


def test_rf06_service_deve_mover_item_de_inbox_para_next_action() -> None:
    rf02Service = RF02Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))
    rf06Service = RF06Service(rf02Service=rf02Service)
    itemId = rf02Service.captureInboxItem(content="Planejar resumo de metodologia")

    updatedItem = rf06Service.changeInboxItemStatus(itemId=itemId, targetStatus="next_action")

    assert updatedItem["id"] == itemId
    assert updatedItem["status"] == "next_action"


def test_rf06_service_deve_mover_item_de_inbox_para_waiting() -> None:
    rf02Service = RF02Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))
    rf06Service = RF06Service(rf02Service=rf02Service)
    itemId = rf02Service.captureInboxItem(content="Aguardar retorno da coordenação")

    updatedItem = rf06Service.changeInboxItemStatus(itemId=itemId, targetStatus="waiting")

    assert updatedItem["id"] == itemId
    assert updatedItem["status"] == "waiting"


def test_rf06_service_deve_rejeitar_transicao_invalida() -> None:
    rf02Service = RF02Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))
    rf06Service = RF06Service(rf02Service=rf02Service)
    itemId = rf02Service.captureInboxItem(content="Definir leitura da semana")

    rf06Service.changeInboxItemStatus(itemId=itemId, targetStatus="next_action")

    try:
        rf06Service.changeInboxItemStatus(itemId=itemId, targetStatus="waiting")
        assert False, "esperava erro para transição inválida"
    except ValueError as error:
        assert str(error) == "transição de status inválida"


def test_rf06_service_deve_rejeitar_item_inexistente() -> None:
    rf06Service = RF06Service(rf02Service=RF02Service())

    try:
        rf06Service.changeInboxItemStatus(itemId=999, targetStatus="next_action")
        assert False, "esperava erro para item inexistente"
    except LookupError as error:
        assert str(error) == "item da caixa de entrada não encontrado"


def test_rf06_service_deve_listar_itens_por_status() -> None:
    timestamps = iter(
        [
            datetime(2026, 3, 26, 12, 0, tzinfo=UTC),
            datetime(2026, 3, 26, 12, 5, tzinfo=UTC),
        ]
    )
    rf02Service = RF02Service(nowProvider=lambda: next(timestamps))
    rf06Service = RF06Service(rf02Service=rf02Service)

    itemInboxId = rf02Service.captureInboxItem(content="Item inbox")
    itemWaitingId = rf02Service.captureInboxItem(content="Item waiting")
    rf06Service.changeInboxItemStatus(itemId=itemWaitingId, targetStatus="waiting")

    inboxItems = rf06Service.listInboxItems(status="inbox")
    waitingItems = rf06Service.listInboxItems(status="waiting")

    assert [item["id"] for item in inboxItems] == [itemInboxId]
    assert [item["id"] for item in waitingItems] == [itemWaitingId]


def test_rf06_http_deve_mudar_status_para_next_action() -> None:
    app = createApp()
    client = TestClient(app)

    captureResponse = client.post("/rf02/inbox-items", json={"content": "Ler texto de avaliação"})
    itemId = captureResponse.json()["id"]

    updateResponse = client.patch(
        f"/rf06/inbox-items/{itemId}/status",
        json={"status": "next_action"},
    )

    assert updateResponse.status_code == 200
    assert updateResponse.json() == {"id": itemId, "status": "next_action"}


def test_rf06_http_deve_mudar_status_para_waiting() -> None:
    app = createApp()
    client = TestClient(app)

    captureResponse = client.post("/rf02/inbox-items", json={"content": "Aguardar confirmação de estágio"})
    itemId = captureResponse.json()["id"]

    updateResponse = client.patch(
        f"/rf06/inbox-items/{itemId}/status",
        json={"status": "waiting"},
    )

    assert updateResponse.status_code == 200
    assert updateResponse.json() == {"id": itemId, "status": "waiting"}


def test_rf06_http_deve_listar_por_status() -> None:
    app = createApp()
    client = TestClient(app)

    inboxItem = client.post("/rf02/inbox-items", json={"content": "Item inbox"}).json()["id"]
    waitingItem = client.post("/rf02/inbox-items", json={"content": "Item waiting"}).json()["id"]

    client.patch(f"/rf06/inbox-items/{waitingItem}/status", json={"status": "waiting"})

    inboxResponse = client.get("/rf06/inbox-items", params={"status": "inbox"})
    waitingResponse = client.get("/rf06/inbox-items", params={"status": "waiting"})

    assert inboxResponse.status_code == 200
    assert waitingResponse.status_code == 200
    assert [item["id"] for item in inboxResponse.json()] == [inboxItem]
    assert [item["id"] for item in waitingResponse.json()] == [waitingItem]


def test_rf06_http_deve_rejeitar_item_inexistente() -> None:
    app = createApp()
    client = TestClient(app)

    response = client.patch(
        "/rf06/inbox-items/999/status",
        json={"status": "next_action"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "message": "item da caixa de entrada não encontrado",
    }


def test_rf06_http_deve_rejeitar_payload_invalido() -> None:
    app = createApp()
    client = TestClient(app)

    captureResponse = client.post("/rf02/inbox-items", json={"content": "Organizar tarefas"})
    itemId = captureResponse.json()["id"]

    payloadInvalido = client.patch(
        f"/rf06/inbox-items/{itemId}/status",
        json={"status": "invalid", "extra": True},
    )
    payloadIncompleto = client.patch(f"/rf06/inbox-items/{itemId}/status", json={})

    assert payloadInvalido.status_code == 422
    assert payloadIncompleto.status_code == 422
