from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf03 import RF03Service


def test_rf03_service_deve_calcular_meta_diaria_com_arredondamento_para_cima() -> None:
    service = RF03Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))

    planId = service.createReadingPlan(totalPages=101, deadlineDays=10)

    plans = service.listReadingPlans()
    assert planId > 0
    assert plans == [
        {
            "id": planId,
            "totalPages": 101,
            "deadlineDays": 10,
            "dailyGoal": 11,
            "isOverloaded": False,
            "remainingPages": 101,
            "createdAt": "2026-03-26T12:00:00+00:00",
        }
    ]


def test_rf03_service_deve_ativar_sobrecarga_quando_meta_diaria_for_maior_que_30() -> None:
    service = RF03Service()

    planId = service.createReadingPlan(totalPages=620, deadlineDays=20)

    plan = service.listReadingPlans()[0]
    assert plan["id"] == planId
    assert plan["dailyGoal"] == 31
    assert plan["isOverloaded"] is True


def test_rf03_service_deve_rejeitar_valores_zero_negativos_ou_combinacoes_invalidas() -> None:
    service = RF03Service()

    for totalPages, deadlineDays, expectedError in [
        (0, 10, "total de páginas deve ser maior que zero"),
        (-1, 10, "total de páginas deve ser maior que zero"),
        (100, 0, "prazo em dias deve ser maior que zero"),
        (100, -5, "prazo em dias deve ser maior que zero"),
    ]:
        try:
            service.createReadingPlan(totalPages=totalPages, deadlineDays=deadlineDays)
            assert False, "esperava ValueError para combinação inválida"
        except ValueError as error:
            assert str(error) == expectedError


def test_rf03_http_deve_criar_e_listar_plano_de_leitura() -> None:
    app = createApp()
    client = TestClient(app)

    respostaCriacao = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 95, "deadlineDays": 3},
    )

    assert respostaCriacao.status_code == 201
    planId = respostaCriacao.json()["id"]

    respostaListagem = client.get("/rf03/reading-plans")
    assert respostaListagem.status_code == 200

    plans = respostaListagem.json()
    assert len(plans) == 1
    assert plans[0]["id"] == planId
    assert plans[0]["totalPages"] == 95
    assert plans[0]["deadlineDays"] == 3
    assert plans[0]["dailyGoal"] == 32
    assert plans[0]["isOverloaded"] is True
    assert plans[0]["remainingPages"] == 95
    assert "createdAt" in plans[0]


def test_rf03_http_deve_rejeitar_payload_invalido_ou_incompleto() -> None:
    app = createApp()
    client = TestClient(app)

    payloadIncompleto = client.post("/rf03/reading-plans", json={"totalPages": 10})
    assert payloadIncompleto.status_code == 422

    payloadInvalido = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 0, "deadlineDays": -1, "campoExtra": True},
    )
    assert payloadInvalido.status_code == 422
