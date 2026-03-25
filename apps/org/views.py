from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_municipios

# Reexports das views padronizadas
from .views_municipios import MunicipioListView, MunicipioCreateView, MunicipioUpdateView, MunicipioDetailView
from .views_secretarias import SecretariaListView, SecretariaCreateView, SecretariaUpdateView, SecretariaDetailView
from .views_unidades import UnidadeListView, UnidadeCreateView, UnidadeUpdateView, UnidadeDetailView
from .views_setores import SetorListView, SetorCreateView, SetorUpdateView, SetorDetailView
from .views_locais import (
    LocalEstruturalListView,
    LocalEstruturalCreateView,
    LocalEstruturalUpdateView,
    LocalEstruturalDetailView,
)
from .models import (
    Municipio,
    Secretaria,
    Unidade,
    Setor,
    LocalEstrutural,
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
    locais_qs = LocalEstrutural.objects.filter(municipio_id__in=municipio_ids)
    steps_qs = OnboardingStep.objects.filter(municipio_id__in=municipio_ids)
    modulos_ativos_qs = MunicipioModuloAtivo.objects.filter(municipio_id__in=municipio_ids, ativo=True)
    provisionamentos_qs = SecretariaProvisionamento.objects.filter(municipio_id__in=municipio_ids)

    steps_total = steps_qs.count()
    steps_concluidos = steps_qs.filter(status=OnboardingStep.Status.CONCLUIDO).count()
    steps_pendentes = max(steps_total - steps_concluidos, 0)
    progress_pct = int((steps_concluidos / steps_total) * 100) if steps_total else 0

    actions = [
        {
            "label": "Assistente guiado",
            "url": "/org/onboarding/",
            "icon": "fa-solid fa-wand-magic-sparkles",
            "variant": "gp-button--primary",
        }
    ]

    return render(request, "org/index.html", {
        "stats": {
            "municipios": municipios_qs.count(),
            "secretarias": secretarias_qs.count(),
            "unidades": unidades_qs.count(),
            "setores": setores_qs.count(),
            "locais": locais_qs.count(),
            "modulos_ativos": modulos_ativos_qs.count(),
            "onboarding_total": steps_total,
            "onboarding_concluidos": steps_concluidos,
            "onboarding_pendentes": steps_pendentes,
            "onboarding_progress_pct": progress_pct,
            "provisionamentos_total": provisionamentos_qs.count(),
        },
        "recent_provisionamentos": list(
            provisionamentos_qs.select_related("template", "secretaria").order_by("-criado_em")[:5]
        ),
        "actions": actions,
        "can_manage_secretaria": can(request.user, "org.manage_secretaria"),
    })
