from django.urls import path
from . import views
from . import views_unidades
from . import views_profissionais
from . import views_atendimentos
from . import views_api
from . import views_relatorios

app_name = "saude"

urlpatterns = [
    path("", views.index, name="index"),

    path("unidades/", views_unidades.unidade_list, name="unidade_list"),
    path("unidades/nova/", views_unidades.unidade_create, name="unidade_create"),
    path("unidades/<int:pk>/", views_unidades.unidade_detail, name="unidade_detail"),
    path("unidades/<int:pk>/editar/", views_unidades.unidade_update, name="unidade_update"),

    path("profissionais/", views_profissionais.profissional_list, name="profissional_list"),
    path("profissionais/novo/", views_profissionais.profissional_create, name="profissional_create"),
    path("profissionais/<int:pk>/", views_profissionais.profissional_detail, name="profissional_detail"),
    path("profissionais/<int:pk>/editar/", views_profissionais.profissional_update, name="profissional_update"),

    path("atendimentos/", views_atendimentos.atendimento_list, name="atendimento_list"),
    path("atendimentos/novo/", views_atendimentos.atendimento_create, name="atendimento_create"),
    path("atendimentos/<int:pk>/", views_atendimentos.atendimento_detail, name="atendimento_detail"),
    path("atendimentos/<int:pk>/editar/", views_atendimentos.atendimento_update, name="atendimento_update"),

    # API (UX)
    path("api/profissionais-por-unidade/", views_api.api_profissionais_por_unidade, name="api_profissionais_por_unidade"),
    path("api/profissionais/suggest/", views_profissionais.api_profissionais_suggest, name="api_profissionais_suggest"),
    path("api/unidades/suggest/", views_unidades.api_unidades_suggest, name="api_unidades_suggest"),
    path("relatorios/mensal/", views_relatorios.relatorio_mensal, name="relatorio_mensal"),

]
