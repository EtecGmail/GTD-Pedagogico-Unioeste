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
| RF-07 | Recuperação de senha via e‑mail | done | Codex | RF-07 finalizado via TDD com tokens temporários hasheados, fluxo cego na solicitação e confirmação com Argon2id + invalidação por uso/expiração. |
| RF-08 | Gráficos de avanço das leituras | done | Codex | Base backend-first implementada via TDD com agregação de dashboard e endpoint mínimo de avanço de leitura. |
| RF-09 | Log de eventos de segurança | todo | — | — |
| RF-10 | Alerta de 90 % de cota de armazenamento | todo | — | — |
| DOC-UPDATE | Manter documentos atualizados com mudanças e decisões | in-progress | Codex | `STATE.md` atualizado neste ciclo com a entrega do RF-07 e validações executadas. |

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
- **27/03/2026 (fase 3 / rf-08, backend-first)** – Implementação da base do RF-08 via TDD estrito. Primeiro foram criados testes de serviço e HTTP para agregação do dashboard do estudante e para avanço de leitura, cobrindo cenários com e sem dados, validação explícita e rejeição de plano inexistente. Em seguida, foi implementado `RF08Service` reutilizando RF-06 (contagens por status), RF-05 (progresso de ACC) e RF-03 (resumo de leitura). Também foi estendido o `RF03Service` com `advanceReadingPlan` para atualização controlada de `remainingPages`. Por fim, endpoints mínimos foram adicionados em FastAPI: `GET /rf08/dashboard` e `PATCH /rf08/reading-plans/{planId}/advance`. Suíte final: `52 passed`.

- **27/03/2026 (fase 3 / rf-07)** – Implementação do RF-07 via TDD estrito. Primeiro foram criados testes de serviço para schema SQLite mínimo de tokens de redefinição, comportamento cego para usuário inexistente, persistência apenas de hash do token, expiração e invalidação por uso. Em seguida, foi implementado `RF07Service` com dependências injetáveis (`authService`, `emailSender`, `nowProvider`), geração criptograficamente segura de token (`secrets.token_urlsafe`) e confirmação com atualização de senha via Argon2id reaproveitando o hasher do `AuthService`. Por fim, o `AuthService` foi estendido com operações explícitas para localizar usuário por e-mail e atualizar hash de senha por ID. Suíte final: `58 passed`.
- **27/03/2026 (fase 3 / rf-07, hardening HTTP)** – Endurecimento do fluxo HTTP de recuperação de senha via TDD. Primeiro foram escritos/atualizados testes para rotas públicas em `/auth/password-reset/*`, cobrindo resposta cega na solicitação, confirmação com sucesso e erro genérico (`400`) para token inválido/usado, validação com `extra="forbid"` e mitigação de abuso (`429`) por rate limit. Em seguida, `http.py` foi ajustado com novos modelos Pydantic (`RequestPasswordResetRequest` e `ConfirmPasswordResetRequest`), endpoints `POST /auth/password-reset/request` e `POST /auth/password-reset/confirm`, e logs sem vazamento de e-mail bruto/token/senha (somente `email_hash` reduzido). Também foi aplicado escopo de rate limit dedicado para isolar login e reset de senha. Validação final concluída com sucesso (`65 passed`).

### Arquivos modificados no ciclo atual
- `src/gtd_backend/http.py`
- `tests/test_auth_http.py`
- `STATE.md`

### Comandos executados e resultados
- `pytest -q tests/test_auth_http.py` (falha de ambiente esperada fora do Poetry: `ModuleNotFoundError: No module named 'fastapi'`).
- `poetry run pytest -q tests/test_auth_http.py` (sucesso: `14 passed`).
- `poetry run pytest -q` (sucesso: `65 passed`).
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
- O resumo de leitura no RF-08 usa agregação simples sobre os planos existentes; para gráficos temporais completos (timeline/ritmo diário), será necessário persistir histórico de avanço por data.

