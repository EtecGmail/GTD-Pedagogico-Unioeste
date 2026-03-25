# PROJECT_CONTEXT.md

Este documento resume a visão e o escopo do projeto **GTD Pedagógico Unioeste**, conforme o documento de visão fornecido.

## Informações Básicas
* **Nome**: GTD Pedagógico Unioeste (Gestão de Tarefas e Descompressão Acadêmica).
* **Data de início**: Definir ao início.
* **Gerente do projeto**: Yuri Garcia Pardinho.
* **Público-alvo**: estudantes do 1º ao 4º ano de Pedagogia da Unioeste, campus Francisco Beltrão.

## Justificativa
O curso de Pedagogia exige uma **carga de leitura teórica densa**. Estudantes relatam sobrecarga cognitiva para gerenciar prazos e certificados de Atividades Curriculares Complementares (ACCs). A ausência de um repositório centralizado gera estresse e perda de documentos. O projeto aplica o método **Getting Things Done (GTD)** para externalizar a carga mental para um sistema digital confiável.

## Objetivos (Metas SMART)
1. **Lançar a versão 1.0** do aplicativo web.
2. **Fornecer repositório criptografado** para até 200 horas de certificados por usuário.
3. **Implementar interface de fatiamento de tarefas** para metas diárias acionáveis.
4. **Garantir 100% de conformidade** com segurança defensiva Shift-Left.

## Escopo
### Incluído
* **Diretriz mobile-first**: interfaces otimizadas para smartphones, mas adaptadas para desktop.
* **Módulo Caixa de Entrada**: captura de ideias em segundos via smartphone.
* **Módulo Fatiador de Leituras**: divisão de capítulos em blocos diários.
* **Cofre de ACCs**: upload de certificados com somatório automático.
* **Segurança GSD**: backend com TDD e criptografia Argon2id.
* **Proteção anti-enumeração**: login blindado com mensagens padronizadas.
* **Dashboards visuais**: gráficos de progresso e telemetria.

### Fora do escopo
* Geração de textos ou planos de aula por IA.
* Integração direta com sistemas Acadêmicos (Academus, Sagu).
* Funcionalidades de rede social ou compartilhamento público.

## Requisitos do Sistema
### Requisitos Funcionais (RF)
1. **RF-01**: cadastro de disciplinas e professores.
2. **RF-02**: captura instantânea na Caixa de Entrada.
3. **RF-03**: cálculo de divisão de páginas por dia.
4. **RF-04**: upload de documentos de até 5 MB no Cofre de ACCs.
5. **RF-05**: barra de progresso visual das horas acumuladas.
6. **RF-06**: categorização em “Próximas Ações” ou “Aguardando”.
7. **RF-07**: recuperação de senha segura via e-mail.
8. **RF-08**: gráficos dinâmicos de avanço das leituras.
9. **RF-09**: log de eventos de segurança para o administrador.
10. **RF-10**: alerta de 90% da cota de armazenamento.

### Requisitos Não Funcionais (RNF)
1. **RNF-01**: certificados armazenados com criptografia em repouso.
2. **RNF-02 (Prioridade mobile)**: tempo de resposta e ergonomia perfeitos em telas pequenas, a complexidade visual aumenta apenas em telas maiores.
3. **RNF-03**: cobertura de testes unitários (TDD) superior a 90%.
4. **RNF-04**: carregamento inicial em <2 s em redes 4G/5G.
5. **RNF-05**: descarte silencioso de tráfego malicioso.
6. **RNF-06**: privacidade total dos arquivos dos alunos.

## Dashboards e Administração
* **Para o estudante**: termômetro de ACCs (gráfico circular de progresso), status de carga mental (proporção de tarefas pendentes), timeline de leitura (indicador de ritmo).
* **Para o administrador**: monitor de segurança e integridade do banco de dados, saúde do servidor e taxa de sucesso dos deploys, volume total de armazenamento utilizado.

## Cronograma de marcos (milestones)
1. **Fase 1 (Kickoff)**: aprovação de escopo e requisitos técnicos.
2. **Fase 2 (Fundação)**: banco de dados, TDD e login blindado.
3. **Fase 3 (Core App)**: módulo GTD, fatiador e Cofre ACC.
4. **Fase 4 (Homologação)**: testes de aceitação com grupo focal.
5. **Fase 5 (Lançamento)**: disponibilização oficial Unioeste FB (manual).

## Stakeholders
* **Patrocinadores**: Centro Acadêmico de Pedagogia.
* **Usuários finais**: estudantes da Unioeste campus FB.
* **Engenharia**: Yuri Garcia Pardinho e equipe GSD.

## Riscos e Mitigações
* **Risco tecnológico**: perda de dados. Mitigação: TDD rigoroso.
* **Risco de segurança**: acessos indevidos. Mitigação: criptografia Argon2id e tecnologias de decepção.
* **Risco de adoção**: baixa utilização. Mitigação: interface minimalista focada em uso móvel imediato.

## User stories relevantes
* **US-002: Fatiador de Leituras Acadêmicas**: o estudante informa total de páginas e prazo. O sistema calcula a meta diária com base na fórmula `metaDiaria = ⌈páginas / prazoDias⌉` e alerta se a meta ultrapassar 30 páginas/dia.
* **US-003: Cofre de ACCs**: o estudante faz upload de certificados (PDF/JPG/PNG até 5 MB) para backup seguro e controle de horas. Os arquivos são renomeados com hash único e criptografados. A interface mobile permite usar a câmera para escanear.