# Educação — Renovação de Matrícula (Operação)

## Objetivo

Padronizar a renovação de matrícula no GEPUB com três frentes:

- configuração da janela pela secretaria;
- pedido online do aluno por prioridade;
- processamento automático de aprovação/rejeição.

## Fluxo da Secretaria

1. Acesse `Educação > Renovação de Matrícula`.
2. Crie uma renovação com:
   - descrição;
   - ano letivo;
   - secretaria;
   - data de início e fim.
3. Entre na renovação criada e adicione as turmas ofertadas.
4. Durante a janela, acompanhe os pedidos.
5. Após o encerramento (ou quando necessário), clique em `Processar pedidos`.

## Fluxo do Aluno

1. Acesse `Área do Aluno > Ensino > Renovação de matrícula`.
2. Escolha as turmas ofertadas e informe prioridade.
3. O sistema permite cancelar pedido pendente durante a janela.
4. Ao fim do processamento, cada pedido fica com status:
   - `Aprovado`;
   - `Rejeitado`.

## Regras de Processamento

- Para cada aluno, apenas o pedido de maior prioridade é aprovado.
- Pedidos restantes do mesmo aluno são rejeitados automaticamente.
- Se já existir matrícula na turma aprovada:
  - matrícula é reativada, quando aplicável.
- Se existir matrícula ativa no mesmo ano letivo em outra turma:
  - é feito remanejamento automático.
- Se não existir matrícula ativa:
  - é criada nova matrícula automaticamente.

## Onde consultar

- Painel principal da Educação:
  - total de renovações;
  - abertas;
  - pendentes de processamento;
  - processadas.
- Detalhe do aluno:
  - bloco `Pedidos de renovação de matrícula`.

## Observações de Operação

- A renovação só fica disponível ao aluno dentro da janela (`data_inicio` a `data_fim`).
- Ofertas inativas não são consideradas no processamento.
- A secretaria pode ativar/inativar a renovação no detalhe da tela.
