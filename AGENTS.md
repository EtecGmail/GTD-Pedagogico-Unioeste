# AGENTS.md

## Objetivo
Atue como engenheiro de software responsável pelo projeto **GTD Pedagógico Unioeste**. A missão é implementar um aplicativo web para ajudar estudantes de Pedagogia da Unioeste a gerir tarefas, dividir leituras e armazenar certificados de ACCs de forma segura. Trabalhe sempre em **Português do Brasil**, siga boas práticas de desenvolvimento seguro e siga um processo iterativo: planejar → testar → implementar → revisar.

## Fluxo de Trabalho
1. **Contexto** – consulte `PROJECT_CONTEXT.md` para entender o escopo, requisitos e metas do projeto.
2. **Planejamento** – antes de codar:
   - descreva o objetivo da tarefa em 3‑6 bullets;
   - liste arquivos que serão criados ou modificados;
   - explique a estratégia de implementação e riscos (segurança, performance, UX);
   - proponha uma abordagem de **Test-Driven Development (TDD)**, descrevendo os testes que demonstrarão o comportamento esperado.
3. **Testes** – escreva primeiro os testes automatizados (ex.: Jest para JS/TS, pytest para Python). Garanta cobertura >90 %, como definido nos requisitos não funcionais.
4. **Implementação** – faça mudanças incrementais e revisitáveis. Siga convenções:
   - nomes de variáveis e funções em **camelCase**;
   - nomes de classes em **PascalCase**;
   - comentários e mensagens em PT‑BR;
   - preserve arquitetura existente e não adicione dependências sem justificativa.
5. **Validação** – execute lint, testes e build. Certifique‑se de que todos os testes estão passando e que os requisitos funcionais foram atendidos.
6. **Resumo** – atualize `STATE.md` com:
   - tarefas concluídas e novas tarefas identificadas;
   - arquivos modificados;
   - comandos executados e resultados;
   - eventuais problemas ou riscos remanescentes.

## Convenções de Git
- Crie branches seguindo o padrão `codex/<tipo>/<ticket-ou-escopo>-<slug>` (ex.: `codex/feat/caixa-entrada`). Tipos recomendados: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Faça commits pequenos e bem descritos, referenciando a user story ou requisito.
- Nunca faça push de segredos ou dados sensíveis; use variáveis de ambiente e segredos.

## Segurança e Privacidade
- Utilize criptografia Argon2id para senhas e arquivos confidenciais conforme os requisitos de segurança.
- Implemente **login blindado** com mensagens genéricas para evitar enumeração de usuários.
- Valide todas as entradas e permissões; descarte tráfico malicioso silenciosamente.
- Proteja dados em repouso e em trânsito; não logar senhas ou tokens.

## Testes
- Para cada requisito funcional (RF‑01 a RF‑10) e user story (US‑002, US‑003 etc.), crie testes automatizados que verifiquem o comportamento esperado antes de implementar a funcionalidade.
- Escreva testes unitários e, quando necessário, testes de integração/end‑to‑end para os fluxos do usuário (ex.: captura na caixa de entrada, fatiamento de leitura, upload de certificado).
- Garanta que falhas de segurança e regressões sejam cobertas pelos testes.

## Comunicação
- Toda a documentação técnica adicional deve ficar em arquivos Markdown no repositório (por exemplo, `PROJECT_CONTEXT.md` para visão do projeto, `PLAN.md` para backlog de tarefas e `STATE.md` para o estado atual).
- Atualize os arquivos conforme novas informações surgirem.

