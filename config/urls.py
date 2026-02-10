from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("org/", include("org.urls", namespace="org")),
    path("educacao/", include("educacao.urls", namespace="educacao")),
    path("nee/", include("nee.urls", namespace="nee")),

    # ✅ raiz do sistema (dashboard /)
    path("", include("core.urls", namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
