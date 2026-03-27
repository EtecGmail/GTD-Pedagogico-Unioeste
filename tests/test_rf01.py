from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf01 import RF01Service


def _autenticarUsuario(client: TestClient, app, email: str) -> dict[str, str]:
    app.state.authService.register_user(email, "SenhaForte123")
    respostaLogin = client.post(
        "/auth/login",
        json={"email": email, "password": "SenhaForte123"},
    )
    token = respostaLogin.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_rf01_service_deve_cadastrar_e_listar_disciplinas() -> None:
    service = RF01Service()

    disciplinaId = service.createDiscipline(name="Didática", code="PED101")

    assert disciplinaId > 0
    assert service.listDisciplines() == [
        {
            "id": disciplinaId,
            "name": "Didática",
            "code": "PED101",
            "professorIds": [],
        }
    ]


def test_rf01_service_deve_cadastrar_e_listar_professores() -> None:
    service = RF01Service()

    professorId = service.createProfessor(name="Maria Silva", email="maria@unioeste.br")

    assert professorId > 0
    assert service.listProfessors() == [
        {
            "id": professorId,
            "name": "Maria Silva",
            "email": "maria@unioeste.br",
        }
    ]


def test_rf01_service_deve_rejeitar_duplicidades_de_disciplina_e_professor() -> None:
    service = RF01Service()

    service.createDiscipline(name="Didática", code="PED101")
    service.createProfessor(name="Maria Silva", email="maria@unioeste.br")

    try:
        service.createDiscipline(name="didática", code="PED101")
        assert False, "esperava erro de duplicidade para disciplina"
    except ValueError as error:
        assert str(error) == "disciplina já cadastrada"

    try:
        service.createProfessor(name="maria silva", email="maria@unioeste.br")
        assert False, "esperava erro de duplicidade para professor"
    except ValueError as error:
        assert str(error) == "professor já cadastrado"


def test_rf01_service_deve_aplicar_ownership_e_duplicidade_por_usuario() -> None:
    service = RF01Service()

    professorUserA = service.createProfessor(
        name="Maria Silva",
        email="maria@unioeste.br",
        userId=1,
    )
    disciplineUserA = service.createDiscipline(
        name="Didática",
        code="PED101",
        professorIds=[professorUserA],
        userId=1,
    )

    professorUserB = service.createProfessor(
        name="Maria Silva",
        email="maria@unioeste.br",
        userId=2,
    )
    disciplineUserB = service.createDiscipline(
        name="Didática",
        code="PED101",
        professorIds=[professorUserB],
        userId=2,
    )

    assert [professor["id"] for professor in service.listProfessors(userId=1)] == [professorUserA]
    assert [professor["id"] for professor in service.listProfessors(userId=2)] == [professorUserB]
    assert [discipline["id"] for discipline in service.listDisciplines(userId=1)] == [disciplineUserA]
    assert [discipline["id"] for discipline in service.listDisciplines(userId=2)] == [disciplineUserB]

    try:
        service.createProfessor(name="Maria Silva", email="maria@unioeste.br", userId=1)
        assert False, "esperava erro de duplicidade no mesmo usuário"
    except ValueError as error:
        assert str(error) == "professor já cadastrado"

    try:
        service.createDiscipline(name="Didática", code="PED101", userId=1)
        assert False, "esperava erro de duplicidade no mesmo usuário"
    except ValueError as error:
        assert str(error) == "disciplina já cadastrada"


def test_rf01_service_deve_vincular_professor_em_disciplina() -> None:
    service = RF01Service()
    professorId = service.createProfessor(name="Maria Silva", email="maria@unioeste.br")
    disciplinaId = service.createDiscipline(
        name="Didática", code="PED101", professorIds=[professorId]
    )

    assert service.listDisciplines() == [
        {
            "id": disciplinaId,
            "name": "Didática",
            "code": "PED101",
            "professorIds": [professorId],
        }
    ]


def test_rf01_http_deve_cadastrar_e_listar_registros() -> None:
    app = createApp()
    client = TestClient(app)
    headers = _autenticarUsuario(client=client, app=app, email="aluna@unioeste.br")

    respostaProfessor = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
        headers=headers,
    )
    assert respostaProfessor.status_code == 201
    professorId = respostaProfessor.json()["id"]

    respostaDisciplina = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101", "professorIds": [professorId]},
        headers=headers,
    )
    assert respostaDisciplina.status_code == 201

    listagemProfessores = client.get("/rf01/professors", headers=headers)
    assert listagemProfessores.status_code == 200
    assert listagemProfessores.json() == [
        {"id": professorId, "name": "Maria Silva", "email": "maria@unioeste.br"}
    ]

    listagemDisciplinas = client.get("/rf01/disciplines", headers=headers)
    assert listagemDisciplinas.status_code == 200
    assert listagemDisciplinas.json() == [
        {
            "id": respostaDisciplina.json()["id"],
            "name": "Didática",
            "code": "PED101",
            "professorIds": [professorId],
        }
    ]


