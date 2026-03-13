# Educação - Declaração de Vínculo (PDF)

## Objetivo
Gerar uma declaração oficial informando o vínculo escolar do aluno, com confirmação de matrícula/situação, dados pessoais básicos e assinatura institucional da unidade.

## Persistência automática em Documentos
- Ao emitir a **Declaração de Vínculo**, o PDF é salvo automaticamente em `AlunoDocumento`.
- Ao emitir a **Carteira Estudantil**, o PDF também é salvo automaticamente em `AlunoDocumento`.
- Resultado: a aba **Documentação do aluno** passa a concentrar os arquivos gerados pelo sistema a cada emissão.

## Rota
- `GET /educacao/alunos/<aluno_id>/declaracao-vinculo.pdf`
- Nome da rota: `educacao:declaracao_vinculo_pdf`

## Regras de acesso
- Permissão: `educacao.view`
- Escopo aplicado por RBAC:
  - só emite para aluno visível ao perfil logado.
  - professor pode emitir somente para alunos das suas turmas.

## Dados usados no PDF
- Aluno: nome, CPF (mascarado), NIS, data de nascimento, mãe/pai.
- Matrícula de referência:
  - prioridade para matrícula ativa;
  - fallback para última matrícula no escopo.
- Vínculo: turma, turno, ano letivo, data de matrícula e situação.
- Institucional:
  - município, secretaria e unidade;
  - logos/brasão (quando disponíveis no `PortalMunicipalConfig`).
- Assinatura:
  - tenta resolver gestor por `CoordenacaoEnsino` ativa da unidade;
  - fallback para perfis de gestão da unidade/secretaria;
  - fallback final para texto padrão ("não informado").

## Interface
- Ação no topo do detalhe do aluno: `Declaração de Vínculo`.
- CTA na seção "Certificados e declarações":
  - `Emitir declaração de vínculo (PDF)`.

## Arquivos principais
- View: `apps/educacao/views_declaracao.py`
- Template PDF: `templates/educacao/pdf/declaracao_vinculo.html`
- URL: `apps/educacao/urls.py`
- Permissão professor (whitelist de rotas): `apps/core/decorators.py`
- Ações da página do aluno: `apps/educacao/views_alunos_listing.py`

## Testes
- `apps.educacao.tests.CalendarioEducacionalTestCase.test_professor_pode_emitir_declaracao_vinculo_do_aluno_da_turma`
- `apps.educacao.tests.EducacaoCatalogoDocumentacaoTestCase.test_declaracao_vinculo_pdf`