### Próximos passos
- Evoluir RF-08 para série temporal de avanço de leitura (gráfico dinâmico real), mantendo o endpoint agregado já entregue.
- Considerar expansão de mitigação antiabuso no RF-07 com buckets adicionais por IP puro (sem e-mail) e backoff progressivo para padrões de ataque distribuído.
- Evoluir `CertificateStorage` para provider persistente com criptografia em repouso (RNF-01), mantendo contrato atual.
- Planejar migração do endpoint de upload para `multipart/form-data` com suporte mobile/câmera e validação de assinatura mágica de arquivo (defesa em profundidade).
- Definir camada de persistência compartilhada para evitar múltiplos bancos em memória por serviço conforme avanço da fase 3.
- Planejar proteção de acesso (autorização/autenticação) nos endpoints de domínio antes de abrir consumo externo.

- **27/03/2026 (fase 3 / rf-07, reforço TDD solicitado)** – Reescrita/organização dos testes de RF-07 em `tests/test_rf07.py` com foco explícito nos cenários solicitados: serviço (não enumeração de conta, geração de token com expiração, rejeição de token inválido/expirado, atualização de hash Argon2id, token de uso único, rejeição de payload inválido) e HTTP (`/auth/password-reset/request` com mesma resposta para e-mails existentes/inexistentes, `/auth/password-reset/confirm` sucesso/erro e validação `422` para payload incompleto/campos extras). Foi adotado `InMemoryPasswordResetEmailSender` e `nowProvider` fixo/mutável nos testes para controlar expiração de forma determinística. Implementação de serviço/endpoints já existente permaneceu compatível e suíte seguiu verde.

### Arquivos modificados no ciclo atual
- `tests/test_rf07.py`
- `STATE.md`

### Comandos executados e resultados
- `pytest -q tests/test_rf07.py tests/test_auth_http.py` (falha de ambiente fora do Poetry: `ModuleNotFoundError: No module named 'fastapi'`).
- `poetry install` (sucesso: sem atualizações necessárias).
- `poetry run pytest -q tests/test_rf07.py` (sucesso: `10 passed`).
- `poetry run pytest -q` (sucesso: `69 passed`).

### Problemas/riscos remanescentes
- O serviço RF-07 mantém tokens em SQLite em memória; para produção será necessário storage persistente e estratégia de revogação distribuída.
- O endpoint de solicitação de reset já mitiga enumeração por resposta genérica, mas ataques distribuídos podem demandar política adicional por IP puro e/ou backoff progressivo.

### Próximos passos
- Evoluir políticas antiabuso do RF-07 (rate limit multicamada e observabilidade de padrões).
- Preparar persistência compartilhada para tokens de reset e demais serviços stateful.

- **27/03/2026 (auth/updatePassword)** – Implementação via TDD do método `updatePassword(userId, newPlainPassword)` no `AuthService`. Primeiro foi adicionado teste unitário cobrindo atualização de hash, autenticação bem-sucedida com a nova senha e falha da senha antiga com mensagem genérica (`credenciais inválidas`). Em seguida, o serviço foi ajustado para validar política mínima de senha (>= 8, após `strip`), gerar novo hash Argon2id e persistir por `user_id` reaproveitando `updateUserPasswordHash`, mantendo erro controlado para usuário inexistente. Não foram adicionados logs no fluxo para evitar vazamento de senha/token.

### Arquivos modificados no ciclo atual
- `src/gtd_backend/auth.py`
- `tests/test_auth.py`
- `STATE.md`

### Comandos executados e resultados
- `poetry run pytest -q tests/test_auth.py -k atualizar_hash` (falha esperada no TDD antes da implementação: `AttributeError` para método inexistente).
- `poetry run pytest -q tests/test_auth.py` (sucesso).
- `poetry run pytest -q` (sucesso: suíte completa aprovada).
- `poetry run python -m compileall src` (sucesso: compilação dos módulos sem erro).

### Problemas/riscos remanescentes
- A política de senha mínima está validada no `AuthService` para `updatePassword`, mas ainda existe validação equivalente em `RF07Service`; vale consolidar em ponto único no futuro para reduzir duplicação de regra.

### Próximos passos
- Reaproveitar `AuthService.updatePassword` no fluxo de RF-07 para centralizar regra de senha/hashing e reduzir superfície de regressão.

