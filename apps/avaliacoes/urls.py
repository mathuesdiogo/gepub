from django.urls import path

from . import views

app_name = "avaliacoes"

urlpatterns = [
    path("", views.avaliacao_list, name="avaliacao_list"),
    path("index/", views.index, name="index"),
    path("nova/", views.avaliacao_create, name="avaliacao_create"),
    path("<int:pk>/", views.avaliacao_detail, name="avaliacao_detail"),
    path("<int:pk>/sincronizar/", views.avaliacao_sync, name="avaliacao_sync"),
    path("<int:avaliacao_pk>/questoes/nova/", views.questao_create, name="questao_create"),
    path(
        "<int:avaliacao_pk>/questoes/<int:questao_pk>/editar/",
        views.questao_update,
        name="questao_update",
    ),
    path(
        "<int:avaliacao_pk>/gabarito/<str:versao>/",
        views.gabarito_update,
        name="gabarito_update",
    ),
    path("<int:avaliacao_pk>/resultados/", views.resultados, name="resultados"),
    path("<int:avaliacao_pk>/resultados.csv", views.resultados_csv, name="resultados_csv"),
    path("<int:avaliacao_pk>/provas.pdf", views.prova_pdf, name="prova_pdf"),
    path("resposta/localizar/", views.folha_token_lookup, name="folha_lookup"),
    path("resposta/<uuid:token>/corrigir/", views.folha_corrigir, name="folha_corrigir"),
    path("validar/prova/<uuid:token>/", views.folha_validar, name="folha_validar"),
]
