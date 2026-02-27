from django.urls import path

from . import views

app_name = "ouvidoria"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("chamados/", views.chamado_list, name="chamado_list"),
    path("chamados/novo/", views.chamado_create, name="chamado_create"),
    path("chamados/<int:pk>/concluir/", views.chamado_concluir, name="chamado_concluir"),
    path("tramitacoes/", views.tramitacao_list, name="tramitacao_list"),
    path("tramitacoes/nova/", views.tramitacao_create, name="tramitacao_create"),
    path("respostas/", views.resposta_list, name="resposta_list"),
    path("respostas/nova/", views.resposta_create, name="resposta_create"),
]
