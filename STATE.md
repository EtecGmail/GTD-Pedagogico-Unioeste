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
| RF-02 | Caixa de Entrada (testes + implementação) | done | Codex | RF-02 implementado via TDD com `RF02Service` (SQLite em memória), validação explícita e endpoints mínimos para captura/listagem da Caixa de Entrada. |
| RF-03 | Fatiador de leituras (testes + implementação) | done | Codex | RF-03 implementado via TDD com `RF03Service` (SQLite em memória), cálculo com arredondamento para cima, alerta de sobrecarga (>30 págs/dia), validação explícita e endpoints mínimos de criação/listagem. |
| RF-04 | Cofre de ACCs (upload seguro de certificados ACC) | done | Codex | RF-04 implementado via TDD com validação explícita de tipo/tamanho, identificador único, abstração de storage e endpoints mínimos de upload/listagem. |
| RF-05 | Barra de progresso das horas acumuladas | done | Codex | RF-05 implementado via TDD com `RF05Service` reutilizando certificados do RF-04 e endpoint `GET /rf05/acc-progress`. |
| RF-06 | Categorização em "Próximas Ações" e "Aguardando" | done | Codex | RF-06 implementado via TDD com transição explícita (`inbox -> next_action|waiting`), rejeição de transições inválidas e endpoints mínimos para atualização/listagem por status. |
| RF-07 | Recuperação de senha via e‑mail | todo | — | — |
| RF-08 | Gráficos de avanço das leituras | todo | — | — |
| RF-09 | Log de eventos de segurança | todo | — | — |
| RF-10 | Alerta de 90 % de cota de armazenamento | todo | — | — |
| DOC-UPDATE | Manter documentos atualizados com mudanças e decisões | in-progress | Codex | `STATE.md` atualizado neste ciclo com a entrega do RF-06 e validações executadas. |

## Histórico

Registre nesta seção um resumo curto de cada ciclo de trabalho: data, tarefas concluídas, dificuldades, resultados de testes e próximos passos.

- **25/03/2026** – Início do projeto. Documentos de contexto e plano preparados. Aguardando definição de stack tecnológica.
- **26/03/2026** – Início da Fase 2 (Fundação): stack base definida e estrutura mínima de backend proposta; autenticação inicial implementada com `Argon2id` e login blindado via TDD. Testes criados antes da implementação e aprovados (`4 passed`).
- **26/03/2026 (ajuste)** – Mitigação de timing attack no login: adicionado `dummyHash` Argon2id para verificar senha mesmo quando usuário não existe, mantendo resposta genérica (`credenciais inválidas`). Novo teste TDD incluído e suíte passou (`5 passed`).
- **26/03/2026 (infra/poetry)** – Estabilização da configuração do Poetry: incluído `package-mode = false` para impedir falha de instalação do projeto raiz sem pacote instalado e criados grupos `dev` e `test` em `tool.poetry.group.*` para compatibilidade com `poetry install --with dev,test`. `poetry lock` atualizado com sucesso. Instalação de dependências e execução de testes ficaram bloqueadas por falha de conectividade com `files.pythonhosted.org`.
- **26/03/2026 (auth/http)** – Ambiente validado com sucesso (`poetry install --with dev,test` e `poetry run pytest`). Em seguida, foi implementada camada HTTP mínima com FastAPI usando TDD: novos testes para `POST /auth/login` criados antes da implementação, cobrindo credenciais válidas, resposta cega para usuário inexistente/senha incorreta e validação explícita de entrada. Ajuste técnico aplicado no SQLite em memória (`check_same_thread=False`) para compatibilidade com execução em thread no `TestClient`. Suíte final: `8 passed`.

- **26/03/2026 (auth/hardening)** – Endurecimento da borda pública de autenticação via TDD. Primeiro foram escritos testes para abstração de rate limit e para o endpoint (`POST /auth/login`) cobrindo bloqueio por excesso de tentativas (status `429`), preservação do login blindado e logs de segurança sem vazamento de senha/e-mail bruto. Implementada abstração `RateLimiter` com `MemoryRateLimiter` (storage substituível), chave de limitação por IP + hash reduzido de e-mail e validação de payload com `extra="forbid"`. Decisão técnica documentada: honeypot não é apropriado para API JSON pura (mais útil em formulários HTML para bots de preenchimento). Suíte final: `12 passed`.
- **26/03/2026 (fase 3 / rf-01)** – Implementação do RF-01 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para cadastro/listagem de disciplinas e professores, validação explícita, rejeição de payload inválido, bloqueio de duplicidades e validação de vínculo disciplina-professor. Em seguida, foi implementado `RF01Service` com SQLite em memória, normalização de campos e tabela de vínculo (`discipline_professor`) para base sustentável dos próximos módulos. Por fim, endpoints mínimos foram adicionados em FastAPI: `POST/GET /rf01/professors` e `POST/GET /rf01/disciplines`. Suíte final: `18 passed`.
- **26/03/2026 (fase 3 / rf-02)** – Implementação do RF-02 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para captura rápida na Caixa de Entrada, listagem, rejeição de payload inválido/incompleto e ordenação por criação mais recente. Em seguida, foi implementado `RF02Service` com SQLite em memória e status inicial `inbox`, incluindo timestamp `createdAt` em ISO 8601. Por fim, endpoints mínimos foram adicionados em FastAPI: `POST /rf02/inbox-items` e `GET /rf02/inbox-items`. Suíte final: `23 passed`.
- **26/03/2026 (fase 3 / rf-03)** – Implementação do RF-03 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para cálculo de meta diária com arredondamento para cima, ativação de sobrecarga quando `dailyGoal > 30`, rejeição de payload inválido/incompleto e tratamento explícito para valores zero/negativos. Em seguida, foi implementado `RF03Service` com SQLite em memória e modelagem mínima para plano de leitura (`totalPages`, `deadlineDays`, `dailyGoal`, `isOverloaded`) com campos de base para evolução (`remainingPages`, `createdAt`). Por fim, endpoints mínimos foram adicionados em FastAPI: `POST /rf03/reading-plans` e `GET /rf03/reading-plans`. Suíte final: `28 passed`.

