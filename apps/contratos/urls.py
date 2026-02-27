from django.urls import path

from . import views

app_name = "contratos"

urlpatterns = [
    path("", views.index, name="index"),
    path("lista/", views.contrato_list, name="list"),
    path("novo/", views.contrato_create, name="create"),
    path("<int:pk>/", views.contrato_detail, name="detail"),
    path("<int:contrato_pk>/aditivos/novo/", views.aditivo_create, name="aditivo_create"),
    path("<int:contrato_pk>/medicoes/novo/", views.medicao_create, name="medicao_create"),
    path("medicoes/<int:medicao_pk>/atestar/", views.medicao_atestar, name="medicao_atestar"),
    path("medicoes/<int:medicao_pk>/liquidar/", views.medicao_liquidar, name="medicao_liquidar"),
]
