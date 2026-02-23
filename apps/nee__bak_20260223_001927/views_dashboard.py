from django.contrib.auth.decorators import login_required
from django.urls import reverse, NoReverseMatch
from django.shortcuts import render


def _safe_reverse(name: str, *args, **kwargs) -> str:
    try:
        return reverse(name, args=args or None, kwargs=kwargs or None)
    except NoReverseMatch:
        return "#"


@login_required
def index(request):
    cards = [
        {
            "title": "Buscar aluno",
            "description": "Selecione um aluno para acessar necessidades, laudos, recursos e timeline.",
            "icon": "fa-solid fa-magnifying-glass",
            "url": _safe_reverse("nee:buscar_aluno"),
        },
        {
            "title": "Tipos de Necessidade",
            "description": "Cadastre e mantenha os tipos (TEA, TDAH, DI, etc.).",
            "icon": "fa-solid fa-tags",
            "url": _safe_reverse("nee:tipo_list"),
        },
        {
            "title": "Relatórios",
            "description": "Relatórios por tipo, município e unidade (com exportação).",
            "icon": "fa-solid fa-chart-column",
            "url": _safe_reverse("nee:relatorios_index"),
        },
        {
            "title": "Alertas",
            "description": "Pendências e acompanhamentos para ação rápida (drilldown).",
            "icon": "fa-solid fa-triangle-exclamation",
            "url": _safe_reverse("nee:alertas_index"),
        },
    ]

    context = {
        "actions": [],
        "cards": cards,
    }
    return render(request, "nee/index.html", context)


# Compat: alguns imports antigos esperam index_simple
index_simple = index
