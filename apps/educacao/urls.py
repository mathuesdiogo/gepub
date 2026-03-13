from django.urls import path
from . import views
from . import views_api
from . import views_censo
from . import views_relatorios
from . import views_diario
from . import views_horarios
from . import views_notas
from . import views_matriculas
from . import views_fechamento
from . import views_historico
from . import views_componentes
from . import views_portal
from . import views_assistencia
from . import views_indicadores
from . import views_calendario
from . import views_catalogos
from . import views_beneficios
from . import views_carteira
from . import views_declaracao
from . import views_aluno_area
from . import views_professor_area
from . import views_estagios
from . import views_informatica
from .views_turmas_list import TurmaListView
from .views_alunos_list import AlunoListView
from .views_diarios_list import DiarioListView
from .views_periodos_list import PeriodoListView
from .views_horarios_index_list import HorariosIndexView
from apps.core.decorators import require_perm

from apps.educacao.views_horarios import (
    horario_turma,
    horario_aula_create,
    horario_aula_update,
    horario_gerar_padrao,
    horario_duplicar,
    horario_duplicar_select,
    horario_limpar,
)

from apps.educacao.views_boletim import boletim_turma, boletim_aluno
from apps.educacao.views_relatorios_turma import relatorio_geral_turma
from apps.educacao.views_boletim_periodo import boletim_turma_periodo
from apps.educacao.views_periodos import (
    periodo_create,
    periodo_update,
    periodo_gerar_bimestres,
    
)

app_name = "educacao"

