from django.urls import path

from . import views

app_name = "tributos"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("contribuintes/", views.contribuinte_list, name="contribuinte_list"),
    path("contribuintes/novo/", views.contribuinte_create, name="contribuinte_create"),
    path("contribuintes/<int:pk>/editar/", views.contribuinte_update, name="contribuinte_update"),
    path("lancamentos/", views.lancamento_list, name="lancamento_list"),
    path("lancamentos/novo/", views.lancamento_create, name="lancamento_create"),
    path("lancamentos/<int:pk>/baixar/", views.lancamento_baixar, name="lancamento_baixar"),
]
