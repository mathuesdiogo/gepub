from django.urls import path

from . import views

app_name = "folha"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("rubricas/", views.rubrica_list, name="rubrica_list"),
    path("rubricas/nova/", views.rubrica_create, name="rubrica_create"),
    path("rubricas/<int:pk>/editar/", views.rubrica_update, name="rubrica_update"),
    path("competencias/", views.competencia_list, name="competencia_list"),
    path("competencias/nova/", views.competencia_create, name="competencia_create"),
    path("competencias/<int:pk>/processar/", views.competencia_processar, name="competencia_processar"),
    path("competencias/<int:pk>/fechar/", views.competencia_fechar, name="competencia_fechar"),
    path("competencias/<int:pk>/reabrir/", views.competencia_reabrir, name="competencia_reabrir"),
    path("competencias/<int:competencia_pk>/enviar-financeiro/", views.enviar_financeiro, name="enviar_financeiro"),
    path("lancamentos/", views.lancamento_list, name="lancamento_list"),
    path("lancamentos/novo/", views.lancamento_create, name="lancamento_create"),
    path(
        "competencias/<int:competencia_pk>/holerite/<int:servidor_id>/pdf/",
        views.holerite_pdf,
        name="holerite_pdf",
    ),
]