- **26/03/2026 (fase 3 / rf-04)** – Implementação do RF-04 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para upload/listagem de certificados ACC, validação explícita de tipo (`PDF/JPG/PNG`), limite de 5 MB, rejeição de payload inválido/incompleto e prevenção de colisões de armazenamento lógico. Em seguida, foi implementado `RF04Service` com modelagem mínima (`fileIdentifier`, `originalName` sanitizado, `contentType`, `sizeBytes`, `hours`, `storageKey`, `metadata`, `createdAt`) e abstração `CertificateStorage` para preparar evolução de criptografia em repouso sem refatoração ampla. Por fim, endpoints mínimos foram adicionados em FastAPI: `POST /rf04/certificates` (payload JSON com `contentBase64`) e `GET /rf04/certificates`. Suíte final: `33 passed`.

- **26/03/2026 (fase 3 / rf-05)** – Implementação do RF-05 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para cálculo de progresso ACC com `totalHours`, `targetHours`, `remainingHours`, `percentage` e `isCompleted`, incluindo casos sem certificados, meta ultrapassada e validação explícita de meta inválida. Em seguida, foi implementado `RF05Service` reutilizando `RF04Service` para agregação de horas sem duplicar persistência. Por fim, endpoint mínimo foi adicionado em FastAPI: `GET /rf05/acc-progress` com `targetHours` opcional para consumo futuro por dashboard/termômetro visual. Suíte final: `38 passed`.

- **26/03/2026 (fase 3 / rf-06)** – Implementação do RF-06 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para transições de status da Caixa de Entrada (`inbox -> next_action` e `inbox -> waiting`), listagem por categoria, rejeição de item inexistente e rejeição de payload inválido/incompleto. Em seguida, foi implementado `RF06Service` reutilizando a persistência do `RF02Service`, com regras explícitas de transição e validação de status suportados. Por fim, endpoints mínimos foram adicionados em FastAPI: `PATCH /rf06/inbox-items/{itemId}/status` e `GET /rf06/inbox-items?status=...`. Suíte final: `48 passed`.

### Arquivos modificados no ciclo atual
- `src/gtd_backend/http.py`
- `src/gtd_backend/rf02.py`
- `src/gtd_backend/rf06.py`
- `tests/test_rf06.py`
- `STATE.md`

### Comandos executados e resultados
- `poetry run pytest -q tests/test_rf06.py` (falha esperada no ciclo TDD após criação dos testes: `ModuleNotFoundError: No module named 'gtd_backend.rf06'`).
- `poetry run pytest -q tests/test_rf06.py` (sucesso após implementação incremental de serviço e endpoints: `10 passed`).
- `poetry run pytest -q` (sucesso: `48 passed`).
- `poetry run python -m compileall src` (sucesso: compilação dos módulos sem erro).

### Problemas/riscos remanescentes
- `RF01Service` usa SQLite em memória por instância de aplicação; ao evoluir para ambiente persistente/multi-instância será necessário repositório compartilhado (PostgreSQL).
- A regra de duplicidade de disciplina considera o par (`nome normalizado`, `código normalizado`); se o domínio exigir unicidade global apenas por código, essa regra deve ser ajustada e coberta por testes.
- Ainda não há autenticação/autorização aplicada nos endpoints de RF-01; isso deve ser incluído quando o módulo de sessão/token estiver disponível.
- `RF02Service` também usa SQLite em memória por instância; para uso real será necessário storage compartilhado e estratégia de migração.
- A ordenação atual de caixa de entrada usa `created_at DESC, id DESC`; em cenários distribuídos será importante padronizar relógio e timezone na camada de persistência.
- As transições de RF-06 estão restritas a `inbox -> next_action|waiting`; se houver necessidade futura de retorno para `inbox` ou transições entre categorias, será necessário explicitar nova política e cobertura de testes.
- O `RF04Service` usa storage em memória sem criptografia em repouso nesta etapa; a abstração `CertificateStorage` foi criada para permitir evolução segura sem refatoração ampla (RNF-01 pendente).
- O endpoint HTTP de upload do RF-04 foi implementado com JSON (`contentBase64`) por limitação de dependência de ambiente (`python-multipart` indisponível sem rede); para produção mobile/câmera, migrar para `multipart/form-data` assim que a dependência estiver disponível.

### Próximos passos
- Integrar as categorias de RF-06 (`inbox`, `next_action`, `waiting`) ao dashboard do estudante para métricas de carga mental e acompanhamento GTD.
- Evoluir `CertificateStorage` para provider persistente com criptografia em repouso (RNF-01), mantendo contrato atual.
- Planejar migração do endpoint de upload para `multipart/form-data` com suporte mobile/câmera e validação de assinatura mágica de arquivo (defesa em profundidade).
- Definir camada de persistência compartilhada para evitar múltiplos bancos em memória por serviço conforme avanço da fase 3.
- Planejar proteção de acesso (autorização/autenticação) nos endpoints de domínio antes de abrir consumo externo.
