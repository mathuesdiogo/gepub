from django.urls import path
from . import views

app_name = "org"

urlpatterns = [
    path("", views.index, name="index"),

    # Municípios
    path("municipios/", views.municipio_list, name="municipio_list"),
    path("municipios/novo/", views.municipio_create, name="municipio_create"),
    path("municipios/<int:pk>/", views.municipio_detail, name="municipio_detail"),
    path("municipios/<int:pk>/editar/", views.municipio_update, name="municipio_update"),
    
    # Secretarias
    path("secretarias/", views.secretaria_list, name="secretaria_list"),
    path("secretarias/novo/", views.secretaria_create, name="secretaria_create"),
    path("secretarias/<int:pk>/", views.secretaria_detail, name="secretaria_detail"),
    path("secretarias/<int:pk>/editar/", views.secretaria_update, name="secretaria_update"),

]
