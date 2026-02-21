from django.urls import path
from . import views

app_name = "pessoas"

urlpatterns = [
    path("", views.index, name="index"),
]
