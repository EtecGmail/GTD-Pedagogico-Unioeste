from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf02 import RF02Service


def test_rf02_service_deve_capturar_e_listar_item_na_caixa_de_entrada() -> None:
    service = RF02Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))

    itemId = service.captureInboxItem(content="Ler capítulo 3 de Didática")

    assert itemId > 0
    assert service.listInboxItems() == [
        {
            "id": itemId,
            "userId": None,
            "content": "Ler capítulo 3 de Didática",
            "status": "inbox",
            "createdAt": "2026-03-26T12:00:00+00:00",
        }
    ]


def test_rf02_service_deve_ordenar_por_criacao_mais_recente() -> None:
    timestamps = iter(
        [
            datetime(2026, 3, 26, 12, 0, tzinfo=UTC),
            datetime(2026, 3, 26, 12, 5, tzinfo=UTC),
        ]
    )
    service = RF02Service(nowProvider=lambda: next(timestamps))

    service.captureInboxItem(content="Item antigo")
    itemRecenteId = service.captureInboxItem(content="Item recente")

    itens = service.listInboxItems()
    assert itens[0]["id"] == itemRecenteId
    assert [item["content"] for item in itens] == ["Item recente", "Item antigo"]


def test_rf02_service_deve_rejeitar_conteudo_invalido() -> None:
    service = RF02Service()

    try:
        service.captureInboxItem(content="   ")
        assert False, "esperava erro para conteúdo vazio"
    except ValueError as error:
        assert str(error) == "conteúdo da captura é obrigatório"


def test_rf02_service_deve_preparar_associacao_por_usuario() -> None:
    service = RF02Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))

    itemUser1 = service.captureInboxItem(content="Ler texto A", userId=1)
    service.captureInboxItem(content="Ler texto B", userId=2)

    itensUser1 = service.listInboxItems(userId=1)

    assert len(itensUser1) == 1
    assert itensUser1[0]["id"] == itemUser1
    assert itensUser1[0]["userId"] == 1


def test_rf02_http_deve_capturar_e_listar_itens_da_caixa_de_entrada() -> None:
    app = createApp()
    client = TestClient(app)

    respostaCaptura = client.post(
        "/rf02/inbox-items",
        json={"content": "Separar leitura para sexta-feira"},
    )

    assert respostaCaptura.status_code == 201
    itemId = respostaCaptura.json()["id"]

    respostaListagem = client.get("/rf02/inbox-items")
    assert respostaListagem.status_code == 200

    itens = respostaListagem.json()
    assert len(itens) == 1
    assert itens[0]["id"] == itemId
    assert itens[0]["content"] == "Separar leitura para sexta-feira"
    assert itens[0]["status"] == "inbox"
    assert "createdAt" in itens[0]


def test_rf02_http_deve_rejeitar_payload_invalido_ou_incompleto() -> None:
    app = createApp()
    client = TestClient(app)

    payloadIncompleto = client.post("/rf02/inbox-items", json={})
    assert payloadIncompleto.status_code == 422

    payloadInvalido = client.post(
        "/rf02/inbox-items",
        json={"content": "", "campoExtra": True},
    )
    assert payloadInvalido.status_code == 422
