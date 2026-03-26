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
| AUTH-EDGE-HARDEN | Endurecer borda pública do `POST /auth/login` (rate limit, logs e validações complementares) | done | Codex | Rate limit 429 com abstração testável (`RateLimiter`), logging minimizado (`email_hash`) e validação `extra="forbid"`. |
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

- **26/03/2026 (auth/hardening)** – Endurecimento da borda pública de autenticação via TDD. Primeiro foram escritos testes para abstração de rate limit e para o endpoint (`POST /auth/login`) cobrindo bloqueio por excesso de tentativas (status `429`), preservação do login blindado e logs de segurança sem vazamento de senha/e-mail bruto. Implementada abstração `RateLimiter` com `MemoryRateLimiter` (storage substituível), chave de limitação por IP + hash reduzido de e-mail e validação de payload com `extra="forbid"`. Decisão técnica documentada: honeypot não é apropriado para API JSON pura (mais útil em formulários HTML para bots de preenchimento). Suíte final: `12 passed`.

### Arquivos modificados no ciclo atual
- `src/gtd_backend/http.py`
- `tests/test_auth_http.py`
- `PLAN.md`
- `STATE.md`

### Comandos executados e resultados
- `poetry run pytest -q` (falha esperada no ciclo TDD após criação dos testes: `ImportError: cannot import name 'MemoryRateLimiter'`).
- `poetry run pytest -q` (sucesso após implementação incremental: `12 passed`).

### Problemas/riscos remanescentes
- `MemoryRateLimiter` em memória não compartilha estado entre múltiplas instâncias/processos; para produção distribuída será necessário backend centralizado (ex.: Redis).
- Identificação por IP pode sofrer efeitos de NAT/proxy; pode exigir ajuste com headers confiáveis em ambiente com reverse proxy.
- Logs minimizados (hash parcial de e-mail) equilibram privacidade e rastreabilidade, mas reduzem contexto investigativo bruto.

### Próximos passos
- Evoluir `RateLimiter` para armazenamento compartilhado mantendo a mesma interface, sem refatorar o endpoint.
- Introduzir gerenciamento de sessão/token com rotação segura e testes de segurança associados.
- Iniciar implementação dos RFs de domínio (RF-01 e RF-02) mantendo cobertura de testes >90%.
