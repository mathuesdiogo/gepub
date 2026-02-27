from django.urls import path

from . import views

app_name = "ponto"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("escalas/", views.escala_list, name="escala_list"),
    path("escalas/nova/", views.escala_create, name="escala_create"),
    path("escalas/<int:pk>/editar/", views.escala_update, name="escala_update"),
    path("vinculos/", views.vinculo_list, name="vinculo_list"),
    path("vinculos/novo/", views.vinculo_create, name="vinculo_create"),
    path("vinculos/<int:pk>/toggle/", views.vinculo_toggle, name="vinculo_toggle"),
    path("ocorrencias/", views.ocorrencia_list, name="ocorrencia_list"),
    path("ocorrencias/nova/", views.ocorrencia_create, name="ocorrencia_create"),
    path("ocorrencias/<int:pk>/aprovar/", views.ocorrencia_aprovar, name="ocorrencia_aprovar"),
    path("ocorrencias/<int:pk>/recusar/", views.ocorrencia_recusar, name="ocorrencia_recusar"),
    path("competencias/", views.competencia_list, name="competencia_list"),
    path("competencias/nova/", views.competencia_create, name="competencia_create"),
    path("competencias/<int:pk>/fechar/", views.competencia_fechar, name="competencia_fechar"),
    path("competencias/<int:pk>/reabrir/", views.competencia_reabrir, name="competencia_reabrir"),
]
