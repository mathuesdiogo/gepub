from django.urls import path

from . import views

app_name = "paineis"

urlpatterns = [
    path("", views.index, name="index"),
    path("datasets/", views.dataset_list, name="dataset_list"),
    path("datasets/novo/", views.dataset_create, name="dataset_create"),
    path("datasets/<int:pk>/", views.dataset_detail, name="dataset_detail"),
    path("datasets/<int:pk>/publicar/", views.dataset_publish, name="dataset_publish"),
    path("datasets/<int:pk>/pacote/", views.dataset_package, name="dataset_package"),
    path("datasets/<int:dataset_pk>/dashboard/", views.dashboard, name="dashboard"),
]
