from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("alterar-senha/", views.alterar_senha_view, name="alterar_senha"),
    path("logout/", views.logout_view, name="logout"),
]
