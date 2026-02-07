from django.urls import path
from . import views

app_name = "org"

urlpatterns = [
    # Index do módulo
    path("", views.index, name="index"),

    # --------------------
    # Municípios
    # --------------------
    path("municipios/", views.municipio_list, name="municipio_list"),
    path("municipios/novo/", views.municipio_create, name="municipio_create"),
    path("municipios/<int:pk>/", views.municipio_detail, name="municipio_detail"),
    path("municipios/<int:pk>/editar/", views.municipio_update, name="municipio_update"),

    # --------------------
    # Secretarias
    # --------------------
    path("secretarias/", views.secretaria_list, name="secretaria_list"),
    path("secretarias/novo/", views.secretaria_create, name="secretaria_create"),
    path("secretarias/<int:pk>/", views.secretaria_detail, name="secretaria_detail"),
    path("secretarias/<int:pk>/editar/", views.secretaria_update, name="secretaria_update"),

    # --------------------
    # Unidades
    # --------------------
    path("unidades/", views.unidade_list, name="unidade_list"),
    path("unidades/novo/", views.unidade_create, name="unidade_create"),
    path("unidades/<int:pk>/", views.unidade_detail, name="unidade_detail"),
    path("unidades/<int:pk>/editar/", views.unidade_update, name="unidade_update"),
    
    # Setores
    path("setores/", views.setor_list, name="setor_list"),
    path("setores/novo/", views.setor_create, name="setor_create"),
    path("setores/<int:pk>/", views.setor_detail, name="setor_detail"),
    path("setores/<int:pk>/editar/", views.setor_update, name="setor_update"),

]
