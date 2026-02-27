from django.urls import path

from . import views

app_name = "compras"

urlpatterns = [
    path("", views.index, name="index"),
    path("requisicoes/", views.requisicao_list, name="requisicao_list"),
    path("requisicoes/nova/", views.requisicao_create, name="requisicao_create"),
    path("requisicoes/<int:pk>/", views.requisicao_detail, name="requisicao_detail"),
    path("requisicoes/<int:requisicao_pk>/itens/novo/", views.item_create, name="item_create"),
    path("requisicoes/<int:pk>/aprovar/", views.aprovar, name="aprovar"),
    path("requisicoes/<int:pk>/gerar-empenho/", views.gerar_empenho, name="gerar_empenho"),
    path("licitacoes/", views.licitacao_list, name="licitacao_list"),
    path("licitacoes/nova/", views.licitacao_create, name="licitacao_create"),
]
