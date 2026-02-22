from __future__ import annotations

from django.urls import path
from . import views

app_name = "nee"

def _as_view(obj):
    """Aceita FBV ou CBV e devolve callable para urlpattern."""
    if obj is None:
        return None
    if hasattr(obj, "as_view"):
        return obj.as_view()
    return obj

def _pick(module, *names):
    for n in names:
        if hasattr(module, n):
            return getattr(module, n)
    return None

# módulos opcionais (compat entre patches)
try:
    from . import views_relatorios as rel_views  # type: ignore
except Exception:  # pragma: no cover
    rel_views = None

try:
    from . import views_tipos as tipos_views  # type: ignore
except Exception:  # pragma: no cover
    tipos_views = None

def pick_rel(*names):
    if rel_views:
        obj = _pick(rel_views, *names)
        if obj is not None:
            return obj
    return _pick(views, *names)

def pick_tipos(*names):
    if tipos_views:
        obj = _pick(tipos_views, *names)
        if obj is not None:
            return obj
    return _pick(views, *names)

urlpatterns = [
    path("", _as_view(_pick(views, "index", "dashboard", "index_simple")), name="index"),

    # Tipos de Necessidade
    path("tipos/", _as_view(pick_tipos("TipoListView", "tipo_list")), name="tipo_list"),
    path("tipos/novo/", _as_view(pick_tipos("TipoCreateView", "tipo_create")), name="tipo_create"),
    path("tipos/<int:pk>/", _as_view(pick_tipos("TipoDetailView", "tipo_detail", "TipoUpdateView", "tipo_update")), name="tipo_detail"),
    path("tipos/<int:pk>/editar/", _as_view(pick_tipos("TipoUpdateView", "tipo_update")), name="tipo_update"),

    # Relatórios
    path("relatorios/", _as_view(pick_rel("relatorios_index", "index")), name="relatorios_index"),
    path("relatorios/por-tipo/", _as_view(pick_rel("relatorio_por_tipo", "relatorios_por_tipo")), name="relatorios_por_tipo"),
    path("relatorios/por-municipio/", _as_view(pick_rel("relatorio_por_municipio", "relatorios_por_municipio")), name="relatorios_por_municipio"),
    path("relatorios/por-unidade/", _as_view(pick_rel("relatorio_por_unidade", "relatorios_por_unidade")), name="relatorios_por_unidade"),

    # Busca / Alertas
    path("buscar/", _as_view(_pick(views, "buscar_aluno")), name="buscar_aluno"),
    path("alertas/", _as_view(_pick(views, "alertas_index")), name="alertas_index"),
]
