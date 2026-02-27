from django.urls import path

from . import views

app_name = "patrimonio"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("bens/", views.bem_list, name="bem_list"),
    path("bens/novo/", views.bem_create, name="bem_create"),
    path("bens/<int:pk>/editar/", views.bem_update, name="bem_update"),
    path("movimentacoes/", views.movimentacao_list, name="movimentacao_list"),
    path("movimentacoes/nova/", views.movimentacao_create, name="movimentacao_create"),
    path("inventarios/", views.inventario_list, name="inventario_list"),
    path("inventarios/novo/", views.inventario_create, name="inventario_create"),
    path("inventarios/<int:pk>/concluir/", views.inventario_concluir, name="inventario_concluir"),
]
