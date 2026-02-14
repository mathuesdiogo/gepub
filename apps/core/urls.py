from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),  # ✅ raiz /
    path("aluno/", views.dashboard_aluno, name="dashboard_aluno"),
    path("avisos/novo/", views.aviso_create, name="aviso_create"),
    path("arquivos/novo/", views.arquivo_create, name="arquivo_create"),
    path("tema/<str:theme>/", views.change_theme, name="change_theme"),
    path("validar/<uuid:codigo>/", views.validar_documento, name="validar_documento"),
]
