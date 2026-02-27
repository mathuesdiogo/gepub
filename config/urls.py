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
    path("avaliacoes/", include(("apps.avaliacoes.urls", "avaliacoes"), namespace="avaliacoes")),
    path("nee/", include(("apps.nee.urls", "nee"), namespace="nee")),
    path("saude/", include(("apps.saude.urls", "saude"), namespace="saude")),
    path("billing/", include(("apps.billing.urls", "billing"), namespace="billing")),
    path("financeiro/", include(("apps.financeiro.urls", "financeiro"), namespace="financeiro")),
    path("processos/", include(("apps.processos.urls", "processos"), namespace="processos")),
    path("compras/", include(("apps.compras.urls", "compras"), namespace="compras")),
    path("contratos/", include(("apps.contratos.urls", "contratos"), namespace="contratos")),
    path("integracoes/", include(("apps.integracoes.urls", "integracoes"), namespace="integracoes")),
    path("paineis/", include(("apps.paineis.urls", "paineis"), namespace="paineis")),
    path("conversor/", include(("apps.conversor.urls", "conversor"), namespace="conversor")),
    path("rh/", include(("apps.rh.urls", "rh"), namespace="rh")),
    path("ponto/", include(("apps.ponto.urls", "ponto"), namespace="ponto")),
    path("folha/", include(("apps.folha.urls", "folha"), namespace="folha")),
    path("patrimonio/", include(("apps.patrimonio.urls", "patrimonio"), namespace="patrimonio")),
    path("almoxarifado/", include(("apps.almoxarifado.urls", "almoxarifado"), namespace="almoxarifado")),
    path("frota/", include(("apps.frota.urls", "frota"), namespace="frota")),
    path("ouvidoria/", include(("apps.ouvidoria.urls", "ouvidoria"), namespace="ouvidoria")),
    path("tributos/", include(("apps.tributos.urls", "tributos"), namespace="tributos")),

    # raiz
    path("", include(("apps.core.urls", "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
