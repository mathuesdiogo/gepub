from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.core.decorators import require_perm

# Reexports das views padronizadas
from .views_municipios import MunicipioListView, MunicipioCreateView, MunicipioUpdateView, MunicipioDetailView
from .views_secretarias import SecretariaListView, SecretariaCreateView, SecretariaUpdateView, SecretariaDetailView
from .views_unidades import UnidadeListView, UnidadeCreateView, UnidadeUpdateView, UnidadeDetailView
from .views_setores import SetorListView, SetorCreateView, SetorUpdateView, SetorDetailView


@login_required
@require_perm("org.view")
def index(request):
    """
    Landing do módulo ORG (mantém rota /org/ sem quebrar nada).
    Você pode depois trocar esse template por um dashboard/atalhos SUAP-like.
    """
    return render(request, "org/index.html", {
        "actions": [
            {"label": "Municípios", "url": "/org/municipios/", "icon": "fa-solid fa-city", "variant": "btn--ghost"},
            {"label": "Secretarias", "url": "/org/secretarias/", "icon": "fa-solid fa-building-columns", "variant": "btn--ghost"},
            {"label": "Unidades", "url": "/org/unidades/", "icon": "fa-solid fa-school", "variant": "btn--ghost"},
            {"label": "Setores", "url": "/org/setores/", "icon": "fa-solid fa-sitemap", "variant": "btn--ghost"},
        ]
    })