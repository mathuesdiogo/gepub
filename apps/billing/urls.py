from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.index, name="index"),
    path("meu-plano/", views.meu_plano, name="meu_plano"),
    path("upgrade/solicitar/", views.solicitar_upgrade, name="solicitar_upgrade"),
    path("simulador/", views.simulador, name="simulador"),
    path("admin/assinaturas/", views.assinaturas_admin, name="assinaturas_admin"),
    path("admin/assinaturas/<int:assinatura_id>/", views.assinatura_admin_detail, name="assinatura_admin_detail"),
    path("faturas/<int:fatura_id>/pdf/", views.fatura_pdf, name="fatura_pdf"),
]
