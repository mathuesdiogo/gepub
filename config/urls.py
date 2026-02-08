from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),

    path("pessoas/", include("pessoas.urls", namespace="pessoas")),
    path("org/", include("org.urls", namespace="org")),
    path("educacao/", include("educacao.urls", namespace="educacao")),
    path("nee/", include("nee.urls", namespace="nee")),

    path("", include("core.urls", namespace="core")),
]
