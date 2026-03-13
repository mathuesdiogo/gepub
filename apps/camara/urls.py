from django.urls import path

from . import views

app_name = "camara"

urlpatterns = [
    path("", views.index, name="index"),
    path("<str:module_key>/", views.module_list, name="module_list"),
    path("<str:module_key>/novo/", views.module_create, name="module_create"),
    path("<str:module_key>/<int:pk>/editar/", views.module_update, name="module_update"),
    path("<str:module_key>/<int:pk>/remover/", views.module_delete, name="module_delete"),
]
