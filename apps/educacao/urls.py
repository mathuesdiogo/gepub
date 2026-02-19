from django.urls import path
from . import views
from . import views_relatorios
from . import views_diario
from . import views_horarios

from . import views_notas
from apps.educacao.views_horarios import horario_turma, horario_aula_create, horario_aula_update
from apps.educacao.views_boletim import boletim_turma, boletim_aluno
from apps.educacao.views_relatorios_turma import relatorio_geral_turma
from apps.educacao.views_boletim_periodo import boletim_turma_periodo
from apps.educacao.views_periodos import periodo_list, periodo_create, periodo_update
from apps.educacao.views_periodos import periodo_list, periodo_create, periodo_update, periodo_gerar_bimestres

from apps.educacao.views_horarios_index import horarios_index
from apps.educacao.views_horarios import horario_turma, horario_aula_create, horario_aula_update
from .views_horarios import horario_gerar_padrao, horario_duplicar

app_name = "educacao"

urlpatterns = [
    path("", views.index, name="index"),
    path("turmas/", views.turma_list, name="turma_list"),
    path("turmas/novo/", views.turma_create, name="turma_create"),
    path("turmas/<int:pk>/", views.turma_detail, name="turma_detail"),
    path("turmas/<int:pk>/editar/", views.turma_update, name="turma_update"),
    # Alunos
    path("alunos/", views.aluno_list, name="aluno_list"),
    path("alunos/novo/", views.aluno_create, name="aluno_create"),
    path("alunos/<int:pk>/", views.aluno_detail, name="aluno_detail"),
    path("alunos/<int:pk>/editar/", views.aluno_update, name="aluno_update"),
    path("matriculas/nova/", views.matricula_create, name="matricula_create"),
    path("api/alunos-suggest/", views.api_alunos_suggest, name="api_alunos_suggest"),
    path("api/turmas-suggest/", views.api_turmas_suggest, name="api_turmas_suggest"),
    path("relatorios/mensal/", views_relatorios.relatorio_mensal, name="relatorio_mensal"),
    
    # DIÁRIO
    path("diario/", views_diario.meus_diarios, name="meus_diarios"),
    path("diario/<int:pk>/", views_diario.diario_detail, name="diario_detail"),
    path("aula/<int:pk>/frequencia/", views_diario.aula_frequencia, name="aula_frequencia"),
    path("diario/<int:pk>/aulas/nova/", views_diario.aula_create, name="aula_create"),
    path("api/turmas/<int:pk>/alunos/suggest/", views_diario.api_alunos_turma_suggest, name="api_alunos_turma_suggest"),

    path("diario/<int:pk>/avaliacoes/", views_notas.avaliacao_list, name="avaliacao_list"),
    path("diario/<int:pk>/avaliacoes/nova/", views_notas.avaliacao_create, name="avaliacao_create"),
    path("avaliacoes/<int:pk>/notas/", views_notas.notas_lancar, name="notas_lancar"),
    path("diario/turma/<int:pk>/criar/", views_diario.diario_create_for_turma, name="diario_create_for_turma"),
    path("turmas/<int:pk>/diario/", views_diario.diario_turma_entry, name="turma_diario"),

    path("turmas/<int:pk>/horario/", horario_turma, name="horario_turma"),
    path("turmas/<int:pk>/horario/aulas/nova/", horario_aula_create, name="horario_aula_create"),
    path("turmas/<int:pk>/horario/aulas/<int:aula_id>/editar/", horario_aula_update, name="horario_aula_update"),

    path("turmas/<int:pk>/boletim/", boletim_turma, name="boletim_turma"),
    path("turmas/<int:pk>/boletim/aluno/<int:aluno_id>/", boletim_aluno, name="boletim_aluno"),
    path("turmas/<int:pk>/relatorio/geral/", relatorio_geral_turma, name="relatorio_geral_turma"),
    path("turmas/<int:pk>/boletim/periodo/", boletim_turma_periodo, name="boletim_turma_periodo"),

    path("periodos/", periodo_list, name="periodo_list"),
    path("periodos/novo/", periodo_create, name="periodo_create"),
    path("periodos/<int:pk>/editar/", periodo_update, name="periodo_update"),
    path("periodos/gerar-bimestres/", periodo_gerar_bimestres, name="periodo_gerar_bimestres"),
    
    
    path("turmas/<int:pk>/horario/", horario_turma, name="horario_turma"),
    path("turmas/<int:turma_pk>/horario/aulas/nova/", horario_aula_create, name="horario_aula_create"),
    path("turmas/<int:turma_pk>/horario/aulas/<int:pk>/editar/", horario_aula_update, name="horario_aula_update"),
    path("horarios/", horarios_index, name="horarios_index"),
    path("turmas/<int:pk>/horario/gerar-padrao/", views_horarios.horario_gerar_padrao, name="horario_gerar_padrao"),
    path("turmas/<int:pk>/horario/duplicar/", views_horarios.horario_duplicar, name="horario_duplicar"),
    path("turmas/<int:pk>/horario/duplicar/selecionar/", views_horarios.horario_duplicar_select, name="horario_duplicar_select"),
    path("turmas/<int:pk>/horario/limpar/", views_horarios.horario_limpar, name="horario_limpar"),

]
