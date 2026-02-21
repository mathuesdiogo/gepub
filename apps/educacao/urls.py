from django.urls import path

from . import views
from . import views_relatorios
from . import views_diario
from . import views_horarios
from . import views_notas
from . import views_matriculas
from .views_turmas_list import TurmaListView
from .views_alunos_list import AlunoListView
from .views_diarios_list import DiarioListView
from .views_periodos_list import PeriodoListView
from .views_horarios_index_list import HorariosIndexView

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
    path("turmas/", TurmaListView.as_view(), name="turma_list"),
    path("turmas/novo/", views.turma_create, name="turma_create"),
    path("turmas/<int:pk>/", views.turma_detail, name="turma_detail"),
    path("turmas/<int:pk>/editar/", views.turma_update, name="turma_update"),

    # ======================
    # ALUNOS
    # ======================
    path("alunos/", AlunoListView.as_view(), name="aluno_list"),
    path("alunos/novo/", views.aluno_create, name="aluno_create"),
    path("alunos/<int:pk>/", views.aluno_detail, name="aluno_detail"),
    path("alunos/<int:pk>/editar/", views.aluno_update, name="aluno_update"),
    path("matriculas/nova/", views_matriculas.matricula_create, name="matricula_create"),
    path("api/alunos-suggest/", views.api_alunos_suggest, name="api_alunos_suggest"),
    path("api/turmas-suggest/", views.api_turmas_suggest, name="api_turmas_suggest"),

    # ======================
    # RELATÓRIO MENSAL
    # ======================
    path("relatorios/mensal/", views_relatorios.relatorio_mensal, name="relatorio_mensal"),

    # ======================
    # DIÁRIO
    # ======================
    path("diario/", DiarioListView.as_view(), name="meus_diarios"),
    path("diario/<int:pk>/", views_diario.diario_detail, name="diario_detail"),
    path("diario/<int:pk>/aulas/nova/", views_diario.aula_create, name="aula_create"),
    path("diario/<int:pk>/aulas/<int:aula_id>/editar/", views_diario.aula_update, name="aula_update"),
    path("diario/<int:pk>/frequencia/<int:aula_id>/", views_diario.aula_frequencia, name="aula_frequencia"),

    # Avaliações / Notas (mantém FBV por enquanto)
    path("diario/<int:pk>/avaliacoes/", views_notas.avaliacao_list, name="avaliacao_list"),
    path("diario/<int:pk>/avaliacoes/nova/", views_notas.avaliacao_create, name="avaliacao_create"),
    path("avaliacoes/<int:pk>/notas/", views_notas.notas_lancar, name="notas_lancar"),

    # ======================
    # HORÁRIOS (INDEX + CRUD)
    # ======================
    path("horarios/", HorariosIndexView.as_view(), name="horarios_index"),
    path("horarios/turma/<int:turma_id>/", horario_turma, name="horario_turma"),
    path("horarios/turma/<int:turma_id>/aula/nova/", horario_aula_create, name="horario_aula_create"),
    path("horarios/turma/<int:turma_id>/aula/<int:pk>/editar/", horario_aula_update, name="horario_aula_update"),
    path("horarios/turma/<int:turma_id>/gerar-padrao/", horario_gerar_padrao, name="horario_gerar_padrao"),
    path("horarios/duplicar/", horario_duplicar_select, name="horario_duplicar_select"),
    path("horarios/duplicar/executar/", horario_duplicar, name="horario_duplicar"),
    path("horarios/turma/<int:turma_id>/limpar/", horario_limpar, name="horario_limpar"),

    # ======================
    # PERÍODOS LETIVOS
    # ======================
    path("periodos/", PeriodoListView.as_view(), name="periodo_list"),
    path("periodos/novo/", periodo_create, name="periodo_create"),
    path("periodos/<int:pk>/editar/", periodo_update, name="periodo_update"),
    path("periodos/gerar-bimestres/", periodo_gerar_bimestres, name="periodo_gerar_bimestres"),

    # ======================
    # BOLETINS / RELATÓRIOS
    # ======================
    path("boletim/turma/<int:pk>/", boletim_turma, name="boletim_turma"),
    path("boletim/aluno/<int:pk>/", boletim_aluno, name="boletim_aluno"),
    path("boletim/turma/<int:pk>/periodo/", boletim_turma_periodo, name="boletim_turma_periodo"),
    path("relatorios/turma/<int:pk>/", relatorio_geral_turma, name="relatorio_geral_turma"),
    
    path("turmas/<int:pk>/", views.TurmaDetailView.as_view(), name="turma_detail"),
    path("alunos/<int:pk>/", views.AlunoDetailView.as_view(), name="aluno_detail"),
]
