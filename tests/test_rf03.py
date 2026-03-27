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


def test_rf03_service_deve_listar_e_avancar_apenas_planos_do_usuario() -> None:
    service = RF03Service(nowProvider=lambda: datetime(2026, 3, 26, 12, 0, tzinfo=UTC))
    planUserA = service.createReadingPlan(totalPages=60, deadlineDays=6, userId=1)
    service.createReadingPlan(totalPages=40, deadlineDays=4, userId=2)

    plansUserA = service.listReadingPlans(userId=1)
    assert [plan["id"] for plan in plansUserA] == [planUserA]

    try:
        service.advanceReadingPlan(planId=planUserA, pagesRead=10, userId=2)
        assert False, "esperava erro para acesso a plano de outro usuário"
    except LookupError as error:
        assert str(error) == "plano de leitura não encontrado"


def test_rf03_http_deve_criar_e_listar_plano_de_leitura() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    token = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    respostaCriacao = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 95, "deadlineDays": 3},
        headers=headers,
    )

    assert respostaCriacao.status_code == 201
    planId = respostaCriacao.json()["id"]

    respostaListagem = client.get("/rf03/reading-plans", headers=headers)
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
    app.state.authService.register_user("aluna@unioeste.br", "SenhaForte123")
    token = client.post(
        "/auth/login",
        json={"email": "aluna@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    payloadIncompleto = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 10},
        headers=headers,
    )
    assert payloadIncompleto.status_code == 422

    payloadInvalido = client.post(
        "/rf03/reading-plans",
        json={"totalPages": 0, "deadlineDays": -1, "campoExtra": True},
        headers=headers,
    )
    assert payloadInvalido.status_code == 422


def test_rf03_http_deve_rejeitar_sem_autenticacao_e_restringir_por_ownership() -> None:
    app = createApp()
    client = TestClient(app)
    app.state.authService.register_user("a@unioeste.br", "SenhaForte123")
    app.state.authService.register_user("b@unioeste.br", "SenhaForte123")
    tokenA = client.post(
        "/auth/login",
        json={"email": "a@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    tokenB = client.post(
        "/auth/login",
        json={"email": "b@unioeste.br", "password": "SenhaForte123"},
    ).json()["accessToken"]
    headersA = {"Authorization": f"Bearer {tokenA}"}
    headersB = {"Authorization": f"Bearer {tokenB}"}

    respostaSemToken = client.get("/rf03/reading-plans")
    assert respostaSemToken.status_code == 401

    client.post("/rf03/reading-plans", json={"totalPages": 50, "deadlineDays": 5}, headers=headersA)
    client.post("/rf03/reading-plans", json={"totalPages": 30, "deadlineDays": 3}, headers=headersB)

    respostaA = client.get("/rf03/reading-plans", headers=headersA)
    respostaB = client.get("/rf03/reading-plans", headers=headersB)
    assert len(respostaA.json()) == 1
    assert len(respostaB.json()) == 1
