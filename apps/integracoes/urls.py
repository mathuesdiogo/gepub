from django.urls import path

from . import views

app_name = "integracoes"

urlpatterns = [
    path("", views.index, name="index"),
    path("conectores/novo/", views.conector_create, name="conector_create"),
    path("execucoes/nova/", views.execucao_create, name="execucao_create"),
]
