from fastapi.testclient import TestClient

from gtd_backend.http import createApp
from gtd_backend.rf01 import RF01Service


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

    respostaProfessor = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
    )
    assert respostaProfessor.status_code == 201
    professorId = respostaProfessor.json()["id"]

    respostaDisciplina = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101", "professorIds": [professorId]},
    )
    assert respostaDisciplina.status_code == 201

    listagemProfessores = client.get("/rf01/professors")
    assert listagemProfessores.status_code == 200
    assert listagemProfessores.json() == [
        {"id": professorId, "name": "Maria Silva", "email": "maria@unioeste.br"}
    ]

    listagemDisciplinas = client.get("/rf01/disciplines")
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

    respostaPayloadInvalido = client.post(
        "/rf01/disciplines",
        json={"name": "A", "code": "", "campoExtra": True},
    )
    assert respostaPayloadInvalido.status_code == 422

    respostaProfessor = client.post(
        "/rf01/professors",
        json={"name": "Maria Silva", "email": "maria@unioeste.br"},
    )
    assert respostaProfessor.status_code == 201

    primeiraDisciplina = client.post(
        "/rf01/disciplines",
        json={"name": "Didática", "code": "PED101"},
    )
    assert primeiraDisciplina.status_code == 201

    respostaDuplicidade = client.post(
        "/rf01/disciplines",
        json={"name": "didática", "code": "PED101"},
    )
    assert respostaDuplicidade.status_code == 400
    assert respostaDuplicidade.json() == {
        "success": False,
        "message": "disciplina já cadastrada",
    }

    respostaRelacaoInexistente = client.post(
        "/rf01/disciplines",
        json={"name": "Currículo", "code": "PED102", "professorIds": [999]},
    )
    assert respostaRelacaoInexistente.status_code == 400
    assert respostaRelacaoInexistente.json() == {
        "success": False,
        "message": "professor informado não existe",
    }
