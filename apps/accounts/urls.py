from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("alterar-senha/", views.alterar_senha_view, name="alterar_senha"),
    path("meu-perfil/", views.meu_perfil, name="meu_perfil"),

    # gestão de usuários (tela normal do sistema)
    path("usuarios/", views.usuarios_list, name="usuarios_list"),
    path("usuarios/novo/", views.usuario_create, name="usuario_create"),
    path("usuarios/<int:pk>/editar/", views.usuario_update, name="usuario_update"),
    path("usuarios/<int:pk>/reset-senha/", views.usuario_reset_senha, name="usuario_reset_senha"),
]
