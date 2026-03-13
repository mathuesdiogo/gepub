# Política de Planos — Apps por Maturidade

## Regra geral
- Todos os planos possuem acesso ao núcleo de gestão interna por secretarias.
- A diferença entre planos está apenas nos apps públicos:
  - `Portal da Prefeitura`
  - `Portal da Transparência`
  - `Portal da Câmara`

## Matriz de apps por plano
- `GEPUB Essencial`: `Gestão`
- `GEPUB Gestão Integrada`: `Gestão + Portal`
- `GEPUB Transformação Digital`: `Gestão + Portal + Transparência`
- `GEPUB Governo Completo`: `Gestão + Portal + Transparência + Câmara`

## Regras de bloqueio
- Quando um app não está no plano, ele deve ser ocultado em:
  - menu lateral e atalhos visuais
  - rotas/telas administrativas correspondentes
  - endpoints de criação/edição/publicação correspondentes
  - navegação pública do portal do município

## Secretarias
- Todas as prefeituras podem ativar qualquer secretaria.
- Não há bloqueio de quantidade de secretarias por plano.

## Ferramentas internas (fase atual)
- Painéis BI, conversor e integrações não estão diferenciados por plano nesta fase.
- Diferenciações futuras dessas ferramentas serão tratadas como add-ons/expansões comerciais.

## Dependências operacionais recomendadas
- `compras` + `processos` + `financeiro` + `contratos`
- `contratos` + `processos` + `financeiro`
- `folha` + `rh` + `ponto` + `financeiro`
- `tributos` + `financeiro`
- `frota` + `almoxarifado`
