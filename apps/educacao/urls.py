from django.urls import path
from . import views

app_name = "educacao"

urlpatterns = [
    path("", views.index, name="index"),

    path("turmas/", views.turma_list, name="turma_list"),
    path("turmas/novo/", views.turma_create, name="turma_create"),
    path("turmas/<int:pk>/", views.turma_detail, name="turma_detail"),
    path("turmas/<int:pk>/editar/", views.turma_update, name="turma_update"),
]
