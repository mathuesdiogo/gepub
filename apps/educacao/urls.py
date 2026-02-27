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
from . import views_carteira
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
    path("carteira/validar/", views_carteira.carteira_verificar_public, name="carteira_verificar_lookup"),
    path("carteira/validar/<uuid:codigo>/", views_carteira.carteira_verificar_public, name="carteira_verificar_public"),
    path("alunos/<int:pk>/historico/", views_historico.historico_aluno, name="historico_aluno"),
    path("matriculas/nova/", views_matriculas.matricula_create, name="matricula_create"),
    path("portal/professor/", views_portal.portal_professor, name="portal_professor"),
    path("portal/aluno/<int:pk>/", views_portal.portal_aluno, name="portal_aluno"),
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
    path("coordenacao/", views_catalogos.coordenacao_list, name="coordenacao_list"),
    path("coordenacao/nova/", views_catalogos.coordenacao_create, name="coordenacao_create"),
    path("coordenacao/<int:pk>/editar/", views_catalogos.coordenacao_update, name="coordenacao_update"),

    # ======================
    # BOLETINS / RELATÓRIOS
    # ======================
    path("boletim/turma/<int:pk>/", boletim_turma, name="boletim_turma"),
    path("boletim/turma/<int:pk>/aluno/<int:aluno_id>/", boletim_aluno, name="boletim_aluno"),
    path("boletim/turma/<int:pk>/periodo/", boletim_turma_periodo, name="boletim_turma_periodo"),
    path("relatorios/turma/<int:pk>/", relatorio_geral_turma, name="relatorio_geral_turma"),
    path("turmas/<int:pk>/fechamento/", views_fechamento.fechamento_turma_periodo, name="fechamento_turma_periodo"),
]
