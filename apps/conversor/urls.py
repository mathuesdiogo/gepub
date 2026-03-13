from django.urls import path

from . import views

app_name = "conversor"

urlpatterns = [
    path("", views.index, name="index"),
    path("jobs/<int:pk>/download/", views.download, name="download"),
    path("jobs/<int:pk>/status/", views.job_status, name="job_status"),
]