def test_rf01_http_deve_rejeitar_payload_invalido_duplicidade_e_relacao_inexistente() -> None:
    app = createApp()
    client = TestClient(app)
    headers = _autenticarUsuario(client=client, app=app, email="aluna@unioeste.br")

    respostaPayloadInvalido = client.post(
        "/rf01/disciplines",
        json={"name": "A", "code": "", "campoExtra": True},
        headers=headers,
    )
    assert respostaPayloadInvalido.status_code == 422

    respostaProfessor = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
        headers=headers,
    )
    assert respostaProfessor.status_code == 201

    primeiraDisciplina = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101"},
        headers=headers,
    )
    assert primeiraDisciplina.status_code == 201

    respostaDuplicidade = client.post(
        "/rf01/disciplines",
        json={"name": "didática", "code": "PED101"},
        headers=headers,
    )
    assert respostaDuplicidade.status_code == 400
    assert respostaDuplicidade.json() == {
        "success": False,
        "message": "disciplina já cadastrada",
    }

    respostaRelacaoInexistente = client.post(
        "/rf01/disciplines",
        json={"name": "Currículo", "code": "PED102", "professorIds": [999]},
        headers=headers,
    )
    assert respostaRelacaoInexistente.status_code == 400
    assert respostaRelacaoInexistente.json() == {
        "success": False,
        "message": "professor informado não existe",
    }


def test_rf01_http_deve_rejeitar_requisicoes_sem_autenticacao() -> None:
    app = createApp()
    client = TestClient(app)

    assert client.get("/rf01/professors").status_code == 401
    assert client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
    ).status_code == 401
    assert client.get("/rf01/disciplines").status_code == 401
    assert client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101"},
    ).status_code == 401


def test_rf01_http_deve_isolar_professores_disciplinas_e_vinculos_por_usuario() -> None:
    app = createApp()
    client = TestClient(app)
    headersUserA = _autenticarUsuario(client=client, app=app, email="a@unioeste.br")
    headersUserB = _autenticarUsuario(client=client, app=app, email="b@unioeste.br")

    professorA = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
        headers=headersUserA,
    ).json()["id"]
    professorB = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
        headers=headersUserB,
    ).json()["id"]

    disciplinaA = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101", "professorIds": [professorA]},
        headers=headersUserA,
    )
    disciplinaB = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101", "professorIds": [professorB]},
        headers=headersUserB,
    )

    assert disciplinaA.status_code == 201
    assert disciplinaB.status_code == 201

    listagemProfessoresA = client.get("/rf01/professors", headers=headersUserA)
    listagemProfessoresB = client.get("/rf01/professors", headers=headersUserB)
    assert [professor["id"] for professor in listagemProfessoresA.json()] == [professorA]
    assert [professor["id"] for professor in listagemProfessoresB.json()] == [professorB]

    listagemDisciplinasA = client.get("/rf01/disciplines", headers=headersUserA)
    listagemDisciplinasB = client.get("/rf01/disciplines", headers=headersUserB)
    assert [disciplina["professorIds"] for disciplina in listagemDisciplinasA.json()] == [[professorA]]
    assert [disciplina["professorIds"] for disciplina in listagemDisciplinasB.json()] == [[professorB]]


def test_rf01_http_deve_rejeitar_vinculo_com_professor_de_outro_usuario() -> None:
    app = createApp()
    client = TestClient(app)
    headersUserA = _autenticarUsuario(client=client, app=app, email="a@unioeste.br")
    headersUserB = _autenticarUsuario(client=client, app=app, email="b@unioeste.br")

    professorUserA = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
        headers=headersUserA,
    ).json()["id"]

    respostaVinculoInvalido = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101", "professorIds": [professorUserA]},
        headers=headersUserB,
    )

    assert respostaVinculoInvalido.status_code == 400
    assert respostaVinculoInvalido.json() == {
        "success": False,
        "message": "professor informado não existe",
    }
