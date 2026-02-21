from django.urls import path

from . import views
from . import views_municipios, views_secretarias, views_unidades, views_setores

app_name = "org"

urlpatterns = [
    path("", views.index, name="index"),

    # Municípios
    path("municipios/", views_municipios.MunicipioListView.as_view(), name="municipio_list"),
    path("municipios/novo/", views_municipios.MunicipioCreateView.as_view(), name="municipio_create"),
    path("municipios/<int:pk>/", views_municipios.MunicipioDetailView.as_view(), name="municipio_detail"),
    path("municipios/<int:pk>/editar/", views_municipios.MunicipioUpdateView.as_view(), name="municipio_update"),

    # Secretarias
    path("secretarias/", views_secretarias.SecretariaListView.as_view(), name="secretaria_list"),
    path("secretarias/novo/", views_secretarias.SecretariaCreateView.as_view(), name="secretaria_create"),
    path("secretarias/<int:pk>/", views_secretarias.SecretariaDetailView.as_view(), name="secretaria_detail"),
    path("secretarias/<int:pk>/editar/", views_secretarias.SecretariaUpdateView.as_view(), name="secretaria_update"),

    # Unidades
    path("unidades/", views_unidades.UnidadeListView.as_view(), name="unidade_list"),
    path("unidades/novo/", views_unidades.UnidadeCreateView.as_view(), name="unidade_create"),
    path("unidades/<int:pk>/", views_unidades.UnidadeDetailView.as_view(), name="unidade_detail"),
    path("unidades/<int:pk>/editar/", views_unidades.UnidadeUpdateView.as_view(), name="unidade_update"),

    # Setores
    path("setores/", views_setores.SetorListView.as_view(), name="setor_list"),
    path("setores/novo/", views_setores.SetorCreateView.as_view(), name="setor_create"),
    path("setores/<int:pk>/", views_setores.SetorDetailView.as_view(), name="setor_detail"),
    path("setores/<int:pk>/editar/", views_setores.SetorUpdateView.as_view(), name="setor_update"),

    # Autocomplete endpoints
    path("autocomplete/secretarias/", views_secretarias.secretaria_autocomplete, name="secretaria_autocomplete"),
    path("autocomplete/unidades/", views_unidades.unidade_autocomplete, name="unidade_autocomplete"),
    path("autocomplete/municipios/", views_municipios.municipio_autocomplete, name="municipio_autocomplete"),
    path("api/setores-suggest/", views_setores.setor_autocomplete, name="setor_autocomplete"),
]
