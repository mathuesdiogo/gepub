from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_view, name="home"),
    path("dashboard/", views.dashboard_view, name="dashboard"),

    path("aluno/", views.dashboard_view, name="dashboard_aluno"),

    path("avisos/novo/", views.aviso_create, name="aviso_create"),
    path("arquivos/novo/", views.arquivo_create, name="arquivo_create"),

    # ✅ atalhos por código (novo)
    path("go/", views.go_code, name="go_code"),
    path("go/<str:codigo>/", views.go_code, name="go_code_path"),
    path("guia/", views.guia_telas, name="guia_telas"),


    # path("validar/<uuid:codigo>/", views.validar_documento, name="validar_documento"),
]
