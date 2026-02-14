from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("org/", include(("apps.org.urls", "org"), namespace="org")),
    path("educacao/", include(("apps.educacao.urls", "educacao"), namespace="educacao")),
    path("nee/", include(("apps.nee.urls", "nee"), namespace="nee")),

    # raiz
    path("", include(("apps.core.urls", "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
