from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_municipios

# Reexports das views padronizadas
from .views_municipios import MunicipioListView, MunicipioCreateView, MunicipioUpdateView, MunicipioDetailView
from .views_secretarias import SecretariaListView, SecretariaCreateView, SecretariaUpdateView, SecretariaDetailView
from .views_unidades import UnidadeListView, UnidadeCreateView, UnidadeUpdateView, UnidadeDetailView
from .views_setores import SetorListView, SetorCreateView, SetorUpdateView, SetorDetailView
from .models import (
    Municipio,
    Secretaria,
    Unidade,
    Setor,
    OnboardingStep,
    MunicipioModuloAtivo,
    SecretariaProvisionamento,
)


@login_required
@require_perm("org.view")
def index(request):
    """
    Landing do módulo ORG (mantém rota /org/ sem quebrar nada).
    Você pode depois trocar esse template por um dashboard/atalhos SUAP-like.
    """
    municipios_qs = scope_filter_municipios(request.user, Municipio.objects.all())
    municipio_ids = municipios_qs.values_list("id", flat=True)

    secretarias_qs = Secretaria.objects.filter(municipio_id__in=municipio_ids)
    unidades_qs = Unidade.objects.filter(secretaria__municipio_id__in=municipio_ids)
    setores_qs = Setor.objects.filter(unidade__secretaria__municipio_id__in=municipio_ids)
    steps_qs = OnboardingStep.objects.filter(municipio_id__in=municipio_ids)
    modulos_ativos_qs = MunicipioModuloAtivo.objects.filter(municipio_id__in=municipio_ids, ativo=True)
    provisionamentos_qs = SecretariaProvisionamento.objects.filter(municipio_id__in=municipio_ids)

    steps_total = steps_qs.count()
    steps_concluidos = steps_qs.filter(status=OnboardingStep.Status.CONCLUIDO).count()
    progress_pct = int((steps_concluidos / steps_total) * 100) if steps_total else 0

    actions = [
        {"label": "Onboarding Inicial", "url": "/org/onboarding/primeiro-acesso/", "icon": "fa-solid fa-wand-magic-sparkles", "variant": "btn-primary"},
        {"label": "Painel de Onboarding", "url": "/org/onboarding/painel/", "icon": "fa-solid fa-list-check", "variant": "btn--ghost"},
        {"label": "Municípios", "url": "/org/municipios/", "icon": "fa-solid fa-city", "variant": "btn--ghost"},
        {"label": "Secretarias", "url": "/org/secretarias/", "icon": "fa-solid fa-building-columns", "variant": "btn--ghost"},
        {"label": "Unidades", "url": "/org/unidades/", "icon": "fa-solid fa-school", "variant": "btn--ghost"},
        {"label": "Setores", "url": "/org/setores/", "icon": "fa-solid fa-sitemap", "variant": "btn--ghost"},
    ]
    if can(request.user, "org.manage_secretaria"):
        actions.insert(2, {"label": "Governança", "url": "/org/secretarias/governanca/", "icon": "fa-solid fa-sliders", "variant": "btn--ghost"})

    return render(request, "org/index.html", {
        "stats": {
            "municipios": municipios_qs.count(),
            "secretarias": secretarias_qs.count(),
            "unidades": unidades_qs.count(),
            "setores": setores_qs.count(),
            "modulos_ativos": modulos_ativos_qs.count(),
            "onboarding_total": steps_total,
            "onboarding_concluidos": steps_concluidos,
            "onboarding_progress_pct": progress_pct,
            "provisionamentos_total": provisionamentos_qs.count(),
        },
        "recent_provisionamentos": list(
            provisionamentos_qs.select_related("template", "secretaria").order_by("-criado_em")[:5]
        ),
        "actions": actions,
        "can_manage_secretaria": can(request.user, "org.manage_secretaria"),
    })