- **27/03/2026 (rf-07 / fechamento documental)** – Consolidação final do estado do RF-07 no `STATE.md`. O status do requisito foi mantido em **done** e o histórico foi atualizado com decisões explícitas de segurança do fluxo de recuperação de senha: **token com expiração**, **token de uso único** e **resposta cega** para evitar enumeração de contas. Também foi registrada a necessidade de integração futura com provedor real de e-mail para ambiente produtivo.

### Arquivos modificados no ciclo atual
- `STATE.md`

### Comandos executados e resultados
- `poetry run pytest -q tests/test_rf07.py` (sucesso: testes do fluxo RF-07 aprovados).
- `poetry run pytest -q` (sucesso: suíte completa aprovada neste ciclo).

### Problemas/riscos remanescentes
- O envio de e-mail ainda depende de implementação em memória/stub no ambiente atual; sem integração com provedor real não há garantia de entrega, reputação de domínio, observabilidade de bounce e políticas antiabuso completas em produção.
- Em ambiente distribuído, o controle de tokens de reset exige persistência compartilhada e política de revogação consistente entre múltiplas instâncias.

### Próximos passos
- Integrar RF-07 com provedor real de e-mail (ex.: SMTP transacional/API dedicada), incluindo autenticação segura, templates versionados e telemetria de entrega.
- Definir estratégia de retentativa/idempotência para envio de e-mails de reset sem vazar informações sensíveis ao cliente.

- **27/03/2026 (sprint de consolidação técnica / persistência compartilhada)** – Evolução incremental da base de persistência via TDD para reduzir acoplamento a SQLite em memória por serviço. Primeiro foram escritos testes novos cobrindo (1) preparação de ownership em `RF02Service` com `userId` e filtro por usuário e (2) persistência compartilhada entre instâncias de aplicação com SQLite em arquivo (`databaseUrl`). Em seguida, foi criada a infraestrutura `persistence.py` com `createSqliteConnection`, e os serviços centrais stateful (`AuthService`, `RF01Service`, `RF02Service`, `RF03Service`, `RF04Service`, `RF07Service`) passaram a aceitar conexão injetável. A função `createApp` agora injeta **uma única conexão compartilhada** para toda a aplicação, eliminando o banco isolado por serviço e preparando migração incremental para provider PostgreSQL em produção. Também foi adicionada coluna `user_id` em `inbox_items` com migração leve (`ALTER TABLE` quando necessário) para iniciar associação de dados por usuário sem quebrar contratos atuais da API.

### Arquivos modificados no ciclo atual
- `src/gtd_backend/persistence.py`
- `src/gtd_backend/http.py`
- `src/gtd_backend/auth.py`
- `src/gtd_backend/rf01.py`
- `src/gtd_backend/rf02.py`
- `src/gtd_backend/rf03.py`
- `src/gtd_backend/rf04.py`
- `src/gtd_backend/rf07.py`
- `tests/test_rf02.py`
- `tests/test_persistence.py`
- `PLAN.md`
- `STATE.md`

### Comandos executados e resultados
- `poetry run pytest -q tests/test_rf02.py tests/test_persistence.py` (falha esperada no TDD antes da implementação; depois sucesso: `7 passed`).
- `poetry run pytest -q` (sucesso: suíte completa aprovada).
- `poetry run python -m compileall src` (sucesso: compilação dos módulos sem erro).

### Problemas/riscos remanescentes
- A infraestrutura compartilhada atual cobre SQLite; o provider de conexão PostgreSQL ainda precisa ser conectado no deploy de produção (sem alterar regras de domínio).
- Endpoints de domínio permanecem sem autenticação/autorização; a base foi preparada com `user_id` em Caixa de Entrada, mas falta enforcement no HTTP.
- `RF04Service` ainda usa storage de arquivo em memória (`InMemoryCertificateStorage`), portanto RNF-01 (criptografia em repouso real) continua pendente.

### Próximos passos
- Adicionar provider de conexão PostgreSQL no bootstrap de produção reutilizando o contrato de conexão atual.
- Aplicar autenticação/autorização nos endpoints de domínio e propagar `userId` autenticado para `RF02Service`.
- Expandir a estratégia de ownership para módulos restantes (leituras, certificados, dashboards) com migração incremental e cobertura de testes.
