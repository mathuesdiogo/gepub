from django.urls import path

from . import views

app_name = "almoxarifado"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("itens/", views.item_list, name="item_list"),
    path("itens/novo/", views.item_create, name="item_create"),
    path("itens/<int:pk>/editar/", views.item_update, name="item_update"),
    path("movimentos/", views.movimento_list, name="movimento_list"),
    path("movimentos/novo/", views.movimento_create, name="movimento_create"),
    path("requisicoes/", views.requisicao_list, name="requisicao_list"),
    path("requisicoes/nova/", views.requisicao_create, name="requisicao_create"),
    path("requisicoes/<int:pk>/aprovar/", views.requisicao_aprovar, name="requisicao_aprovar"),
    path("requisicoes/<int:pk>/atender/", views.requisicao_atender, name="requisicao_atender"),
]