urlpatterns = [

    # ======================
    # DASHBOARD
    # ======================
    path("", views.index, name="index"),

    # ======================
    # TURMAS
    # ======================
    path("turmas/", require_perm("educacao.view")(TurmaListView.as_view()), name="turma_list"),
    path("turmas/novo/", views.turma_create, name="turma_create"),
    path("turmas/<int:pk>/", views.turma_detail, name="turma_detail"),
    path("turmas/<int:pk>/editar/", views.turma_update, name="turma_update"),

    # ======================
    # ALUNOS
    # ======================
    path("alunos/", require_perm("educacao.view")(AlunoListView.as_view()), name="aluno_list"),
    path("alunos/novo/", views.aluno_create, name="aluno_create"),
    path("alunos/<int:pk>/", views.aluno_detail, name="aluno_detail"),
    path("alunos/<int:pk>/editar/", views.aluno_update, name="aluno_update"),
    path("alunos/<int:aluno_id>/carteira.pdf", views_carteira.carteira_emitir_pdf, name="carteira_emitir_pdf"),
    path("alunos/<int:aluno_id>/declaracao-vinculo.pdf", views_declaracao.declaracao_vinculo_pdf, name="declaracao_vinculo_pdf"),
    path("carteira/validar/", views_carteira.carteira_verificar_public, name="carteira_verificar_lookup"),
    path("carteira/validar/<uuid:codigo>/", views_carteira.carteira_verificar_public, name="carteira_verificar_public"),
    path("alunos/<int:pk>/historico/", views_historico.historico_aluno, name="historico_aluno"),
    path("matriculas/nova/", views_matriculas.matricula_create, name="matricula_create"),
    path("portal/professor/", views_portal.portal_professor, name="portal_professor"),
    path("portal/aluno/<int:pk>/", views_portal.portal_aluno, name="portal_aluno"),
    path("portal/aluno/<int:pk>/editais/<int:inscricao_id>/", views_portal.portal_aluno_edital_detail, name="portal_aluno_edital_detail"),
    path("aluno/<str:codigo>/", views_portal.aluno_meus_dados, name="aluno_meus_dados"),
    path("aluno/<str:codigo>/documentos-processos/", views_aluno_area.aluno_documentos_processos, name="aluno_documentos_processos"),
    path("aluno/<str:codigo>/ensino/", views_aluno_area.aluno_ensino, name="aluno_ensino"),
    path("aluno/<str:codigo>/ensino/dados/", views_aluno_area.aluno_ensino_dados, name="aluno_ensino_dados"),
    path("aluno/<str:codigo>/ensino/justificativa-falta/", views_aluno_area.aluno_ensino_justificativa, name="aluno_ensino_justificativa"),
    path("aluno/<str:codigo>/ensino/boletins-avaliacoes/", views_aluno_area.aluno_ensino_boletins, name="aluno_ensino_boletins"),
    path("aluno/<str:codigo>/ensino/avaliacoes/", views_aluno_area.aluno_ensino_avaliacoes, name="aluno_ensino_avaliacoes"),
    path("aluno/<str:codigo>/ensino/disciplinas/", views_aluno_area.aluno_ensino_disciplinas, name="aluno_ensino_disciplinas"),
    path("aluno/<str:codigo>/ensino/horarios/", views_aluno_area.aluno_ensino_horarios, name="aluno_ensino_horarios"),
    path("aluno/<str:codigo>/ensino/mensagens/", views_aluno_area.aluno_ensino_mensagens, name="aluno_ensino_mensagens"),
    path("aluno/<str:codigo>/ensino/biblioteca/", views_aluno_area.aluno_ensino_biblioteca, name="aluno_ensino_biblioteca"),
    path("aluno/<str:codigo>/ensino/apoio/", views_aluno_area.aluno_ensino_apoio, name="aluno_ensino_apoio"),
    path("aluno/<str:codigo>/ensino/processos-seletivos/", views_aluno_area.aluno_ensino_seletivos, name="aluno_ensino_seletivos"),
    path("aluno/<str:codigo>/pesquisa/", views_aluno_area.aluno_pesquisa, name="aluno_pesquisa"),
    path("aluno/<str:codigo>/central-servicos/", views_aluno_area.aluno_central_servicos, name="aluno_central_servicos"),
    path("aluno/<str:codigo>/atividades-estudantis/", views_aluno_area.aluno_atividades, name="aluno_atividades"),
    path("aluno/<str:codigo>/saude/", views_aluno_area.aluno_saude, name="aluno_saude"),
    path("aluno/<str:codigo>/comunicacao-social/", views_aluno_area.aluno_comunicacao, name="aluno_comunicacao"),
    path("professor/<str:codigo>/", views_professor_area.professor_inicio, name="professor_inicio"),
    path("professor/<str:codigo>/diarios/", views_professor_area.professor_diarios, name="professor_diarios"),
    path("professor/<str:codigo>/aulas/", views_professor_area.professor_aulas, name="professor_aulas"),
    path("professor/<str:codigo>/frequencias/", views_professor_area.professor_frequencias, name="professor_frequencias"),
    path("professor/<str:codigo>/notas/", views_professor_area.professor_notas, name="professor_notas"),
    path(
        "professor/<str:codigo>/informatica/turmas/<int:turma_id>/avaliacoes/",
        views_professor_area.professor_informatica_avaliacoes,
        name="professor_informatica_avaliacoes",
    ),
    path(
        "professor/<str:codigo>/informatica/turmas/<int:turma_id>/avaliacoes/nova/",
        views_professor_area.professor_informatica_avaliacao_create,
        name="professor_informatica_avaliacao_create",
    ),
    path(
        "professor/<str:codigo>/informatica/avaliacoes/<int:avaliacao_id>/notas/",
        views_professor_area.professor_informatica_notas_lancar,
        name="professor_informatica_notas_lancar",
    ),
    path("professor/<str:codigo>/agenda-avaliacoes/", views_professor_area.professor_agenda_avaliacoes, name="professor_agenda_avaliacoes"),
    path("professor/<str:codigo>/horarios/", views_professor_area.professor_horarios, name="professor_horarios"),
    path("professor/<str:codigo>/planos-ensino/", views_professor_area.professor_planos_ensino, name="professor_planos_ensino"),
    path(
        "professor/<str:codigo>/planos-ensino/<int:diario_id>/",
        views_professor_area.professor_plano_ensino_editar,
        name="professor_plano_ensino_editar",
    ),
    path(
        "professor/<str:codigo>/planos-ensino/informatica/<int:turma_id>/",
        views_professor_area.professor_plano_ensino_informatica_editar,
        name="professor_plano_ensino_informatica_editar",
    ),
    path("professor/<str:codigo>/materiais/", views_professor_area.professor_materiais, name="professor_materiais"),
    path("professor/<str:codigo>/materiais/novo/", views_professor_area.professor_material_novo, name="professor_material_novo"),
    path(
        "professor/<str:codigo>/materiais/<int:pk>/editar/",
        views_professor_area.professor_material_editar,
        name="professor_material_editar",
    ),
    path("professor/<str:codigo>/justificativas/", views_professor_area.professor_justificativas, name="professor_justificativas"),
    path("professor/<str:codigo>/fechamento/", views_professor_area.professor_fechamento, name="professor_fechamento"),
    path("assistencia/", views_assistencia.assistencia_index, name="assistencia_index"),
    path("assistencia/cardapios/", views_assistencia.assist_cardapio_list, name="assist_cardapio_list"),
    path("assistencia/cardapios/novo/", views_assistencia.assist_cardapio_create, name="assist_cardapio_create"),
    path("assistencia/cardapios/<int:pk>/", views_assistencia.assist_cardapio_detail, name="assist_cardapio_detail"),
    path("assistencia/cardapios/<int:pk>/editar/", views_assistencia.assist_cardapio_update, name="assist_cardapio_update"),
    path("assistencia/refeicoes/", views_assistencia.assist_refeicao_list, name="assist_refeicao_list"),
    path("assistencia/refeicoes/novo/", views_assistencia.assist_refeicao_create, name="assist_refeicao_create"),
    path("assistencia/refeicoes/<int:pk>/", views_assistencia.assist_refeicao_detail, name="assist_refeicao_detail"),
    path("assistencia/refeicoes/<int:pk>/editar/", views_assistencia.assist_refeicao_update, name="assist_refeicao_update"),
    path("assistencia/rotas/", views_assistencia.assist_rota_list, name="assist_rota_list"),
    path("assistencia/rotas/novo/", views_assistencia.assist_rota_create, name="assist_rota_create"),
    path("assistencia/rotas/<int:pk>/", views_assistencia.assist_rota_detail, name="assist_rota_detail"),
    path("assistencia/rotas/<int:pk>/editar/", views_assistencia.assist_rota_update, name="assist_rota_update"),
    path("assistencia/transporte-registros/", views_assistencia.assist_transporte_registro_list, name="assist_transporte_registro_list"),
    path("assistencia/transporte-registros/novo/", views_assistencia.assist_transporte_registro_create, name="assist_transporte_registro_create"),
    path("assistencia/transporte-registros/<int:pk>/", views_assistencia.assist_transporte_registro_detail, name="assist_transporte_registro_detail"),
    path("assistencia/transporte-registros/<int:pk>/editar/", views_assistencia.assist_transporte_registro_update, name="assist_transporte_registro_update"),

    # ======================
    # BENEFÍCIOS E ENTREGAS
    # ======================
    path("beneficios/", views_beneficios.beneficios_index, name="beneficios_index"),
    path("beneficios/tipos/", views_beneficios.beneficio_tipo_list, name="beneficio_tipo_list"),
    path("beneficios/tipos/novo/", views_beneficios.beneficio_tipo_create, name="beneficio_tipo_create"),
    path("beneficios/tipos/<int:pk>/", views_beneficios.beneficio_tipo_detail, name="beneficio_tipo_detail"),
    path("beneficios/tipos/<int:pk>/editar/", views_beneficios.beneficio_tipo_update, name="beneficio_tipo_update"),
    path("beneficios/tipos/<int:pk>/itens/adicionar/", views_beneficios.beneficio_tipo_item_add, name="beneficio_tipo_item_add"),
    path("beneficios/tipos/<int:pk>/itens/<int:item_id>/remover/", views_beneficios.beneficio_tipo_item_remove, name="beneficio_tipo_item_remove"),

    path("beneficios/campanhas/", views_beneficios.beneficio_campanha_list, name="beneficio_campanha_list"),
    path("beneficios/campanhas/nova/", views_beneficios.beneficio_campanha_create, name="beneficio_campanha_create"),
    path("beneficios/campanhas/<int:pk>/", views_beneficios.beneficio_campanha_detail, name="beneficio_campanha_detail"),
    path("beneficios/campanhas/<int:pk>/editar/", views_beneficios.beneficio_campanha_update, name="beneficio_campanha_update"),
    path("beneficios/campanhas/<int:pk>/alunos/adicionar/", views_beneficios.beneficio_campanha_aluno_add, name="beneficio_campanha_aluno_add"),
    path(
        "beneficios/campanhas/<int:pk>/alunos/gerar-turma/",
        views_beneficios.beneficio_campanha_gerar_alunos_turma,
        name="beneficio_campanha_gerar_alunos_turma",
    ),

    path("beneficios/entregas/", views_beneficios.beneficio_entrega_list, name="beneficio_entrega_list"),
    path("beneficios/entregas/nova/", views_beneficios.beneficio_entrega_create, name="beneficio_entrega_create"),
    path("beneficios/entregas/<int:pk>/", views_beneficios.beneficio_entrega_detail, name="beneficio_entrega_detail"),
    path("beneficios/entregas/<int:pk>/editar/", views_beneficios.beneficio_entrega_update, name="beneficio_entrega_update"),
    path("beneficios/entregas/<int:pk>/itens/adicionar/", views_beneficios.beneficio_entrega_item_add, name="beneficio_entrega_item_add"),
    path("beneficios/entregas/<int:pk>/itens/<int:item_id>/remover/", views_beneficios.beneficio_entrega_item_remove, name="beneficio_entrega_item_remove"),
    path("beneficios/entregas/<int:pk>/confirmar/", views_beneficios.beneficio_entrega_confirmar, name="beneficio_entrega_confirmar"),
    path("beneficios/entregas/<int:pk>/estornar/", views_beneficios.beneficio_entrega_estornar, name="beneficio_entrega_estornar"),
    path("beneficios/entregas/<int:pk>/recibo.pdf", views_beneficios.beneficio_entrega_recibo_pdf, name="beneficio_entrega_recibo_pdf"),

    path("beneficios/editais/", views_beneficios.beneficio_edital_list, name="beneficio_edital_list"),
    path("beneficios/editais/novo/", views_beneficios.beneficio_edital_create, name="beneficio_edital_create"),
    path("beneficios/editais/<int:pk>/", views_beneficios.beneficio_edital_detail, name="beneficio_edital_detail"),
    path("beneficios/editais/<int:pk>/editar/", views_beneficios.beneficio_edital_update, name="beneficio_edital_update"),
    path("beneficios/editais/<int:pk>/publicar/", views_beneficios.beneficio_edital_publicar, name="beneficio_edital_publicar"),
    path("beneficios/editais/<int:pk>/criterios/adicionar/", views_beneficios.beneficio_edital_criterio_add, name="beneficio_edital_criterio_add"),
    path("beneficios/editais/<int:pk>/documentos/adicionar/", views_beneficios.beneficio_edital_documento_add, name="beneficio_edital_documento_add"),
    path("beneficios/editais/<int:pk>/inscricoes/adicionar/", views_beneficios.beneficio_edital_inscricao_add, name="beneficio_edital_inscricao_add"),
    path(
        "beneficios/editais/<int:pk>/inscricoes/<int:inscricao_id>/",
        views_beneficios.beneficio_edital_inscricao_detail,
        name="beneficio_edital_inscricao_detail",
    ),
    path(
        "beneficios/editais/<int:pk>/inscricoes/<int:inscricao_id>/reprocessar/",
        views_beneficios.beneficio_edital_inscricao_reprocessar,
        name="beneficio_edital_inscricao_reprocessar",
    ),
    path(
        "beneficios/editais/<int:pk>/inscricoes/<int:inscricao_id>/analisar/",
        views_beneficios.beneficio_edital_inscricao_analisar,
        name="beneficio_edital_inscricao_analisar",
    ),

    path("beneficios/recorrencias/", views_beneficios.beneficio_recorrencia_list, name="beneficio_recorrencia_list"),
    path("beneficios/recorrencias/nova/", views_beneficios.beneficio_recorrencia_create, name="beneficio_recorrencia_create"),
    path("beneficios/recorrencias/<int:pk>/", views_beneficios.beneficio_recorrencia_detail, name="beneficio_recorrencia_detail"),
    path("beneficios/recorrencias/<int:pk>/editar/", views_beneficios.beneficio_recorrencia_update, name="beneficio_recorrencia_update"),
    path("beneficios/recorrencias/<int:pk>/gerar-ciclos/", views_beneficios.beneficio_recorrencia_gerar_ciclos, name="beneficio_recorrencia_gerar_ciclos"),
    path(
        "beneficios/recorrencias/<int:pk>/ciclos/<int:ciclo_id>/executar/",
        views_beneficios.beneficio_recorrencia_executar_ciclo,
        name="beneficio_recorrencia_executar_ciclo",
    ),
    path("api/alunos-suggest/", views_api.api_alunos_suggest, name="api_alunos_suggest"),
    path("api/turmas-suggest/", views_api.api_turmas_suggest, name="api_turmas_suggest"),
    path("calendario/", views_calendario.calendario_index, name="calendario_index"),
    path("calendario/eventos/novo/", views_calendario.calendario_evento_create, name="calendario_evento_create"),
    path("calendario/eventos/<int:pk>/editar/", views_calendario.calendario_evento_update, name="calendario_evento_update"),
    path("calendario/eventos/<int:pk>/excluir/", views_calendario.calendario_evento_delete, name="calendario_evento_delete"),

    # ======================
    # RELATÓRIO MENSAL
    # ======================
    path("relatorios/mensal/", views_relatorios.relatorio_mensal, name="relatorio_mensal"),
    path("relatorios/indicadores/", views_indicadores.indicadores_gerenciais, name="indicadores_gerenciais"),
    path("censo/", views_censo.censo_escolar, name="censo_escolar"),

    # ======================
    # DIÁRIO
    # ======================
    path("diario/", require_perm("educacao.view")(DiarioListView.as_view()), name="meus_diarios"),
    path("diario/justificativas/", views_diario.justificativa_falta_list, name="justificativa_falta_list"),
    path("diario/justificativas/<int:pk>/", views_diario.justificativa_falta_detail, name="justificativa_falta_detail"),
    path("diario/<int:pk>/", views_diario.diario_detail, name="diario_detail"),
    path("diario/<int:pk>/aulas/nova/", views_diario.aula_create, name="aula_create"),
    path("diario/<int:pk>/aulas/<int:aula_id>/editar/", views_diario.aula_update, name="aula_update"),
    path("diario/<int:pk>/frequencia/<int:aula_id>/", views_diario.aula_frequencia, name="aula_frequencia"),
    path("api/turmas/<int:pk>/alunos-suggest/", views_diario.api_alunos_turma_suggest, name="api_alunos_turma_suggest"),

    # Avaliações / Notas (mantém FBV por enquanto)
    path("diario/<int:pk>/avaliacoes/", views_notas.avaliacao_list, name="avaliacao_list"),
    path("diario/<int:pk>/avaliacoes/nova/", views_notas.avaliacao_create, name="avaliacao_create"),
    path("avaliacoes/<int:pk>/notas/", views_notas.notas_lancar, name="notas_lancar"),

    # ======================
    # HORÁRIOS (INDEX + CRUD)
    # ======================
    path("horarios/", require_perm("educacao.view")(HorariosIndexView.as_view()), name="horarios_index"),
    path("horarios/turma/<int:turma_id>/", horario_turma, name="horario_turma"),
    path("horarios/turma/<int:turma_id>/aula/nova/", horario_aula_create, name="horario_aula_create"),
    path("horarios/turma/<int:turma_id>/aula/<int:pk>/editar/", horario_aula_update, name="horario_aula_update"),
    path("horarios/turma/<int:turma_id>/gerar-padrao/", horario_gerar_padrao, name="horario_gerar_padrao"),
    path("horarios/turma/<int:turma_id>/duplicar/", horario_duplicar_select, name="horario_duplicar_select"),
    path("horarios/turma/<int:turma_id>/duplicar/executar/", horario_duplicar, name="horario_duplicar"),
    path("horarios/turma/<int:turma_id>/limpar/", horario_limpar, name="horario_limpar"),

    # ======================
    # PERÍODOS LETIVOS
    # ======================
    path("periodos/", require_perm("educacao.view")(PeriodoListView.as_view()), name="periodo_list"),
    path("periodos/novo/", periodo_create, name="periodo_create"),
    path("periodos/<int:pk>/editar/", periodo_update, name="periodo_update"),
    path("periodos/gerar-bimestres/", periodo_gerar_bimestres, name="periodo_gerar_bimestres"),

    # ======================
    # COMPONENTES CURRICULARES
    # ======================
    path("componentes/", views_componentes.componente_list, name="componente_list"),
    path("componentes/novo/", views_componentes.componente_create, name="componente_create"),
    path("componentes/<int:pk>/", views_componentes.componente_detail, name="componente_detail"),
    path("componentes/<int:pk>/editar/", views_componentes.componente_update, name="componente_update"),

    # Catálogos acadêmicos
    path("cursos/", views_catalogos.curso_list, name="curso_list"),
    path("cursos/novo/", views_catalogos.curso_create, name="curso_create"),
    path("cursos/<int:pk>/editar/", views_catalogos.curso_update, name="curso_update"),
    path("matrizes/", views_catalogos.matriz_list, name="matriz_list"),
    path("matrizes/modelos/", views_catalogos.matriz_modelos, name="matriz_modelos"),
    path("matrizes/nova/", views_catalogos.matriz_create, name="matriz_create"),
    path("matrizes/<int:pk>/editar/", views_catalogos.matriz_update, name="matriz_update"),
    path("matrizes/<int:pk>/equivalencias/", views_catalogos.matriz_equivalencias, name="matriz_equivalencias"),
    path("matrizes/<int:pk>/consistencia/", views_catalogos.matriz_consistencia, name="matriz_consistencia"),
    path("coordenacao/", views_catalogos.coordenacao_list, name="coordenacao_list"),
    path("coordenacao/nova/", views_catalogos.coordenacao_create, name="coordenacao_create"),
    path("coordenacao/<int:pk>/editar/", views_catalogos.coordenacao_update, name="coordenacao_update"),
    path("estagios/", views_estagios.estagio_list, name="estagio_list"),
    path("estagios/novo/", views_estagios.estagio_create, name="estagio_create"),
    path("estagios/<int:pk>/", views_estagios.estagio_detail, name="estagio_detail"),
    path("estagios/<int:pk>/editar/", views_estagios.estagio_update, name="estagio_update"),

    # ======================
    # CURSO DE INFORMÁTICA / LABORATÓRIOS
    # ======================
    path("informatica/", views_informatica.informatica_index, name="informatica_index"),
    path("informatica/cursos/", views_informatica.informatica_curso_list, name="informatica_curso_list"),
    path("informatica/cursos/novo/", views_informatica.informatica_curso_create, name="informatica_curso_create"),
    path("informatica/cursos/<int:pk>/editar/", views_informatica.informatica_curso_update, name="informatica_curso_update"),

    path("informatica/laboratorios/", views_informatica.informatica_laboratorio_list, name="informatica_laboratorio_list"),
    path("informatica/laboratorios/novo/", views_informatica.informatica_laboratorio_create, name="informatica_laboratorio_create"),
    path("informatica/laboratorios/<int:pk>/editar/", views_informatica.informatica_laboratorio_update, name="informatica_laboratorio_update"),

    path("informatica/grades/", views_informatica.informatica_grade_list, name="informatica_grade_list"),
    path("informatica/grades/nova/", views_informatica.informatica_grade_create, name="informatica_grade_create"),
    path("informatica/grades/<int:pk>/editar/", views_informatica.informatica_grade_update, name="informatica_grade_update"),
    path("informatica/grades/<int:pk>/duplicar/", views_informatica.informatica_grade_duplicate, name="informatica_grade_duplicate"),
    path("informatica/grades/<int:pk>/toggle/", views_informatica.informatica_grade_toggle, name="informatica_grade_toggle"),

    path("informatica/turmas/", views_informatica.informatica_turma_list, name="informatica_turma_list"),
    path("informatica/turmas/nova/", views_informatica.informatica_turma_create, name="informatica_turma_create"),
    path("informatica/turmas/<int:pk>/", views_informatica.informatica_turma_detail, name="informatica_turma_detail"),
    path("informatica/turmas/<int:pk>/editar/", views_informatica.informatica_turma_update, name="informatica_turma_update"),

    path("informatica/solicitacoes/", views_informatica.informatica_solicitacao_list, name="informatica_solicitacao_list"),
    path("informatica/solicitacoes/nova/", views_informatica.informatica_solicitacao_create, name="informatica_solicitacao_create"),
    path("informatica/solicitacoes/<int:pk>/lista-espera/", views_informatica.informatica_solicitacao_lista, name="informatica_solicitacao_lista"),

    path("informatica/matriculas/", views_informatica.informatica_matricula_list, name="informatica_matricula_list"),
    path("informatica/matriculas/nova/", views_informatica.informatica_matricula_create, name="informatica_matricula_create"),
    path(
        "informatica/matriculas/<int:pk>/remanejar/",
        views_informatica.informatica_matricula_remanejar,
        name="informatica_matricula_remanejar",
    ),
    path("informatica/matriculas/<int:pk>/cancelar/", views_informatica.informatica_matricula_cancelar, name="informatica_matricula_cancelar"),
    path("informatica/alunos/novo/", views_informatica.informatica_aluno_create, name="informatica_aluno_create"),
    path("informatica/api/aluno/<int:aluno_id>/origem/", views_informatica.informatica_api_aluno_origem, name="informatica_api_aluno_origem"),

    path("informatica/lista-espera/", views_informatica.informatica_lista_espera, name="informatica_lista_espera"),

    path("informatica/frequencia/", views_informatica.informatica_aula_list, name="informatica_frequencia"),
    path("informatica/aulas/nova/", views_informatica.informatica_aula_create, name="informatica_aula_create"),
    path("informatica/aulas/<int:pk>/editar/", views_informatica.informatica_aula_update, name="informatica_aula_update"),
    path("informatica/aulas/<int:pk>/frequencia/", views_informatica.informatica_frequencia_aula, name="informatica_frequencia_aula"),

    path("informatica/agenda/", views_informatica.informatica_agenda, name="informatica_agenda"),
    path("informatica/professor/agenda/", views_informatica.informatica_professor_agenda, name="informatica_professor_agenda"),
    path("informatica/relatorios/", views_informatica.informatica_relatorios, name="informatica_relatorios"),
    path("informatica/ocorrencias/", views_informatica.informatica_ocorrencia_list, name="informatica_ocorrencia_list"),

    # ======================
    # BOLETINS / RELATÓRIOS
    # ======================
    path("boletim/turma/<int:pk>/", boletim_turma, name="boletim_turma"),
    path("boletim/turma/<int:pk>/aluno/<int:aluno_id>/", boletim_aluno, name="boletim_aluno"),
    path("boletim/turma/<int:pk>/periodo/", boletim_turma_periodo, name="boletim_turma_periodo"),
    path("relatorios/turma/<int:pk>/", relatorio_geral_turma, name="relatorio_geral_turma"),
    path("turmas/<int:pk>/fechamento/", views_fechamento.fechamento_turma_periodo, name="fechamento_turma_periodo"),
]
