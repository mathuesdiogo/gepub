from django.urls import path
from . import views
from . import views_users

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("alterar-senha/", views.alterar_senha_view, name="alterar_senha"),
    path("meu-perfil/", views.meu_perfil, name="meu_perfil"),

    # gestão de usuários (tela normal do sistema)
    path("usuarios/", views_users.usuarios_list, name="usuarios_list"),
    path("usuarios/novo/", views_users.usuario_create, name="usuario_create"),
    path("usuarios/<int:pk>/", views_users.usuario_detail, name="usuario_detail"),
    path("usuarios/<int:pk>/editar/", views_users.usuario_update, name="usuario_update"),
    path("usuarios/<int:pk>/toggle-ativo/", views_users.usuario_toggle_ativo, name="usuario_toggle_ativo"),
    path("usuarios/<int:pk>/toggle-bloqueio/", views_users.usuario_toggle_bloqueio, name="usuario_toggle_bloqueio"),
    path("usuarios/<int:pk>/reset-codigo/", views_users.usuario_reset_codigo, name="usuario_reset_codigo"),
    path("usuarios/<int:pk>/reset-senha/", views_users.usuario_reset_senha, name="usuario_reset_senha"),
    path("api/users-suggest/", views_users.users_autocomplete, name="users_autocomplete"),


]
