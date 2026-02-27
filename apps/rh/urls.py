from django.urls import path

from . import views

app_name = "rh"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("servidores/", views.servidor_list, name="servidor_list"),
    path("servidores/novo/", views.servidor_create, name="servidor_create"),
    path("servidores/<int:pk>/editar/", views.servidor_update, name="servidor_update"),
    path("movimentacoes/", views.movimentacao_list, name="movimentacao_list"),
    path("movimentacoes/nova/", views.movimentacao_create, name="movimentacao_create"),
    path("movimentacoes/<int:pk>/aprovar/", views.movimentacao_aprovar, name="movimentacao_aprovar"),
    path("movimentacoes/<int:pk>/recusar/", views.movimentacao_recusar, name="movimentacao_recusar"),
    path("documentos/", views.documento_list, name="documento_list"),
    path("documentos/novo/", views.documento_create, name="documento_create"),
]
