# STATE.md

Este arquivo acompanha o status das tarefas do projeto **GTD Pedagógico Unioeste**. Atualize-o a cada ciclo de trabalho para registrar progresso, decisões e novos problemas. Use as seguintes categorias de status: **`todo`**, **`in-progress`**, **`review`**, **`done`**, **`blocked`**.

## Tarefas

| ID | Descrição | Status | Responsável | Observações |
|---|-----------|--------|-------------|------------|
| SETUP-REPO | Inicializar repositório, criar estrutura de pastas e adicionar documentos (`PROJECT_CONTEXT.md`, `AGENTS.md`, `PLAN.md`, `STATE.md`) | in-progress | Codex | Estrutura Python inicial criada (`src/`, `tests/`, `pyproject.toml`). |
| STACK-DECISION | Escolher stack tecnológica (frontend, backend, banco, testes) | done | Codex | Definida stack base: Python 3.12 + pytest + Argon2id; PostgreSQL em produção e SQLite para testes. |
| ENV-CONFIG | Configurar ambientes Codex (`default-dev`, `web-research`), variáveis e secrets | todo | — | — |
| AUTH-SECURITY | Implementar autenticação com Argon2id e login blindado | done | Codex | Testes TDD implementados e aprovados com mensagens genéricas de erro. |
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
| DOC-UPDATE | Manter documentos atualizados com mudanças e decisões | in-progress | Codex | `PLAN.md` e `STATE.md` atualizados neste ciclo. |

## Histórico

Registre nesta seção um resumo curto de cada ciclo de trabalho: data, tarefas concluídas, dificuldades, resultados de testes e próximos passos.

- **25/03/2026** – Início do projeto. Documentos de contexto e plano preparados. Aguardando definição de stack tecnológica.
- **26/03/2026** – Início da Fase 2 (Fundação): stack base definida e estrutura mínima de backend proposta; autenticação inicial implementada com `Argon2id` e login blindado via TDD. Testes criados antes da implementação e aprovados (`4 passed`).
- **26/03/2026 (ajuste)** – Mitigação de timing attack no login: adicionado `dummyHash` Argon2id para verificar senha mesmo quando usuário não existe, mantendo resposta genérica (`credenciais inválidas`). Novo teste TDD incluído e suíte passou (`5 passed`).

### Arquivos modificados no ciclo atual
- `pyproject.toml`
- `src/gtd_backend/__init__.py`
- `src/gtd_backend/auth.py`
- `tests/test_auth.py`
- `PLAN.md`
- `STATE.md`

### Comandos executados e resultados
- `pytest -q` (falhou inicialmente por ausência do pacote `gtd_backend` durante etapa vermelha do TDD).
- `python -m pip install -e '.[dev]'` (sucesso, dependências instaladas).
- `pytest` (sucesso, `4 passed in 1.28s`).
- `pytest -q` (falha no novo teste TDD antes da implementação do `dummyHash`).
- `pytest -q` (sucesso após implementação, `5 passed`).

### Problemas/riscos remanescentes
- Ainda não há camada HTTP (API) para autenticação.
- Ainda não há rate limit/honeypot para endpoint público de login.
- Persistência ainda em SQLite em memória no serviço atual; migração para PostgreSQL será necessária nas próximas iterações.
