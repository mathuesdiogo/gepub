from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_view, name="home"),
    path("dashboard/", views.dashboard_view, name="dashboard"),

    path("aluno/", views.dashboard_view, name="dashboard_aluno"),

    path("avisos/novo/", views.aviso_create, name="aviso_create"),
    path("arquivos/novo/", views.arquivo_create, name="arquivo_create"),

    # path("validar/<uuid:codigo>/", views.validar_documento, name="validar_documento"),
]
