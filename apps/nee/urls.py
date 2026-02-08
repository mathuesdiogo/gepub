from django.urls import path
from . import views

app_name = "nee"

urlpatterns = [
    path("", views.index, name="index"),

    # Tipos de Necessidade
    path("tipos/", views.tipo_list, name="tipo_list"),
    path("tipos/novo/", views.tipo_create, name="tipo_create"),
    path("tipos/<int:pk>/", views.tipo_detail, name="tipo_detail"),
    path("tipos/<int:pk>/editar/", views.tipo_update, name="tipo_update"),
    # Relatórios
    path("relatorios/", views.relatorios_index, name="relatorios_index"),
    path("relatorios/por-tipo/", views.relatorio_por_tipo, name="relatorio_por_tipo"),
]