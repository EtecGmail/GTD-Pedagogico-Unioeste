# PLAN.md

Este plano de trabalho organiza o backlog de tarefas do projeto **GTD Pedagógico Unioeste**. Cada tarefa deve ser executada seguindo o processo descrito em `AGENTS.md` – planejar, escrever testes (TDD), implementar, validar e atualizar o estado em `STATE.md`.

## Tarefas iniciais
1. **Configuração do repositório**
   - Inicializar repositório com estrutura de pastas: `src/`, `tests/`, `docs/`.
   - Adicionar arquivos de configuração (lint, prettier, CI) e licenças adequadas.
   - Criar `PROJECT_CONTEXT.md`, `AGENTS.md`, `PLAN.md` e `STATE.md` (já preparados).

2. **Definição da stack tecnológica**
   - Selecionar frameworks adequados: por exemplo React/Vue para frontend; Node.js/Express ou Django/FastAPI para backend.
   - Escolher bases de dados seguras (PostgreSQL + criptografia em repouso ou MongoDB com encryption at rest).
   - Definir ferramentas de testes (Jest/Vitest/Cypress para JS, pytest para Python) e pipeline de CI.

3. **Configuração do ambiente Codex**
   - Criar environment `default-dev` com internet desligada para a maioria das tarefas, conforme as recomendações.
   - Criar environment `web-research` com internet habilitada e allowlist minimal para consultas externas.
   - Definir variáveis de ambiente seguras e secrets necessários para instalar dependências.
   - Adicionar scripts de `setup` e `maintenance` (ver exemplo no guia anterior) para instalar dependências com base na stack escolhida.

4. **Implementação da infraestrutura de segurança**
   - Configurar autenticação com login blindado usando Argon2id.
   - Escrever testes para garantir que mensagens de erro de login não revelam se o usuário existe.
   - Implementar camadas de criptografia em repouso para certificados.
   - Criar middleware de validação de entrada e descarte de tráfego malicioso.

## Backlog de funcionalidades

Cada funcionalidade abaixo corresponde a um requisito funcional (RF). Para cada item, primeiro escreva testes no diretório `tests/` (TDD) e só então implemente a funcionalidade no diretório `src/`.

1. **RF‑01 – Cadastro de disciplinas e professores**
   - Testes: criar e recuperar disciplinas/professores; validar campos obrigatórios e restrições.
   - Implementar rotas/API e interface para cadastro e listagem.

2. **RF‑02 – Captura instantânea na Caixa de Entrada**
   - Testes: garantir que tarefas rápidas são salvas com título e timestamp; verificar usabilidade mobile.
   - Implementar componente de entrada e persistência das tarefas.

3. **RF‑03 – Fatiador de leituras**
   - Testes: dado número de páginas e prazo, calcular meta diária com arredondamento para cima; exibir alerta se meta >30 páginas/dia.
   - Implementar função de cálculo e interface amigável com seletores numéricos grandes.

4. **RF‑04 – Upload de certificados (Cofre de ACCs)**
   - Testes: upload de PDFs/JPG/PNG até 5 MB; renomear arquivo com hash único; criptografia ao armazenar; rejeitar arquivos grandes ou formatos não suportados.
   - Implementar endpoint de upload e armazenamento seguro; somatório automático de horas.

5. **RF‑05 – Barra de progresso de horas acumuladas**
   - Testes: somar horas dos certificados de forma precisa; atualizar gráfico em tempo real.
   - Implementar componente visual (termômetro/medidor) e API de consulta.

6. **RF‑06 – Categorização em “Próximas Ações” e “Aguardando”**
   - Testes: mover tarefas entre listas; persistir estado entre sessões; filtrar tarefas por categoria.
   - Implementar modelos e UI para categorizar tarefas.

7. **RF‑07 – Recuperação de senha via e‑mail**
   - Testes: fluxo de solicitação de redefinição; verificação de token de segurança; garantia de que e‑mail enviado não revela dados sensíveis.
   - Implementar serviço de e‑mail e API de redefinição com tokens temporários.

8. **RF‑08 – Gráficos de avanço das leituras**
   - Testes: geração correta de séries temporais; cálculo de ritmo; responsividade em mobile.
   - Implementar componente de gráficos utilizando biblioteca confiável.

9. **RF‑09 – Log de eventos de segurança**
   - Testes: registrar tentativas de login falhas, uploads e ações administrativas; validar que logs são acessíveis apenas para administradores.
   - Implementar sistema de logging segregado.

10. **RF‑10 – Alerta de 90 % da cota de armazenamento**
    - Testes: emissão de alerta quando o uso de armazenamento atingir 90 % da cota; não alertar antes.
    - Implementar verificação periódica ou no momento do upload.

## Outras atividades contínuas

- **Documentação** – manter `PROJECT_CONTEXT.md` e outros documentos atualizados com decisões e alterações.
- **Melhorias de UX** – garantir que a interface mobile-first atenda às exigências de ergonomia.
- **Auditorias de segurança** – revisar código para detectar vulnerabilidades; adicionar testes de segurança.
- **Preparação para deployment** – configurar scripts de build e containers; preparar ambiente de staging/homologação.

## Próximos passos

1. Selecionar stack tecnológica e atualizar `PLAN.md` com detalhes da stack.
2. Configurar CI/CD para rodar testes automaticamente a cada commit/pull request.
3. Começar pela **Fase 2 – Fundação**, implementando a infraestrutura de banco de dados, autenticação e cobertura de testes básica.

