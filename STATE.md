# STATE.md

Este arquivo acompanha o status das tarefas do projeto **GTD Pedagógico Unioeste**. Atualize-o a cada ciclo de trabalho para registrar progresso, decisões e novos problemas. Use as seguintes categorias de status: **`todo`**, **`in-progress`**, **`review`**, **`done`**, **`blocked`**.

## Tarefas

| ID | Descrição | Status | Responsável | Observações |
|---|-----------|--------|-------------|------------|
| SETUP-REPO | Inicializar repositório, criar estrutura de pastas e adicionar documentos (`PROJECT_CONTEXT.md`, `AGENTS.md`, `PLAN.md`, `STATE.md`) | in-progress | Codex | Estrutura Python inicial criada (`src/`, `tests/`, `pyproject.toml`). |
| STACK-DECISION | Escolher stack tecnológica (frontend, backend, banco, testes) | done | Codex | Definida stack base: Python 3.12 + pytest + Argon2id; PostgreSQL em produção e SQLite para testes. |
| ENV-CONFIG | Configurar ambientes Codex (`default-dev`, `web-research`), variáveis e secrets | done | Codex | `poetry install --with dev,test` validado com sucesso neste ambiente controlado. |
| AUTH-SECURITY | Implementar autenticação com Argon2id e login blindado | done | Codex | Login blindado com mensagem genérica e mitigação de timing attack preservados. |
| AUTH-HTTP | Implementar camada HTTP mínima de autenticação com FastAPI | done | Codex | Endpoint `POST /auth/login` implementado via TDD reutilizando `AuthService`. |
| RF-01 | Cadastro de disciplinas e professores (testes + implementação) | todo | — | — |
| RF-02 | Caixa de Entrada (testes + implementação) | todo | — | — |
| RF-03 | Fatiador de leituras (testes + implementação) | todo | — | — |
| RF-04 | Cofre de ACCs (upload criptografado) | todo | — | — |
| RF-05 | Barra de progresso das horas acumuladas | todo | — | — |
| RF-06 | Categorização em "Próximas Ações" e "Aguardando" | todo | — | — |
| RF-07 | Recuperação de senha via e‑mail | todo | — | — |
| RF-08 | Gráficos de avanço das leituras | todo | — | — |
| RF-09 | Log de eventos de segurança | todo | — | — |
| RF-10 | Alerta de 90 % de cota de armazenamento | todo | — | — |
| DOC-UPDATE | Manter documentos atualizados com mudanças e decisões | in-progress | Codex | `STATE.md` atualizado neste ciclo com validações e implementação HTTP mínima. |

## Histórico

Registre nesta seção um resumo curto de cada ciclo de trabalho: data, tarefas concluídas, dificuldades, resultados de testes e próximos passos.

- **25/03/2026** – Início do projeto. Documentos de contexto e plano preparados. Aguardando definição de stack tecnológica.
- **26/03/2026** – Início da Fase 2 (Fundação): stack base definida e estrutura mínima de backend proposta; autenticação inicial implementada com `Argon2id` e login blindado via TDD. Testes criados antes da implementação e aprovados (`4 passed`).
- **26/03/2026 (ajuste)** – Mitigação de timing attack no login: adicionado `dummyHash` Argon2id para verificar senha mesmo quando usuário não existe, mantendo resposta genérica (`credenciais inválidas`). Novo teste TDD incluído e suíte passou (`5 passed`).
- **26/03/2026 (infra/poetry)** – Estabilização da configuração do Poetry: incluído `package-mode = false` para impedir falha de instalação do projeto raiz sem pacote instalado e criados grupos `dev` e `test` em `tool.poetry.group.*` para compatibilidade com `poetry install --with dev,test`. `poetry lock` atualizado com sucesso. Instalação de dependências e execução de testes ficaram bloqueadas por falha de conectividade com `files.pythonhosted.org`.
- **26/03/2026 (auth/http)** – Ambiente validado com sucesso (`poetry install --with dev,test` e `poetry run pytest`). Em seguida, foi implementada camada HTTP mínima com FastAPI usando TDD: novos testes para `POST /auth/login` criados antes da implementação, cobrindo credenciais válidas, resposta cega para usuário inexistente/senha incorreta e validação explícita de entrada. Ajuste técnico aplicado no SQLite em memória (`check_same_thread=False`) para compatibilidade com execução em thread no `TestClient`. Suíte final: `8 passed`.

### Arquivos modificados no ciclo atual
- `pyproject.toml`
- `poetry.lock`
- `src/gtd_backend/auth.py`
- `src/gtd_backend/http.py`
- `tests/test_auth_http.py`
- `STATE.md`

### Comandos executados e resultados
- `poetry install --with dev,test` (sucesso, sem pendências de instalação neste ambiente).
- `poetry run pytest` (sucesso inicial, `5 passed`).
- `poetry run pytest` (falha esperada em TDD após criar testes HTTP, `ModuleNotFoundError: No module named 'fastapi'`).
- `poetry add fastapi` (sucesso, dependência mínima da camada HTTP adicionada e lock atualizado).
- `poetry run pytest` (falha esperada em TDD, `starlette.testclient` exigiu `httpx`).
- `poetry add --group test httpx` (sucesso, dependência de teste adicionada e lock atualizado).
- `poetry run pytest` (falha esperada em TDD após implementação inicial HTTP, erro de thread no SQLite: `check_same_thread`).
- `poetry run pytest` (sucesso após ajuste técnico no SQLite, `8 passed in 5.64s`).

### Problemas/riscos remanescentes
- Endpoint público de login ainda sem rate limit e sem honeypot; permanece risco de abuso por força bruta.
- Persistência segue em SQLite em memória no serviço atual; será necessário evoluir para repositório persistente (SQLite arquivo/PostgreSQL) em próximas iterações.
- Ainda não há emissão de token/sessão após login; no momento a camada HTTP apenas valida credenciais.

### Próximos passos
- Adicionar proteção anti-abuso no `POST /auth/login` (rate limit + estratégia de honeypot para formulários públicos).
- Introduzir gerenciamento de sessão/token com rotação segura e testes de segurança associados.
- Iniciar implementação dos RFs de domínio (RF-01 e RF-02) mantendo cobertura de testes >90%.
