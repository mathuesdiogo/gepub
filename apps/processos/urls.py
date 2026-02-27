from django.urls import path

from . import views

app_name = "processos"

urlpatterns = [
    path("", views.index, name="index"),
    path("lista/", views.processo_list, name="list"),
    path("novo/", views.processo_create, name="create"),
    path("<int:pk>/", views.processo_detail, name="detail"),
    path("<int:processo_pk>/andamentos/novo/", views.andamento_create, name="andamento_create"),
]
