from django.urls import path

from . import views

app_name = "frota"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("veiculos/", views.veiculo_list, name="veiculo_list"),
    path("veiculos/novo/", views.veiculo_create, name="veiculo_create"),
    path("veiculos/<int:pk>/editar/", views.veiculo_update, name="veiculo_update"),
    path("abastecimentos/", views.abastecimento_list, name="abastecimento_list"),
    path("abastecimentos/novo/", views.abastecimento_create, name="abastecimento_create"),
    path("manutencoes/", views.manutencao_list, name="manutencao_list"),
    path("manutencoes/nova/", views.manutencao_create, name="manutencao_create"),
    path("manutencoes/<int:pk>/concluir/", views.manutencao_concluir, name="manutencao_concluir"),
    path("viagens/", views.viagem_list, name="viagem_list"),
    path("viagens/nova/", views.viagem_create, name="viagem_create"),
    path("viagens/<int:pk>/concluir/", views.viagem_concluir, name="viagem_concluir"),
]
