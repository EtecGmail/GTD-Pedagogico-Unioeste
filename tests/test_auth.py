from gtd_backend.auth import AuthService, AuthResult, CREDENCIAIS_INVALIDAS


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
