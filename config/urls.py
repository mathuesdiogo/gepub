from django.contrib import admin
from django.urls import path, include
from apps.core import views as core_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("portal/", core_views.portal, name="portal"),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("org/", include(("apps.org.urls", "org"), namespace="org")),
    path("educacao/", include(("apps.educacao.urls", "educacao"), namespace="educacao")),
    path("nee/", include(("apps.nee.urls", "nee"), namespace="nee")),
    path("saude/", include(("apps.saude.urls", "saude"), namespace="saude")),

    # raiz
    path("", include(("apps.core.urls", "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)