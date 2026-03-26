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
| RF-01 | Cadastro de disciplinas e professores (testes + implementação) | done | Codex | RF-01 implementado via TDD com serviço dedicado (`RF01Service`) e endpoints mínimos para cadastro/listagem de disciplinas e professores. |
| RF-02 | Caixa de Entrada (testes + implementação) | todo | — | — |
| RF-03 | Fatiador de leituras (testes + implementação) | todo | — | — |
| RF-04 | Cofre de ACCs (upload criptografado) | todo | — | — |
| RF-05 | Barra de progresso das horas acumuladas | todo | — | — |
| RF-06 | Categorização em "Próximas Ações" e "Aguardando" | todo | — | — |
| RF-07 | Recuperação de senha via e‑mail | todo | — | — |
| RF-08 | Gráficos de avanço das leituras | todo | — | — |
| RF-09 | Log de eventos de segurança | todo | — | — |
| RF-10 | Alerta de 90 % de cota de armazenamento | todo | — | — |
| DOC-UPDATE | Manter documentos atualizados com mudanças e decisões | in-progress | Codex | `STATE.md` atualizado neste ciclo com a entrega do RF-01 e validações executadas. |

## Histórico

Registre nesta seção um resumo curto de cada ciclo de trabalho: data, tarefas concluídas, dificuldades, resultados de testes e próximos passos.

- **25/03/2026** – Início do projeto. Documentos de contexto e plano preparados. Aguardando definição de stack tecnológica.
- **26/03/2026** – Início da Fase 2 (Fundação): stack base definida e estrutura mínima de backend proposta; autenticação inicial implementada com `Argon2id` e login blindado via TDD. Testes criados antes da implementação e aprovados (`4 passed`).
- **26/03/2026 (ajuste)** – Mitigação de timing attack no login: adicionado `dummyHash` Argon2id para verificar senha mesmo quando usuário não existe, mantendo resposta genérica (`credenciais inválidas`). Novo teste TDD incluído e suíte passou (`5 passed`).
- **26/03/2026 (infra/poetry)** – Estabilização da configuração do Poetry: incluído `package-mode = false` para impedir falha de instalação do projeto raiz sem pacote instalado e criados grupos `dev` e `test` em `tool.poetry.group.*` para compatibilidade com `poetry install --with dev,test`. `poetry lock` atualizado com sucesso. Instalação de dependências e execução de testes ficaram bloqueadas por falha de conectividade com `files.pythonhosted.org`.
- **26/03/2026 (auth/http)** – Ambiente validado com sucesso (`poetry install --with dev,test` e `poetry run pytest`). Em seguida, foi implementada camada HTTP mínima com FastAPI usando TDD: novos testes para `POST /auth/login` criados antes da implementação, cobrindo credenciais válidas, resposta cega para usuário inexistente/senha incorreta e validação explícita de entrada. Ajuste técnico aplicado no SQLite em memória (`check_same_thread=False`) para compatibilidade com execução em thread no `TestClient`. Suíte final: `8 passed`.

- **26/03/2026 (auth/hardening)** – Endurecimento da borda pública de autenticação via TDD. Primeiro foram escritos testes para abstração de rate limit e para o endpoint (`POST /auth/login`) cobrindo bloqueio por excesso de tentativas (status `429`), preservação do login blindado e logs de segurança sem vazamento de senha/e-mail bruto. Implementada abstração `RateLimiter` com `MemoryRateLimiter` (storage substituível), chave de limitação por IP + hash reduzido de e-mail e validação de payload com `extra="forbid"`. Decisão técnica documentada: honeypot não é apropriado para API JSON pura (mais útil em formulários HTML para bots de preenchimento). Suíte final: `12 passed`.
- **26/03/2026 (fase 3 / rf-01)** – Implementação do RF-01 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para cadastro/listagem de disciplinas e professores, validação explícita, rejeição de payload inválido, bloqueio de duplicidades e validação de vínculo disciplina-professor. Em seguida, foi implementado `RF01Service` com SQLite em memória, normalização de campos e tabela de vínculo (`discipline_professor`) para base sustentável dos próximos módulos. Por fim, endpoints mínimos foram adicionados em FastAPI: `POST/GET /rf01/professors` e `POST/GET /rf01/disciplines`. Suíte final: `18 passed`.

### Arquivos modificados no ciclo atual
- `src/gtd_backend/http.py`
- `src/gtd_backend/rf01.py`
- `tests/test_rf01.py`
- `STATE.md`

### Comandos executados e resultados
- `poetry run pytest -q` (falha esperada no ciclo TDD após criação dos testes: `ModuleNotFoundError: No module named 'gtd_backend.rf01'`).
- `poetry run pytest -q` (sucesso após implementação incremental: `18 passed`).
- `poetry run python -m compileall src` (sucesso: compilação dos módulos sem erro).

### Problemas/riscos remanescentes
- `RF01Service` usa SQLite em memória por instância de aplicação; ao evoluir para ambiente persistente/multi-instância será necessário repositório compartilhado (PostgreSQL).
- A regra de duplicidade de disciplina considera o par (`nome normalizado`, `código normalizado`); se o domínio exigir unicidade global apenas por código, essa regra deve ser ajustada e coberta por testes.
- Ainda não há autenticação/autorização aplicada nos endpoints de RF-01; isso deve ser incluído quando o módulo de sessão/token estiver disponível.

### Próximos passos
- Iniciar RF-02 (Caixa de Entrada) reaproveitando o padrão TDD e validações explícitas utilizado em RF-01.
- Definir camada de persistência compartilhada para evitar múltiplos bancos em memória por serviço conforme avanço da fase 3.
- Planejar proteção de acesso (autorização/autenticação) nos endpoints de domínio antes de abrir consumo externo.
