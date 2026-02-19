from django.urls import path
from . import views
from . import views_relatorios
from . import views_diario
from . import views_notas
from apps.educacao.views_horarios import horario_turma, horario_aula_create, horario_aula_update

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



]
