from django.urls import path
from . import views
from . import views_unidades

app_name = "saude"

urlpatterns = [
    path("", views.index, name="index"),

    path("unidades/", views_unidades.unidade_list, name="unidade_list"),
    path("unidades/nova/", views_unidades.unidade_create, name="unidade_create"),
    path("unidades/<int:pk>/", views_unidades.unidade_detail, name="unidade_detail"),
    path("unidades/<int:pk>/editar/", views_unidades.unidade_update, name="unidade_update"),
]
