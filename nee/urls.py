from django.urls import path
from . import views

app_name = "nee"

urlpatterns = [
    path("", views.index, name="index"),

    # Tipos de Necessidade
    path("tipos/", views.TipoListView.as_view(), name="tipo_list"),
    path("tipos/novo/", views.TipoCreateView.as_view(), name="tipo_create"),
    path("tipos/<int:pk>/", views.TipoDetailView.as_view(), name="tipo_detail"),
    path("tipos/<int:pk>/editar/", views.TipoUpdateView.as_view(), name="tipo_update"),

    # Necessidades do aluno
    path("alunos/<int:aluno_id>/necessidades/", views.AlunoNecessidadeListView.as_view(), name="aluno_necessidade_list"),
    path("alunos/<int:aluno_id>/necessidades/novo/", views.AlunoNecessidadeCreateView.as_view(), name="aluno_necessidade_create"),
    path("alunos/<int:aluno_id>/necessidades/<int:pk>/", views.AlunoNecessidadeDetailView.as_view(), name="aluno_necessidade_detail"),
    path("alunos/<int:aluno_id>/necessidades/<int:pk>/editar/", views.AlunoNecessidadeUpdateView.as_view(), name="aluno_necessidade_update"),

    # Apoios da matrícula (por aluno)
    path("alunos/<int:aluno_id>/apoios/", views.ApoioListView.as_view(), name="apoio_list"),
    path("alunos/<int:aluno_id>/apoios/novo/", views.ApoioCreateView.as_view(), name="apoio_create"),
    path("alunos/<int:aluno_id>/apoios/<int:pk>/", views.ApoioDetailView.as_view(), name="apoio_detail"),
    path("alunos/<int:aluno_id>/apoios/<int:pk>/editar/", views.ApoioUpdateView.as_view(), name="apoio_update"),


    # Laudos (por aluno)
    path("alunos/<int:aluno_id>/laudos/", views.LaudoListView.as_view(), name="laudo_list"),
    path("alunos/<int:aluno_id>/laudos/novo/", views.LaudoCreateView.as_view(), name="laudo_create"),
    path("alunos/<int:aluno_id>/laudos/<int:pk>/", views.LaudoDetailView.as_view(), name="laudo_detail"),
    path("alunos/<int:aluno_id>/laudos/<int:pk>/editar/", views.LaudoUpdateView.as_view(), name="laudo_update"),

    # Recursos/Adaptações (por aluno)
    path("alunos/<int:aluno_id>/recursos/", views.RecursoListView.as_view(), name="recurso_list"),
    path("alunos/<int:aluno_id>/recursos/novo/", views.RecursoCreateView.as_view(), name="recurso_create"),
    path("alunos/<int:aluno_id>/recursos/<int:pk>/", views.RecursoDetailView.as_view(), name="recurso_detail"),
    path("alunos/<int:aluno_id>/recursos/<int:pk>/editar/", views.RecursoUpdateView.as_view(), name="recurso_update"),

    # Acompanhamentos (por aluno)
    path("alunos/<int:aluno_id>/acompanhamentos/", views.AcompanhamentoListView.as_view(), name="acompanhamento_list"),
    path("alunos/<int:aluno_id>/acompanhamentos/novo/", views.AcompanhamentoCreateView.as_view(), name="acompanhamento_create"),
    path("alunos/<int:aluno_id>/acompanhamentos/<int:pk>/", views.AcompanhamentoDetailView.as_view(), name="acompanhamento_detail"),
    path("alunos/<int:aluno_id>/acompanhamentos/<int:pk>/editar/", views.AcompanhamentoUpdateView.as_view(), name="acompanhamento_update"),


    # Relatórios
    path("relatorios/", views.relatorios_index, name="relatorios_index"),
    path("relatorios/por-tipo/", views.relatorio_por_tipo, name="relatorio_por_tipo"),
    path("relatorios/por-municipio/", views.relatorio_por_municipio, name="relatorio_por_municipio"),
    path("relatorios/por-unidade/", views.relatorio_por_unidade, name="relatorio_por_unidade"),
]
