import sqlite3

import pytest

from gtd_backend.auth import (
    AuthService,
    AuthResult,
    CREDENCIAIS_INVALIDAS,
    EMAIL_JA_CADASTRADO,
    DuplicateEmailError,
)


def test_deve_retornar_erro_generico_quando_usuario_nao_existe() -> None:
    auth = AuthService()

    resultado = auth.login("inexistente@unioeste.br", "senha-qualquer")

    assert resultado == AuthResult(success=False, message=CREDENCIAIS_INVALIDAS)


def test_deve_retornar_erro_generico_quando_senha_esta_incorreta() -> None:
    auth = AuthService()
    auth.register_user("aluna@unioeste.br", "SenhaForte123")

    resultado = auth.login("aluna@unioeste.br", "senha-invalida")

    assert resultado == AuthResult(success=False, message=CREDENCIAIS_INVALIDAS)


def test_deve_autenticar_quando_credenciais_estao_corretas() -> None:
    auth = AuthService()
    auth.register_user("aluna@unioeste.br", "SenhaForte123")

    resultado = auth.login("aluna@unioeste.br", "SenhaForte123")

    assert resultado == AuthResult(success=True, message="login realizado com sucesso")


def test_deve_armazenar_hash_em_argon2id() -> None:
    auth = AuthService()
    user_id = auth.register_user("seguranca@unioeste.br", "SenhaForte123")

    hash_senha = auth.get_password_hash(user_id)

    assert hash_senha.startswith("$argon2id$")


def test_deve_usar_hash_falso_quando_usuario_nao_existe() -> None:
    auth = AuthService()
    hashesVerificados: list[str] = []

    class FakeHasher:
        def verify(self, passwordHash: str, plainPassword: str) -> bool:
            hashesVerificados.append(passwordHash)
            return False

    auth.passwordHasher = FakeHasher()

    auth.login("naoexiste@unioeste.br", "SenhaQualquer123")

    assert hashesVerificados == [auth.dummyHash]


def test_deve_atualizar_hash_e_permitir_login_com_nova_senha() -> None:
    auth = AuthService()
    userId = auth.register_user("troca@unioeste.br", "SenhaAntiga123")
    hashAntigo = auth.get_password_hash(userId)

    auth.updatePassword(userId, "SenhaNova123")

    hashNovo = auth.get_password_hash(userId)
    loginComNovaSenha = auth.login("troca@unioeste.br", "SenhaNova123")
    loginComSenhaAntiga = auth.login("troca@unioeste.br", "SenhaAntiga123")

    assert hashNovo != hashAntigo
    assert hashNovo.startswith("$argon2id$")
    assert loginComNovaSenha == AuthResult(success=True, message="login realizado com sucesso")
    assert loginComSenhaAntiga == AuthResult(success=False, message=CREDENCIAIS_INVALIDAS)


def test_deve_retornar_erro_de_dominio_quando_email_ja_cadastrado() -> None:
    auth = AuthService()
    auth.register_user("duplicado@unioeste.br", "SenhaForte123")

    with pytest.raises(DuplicateEmailError) as erro:
        auth.register_user("duplicado@unioeste.br", "SenhaForte123")

    assert str(erro.value) == EMAIL_JA_CADASTRADO


def test_nao_deve_propagar_sqlite_integrity_error_no_cadastro_duplicado() -> None:
    auth = AuthService()
    auth.register_user("infra@unioeste.br", "SenhaForte123")

    with pytest.raises(Exception) as erro:
        auth.register_user("infra@unioeste.br", "SenhaForte123")

    assert isinstance(erro.value, DuplicateEmailError)
    assert not isinstance(erro.value, sqlite3.IntegrityError)
