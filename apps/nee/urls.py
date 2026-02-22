from __future__ import annotations

from django.urls import path

from .views_dashboard import index
from .views_busca import buscar_aluno
from .views_alertas import alertas_index
from .views_relatorios import (
    relatorios_index,
    relatorios_por_tipo,
    relatorios_por_municipio,
    relatorios_por_unidade,
    relatorios_alunos,
)

# Tipos (CBVs)
from .views_tipos import TipoListView, TipoCreateView, TipoUpdateView
try:
    from .views_tipos import TipoDetailView
except Exception:  # pragma: no cover
    TipoDetailView = TipoUpdateView  # fallback compat

app_name = "nee"

urlpatterns = [
    path("", index, name="index"),

    # Tipos de Necessidade
    path("tipos/", TipoListView.as_view(), name="tipo_list"),
    path("tipos/novo/", TipoCreateView.as_view(), name="tipo_create"),
    path("tipos/<int:pk>/", TipoDetailView.as_view(), name="tipo_detail"),
    path("tipos/<int:pk>/editar/", TipoUpdateView.as_view(), name="tipo_update"),

    # Relatórios
    path("relatorios/", relatorios_index, name="relatorios_index"),
    path("relatorios/por-tipo/", relatorios_por_tipo, name="relatorios_por_tipo"),
    path("relatorios/por-municipio/", relatorios_por_municipio, name="relatorios_por_municipio"),
    path("relatorios/por-unidade/", relatorios_por_unidade, name="relatorios_por_unidade"),
    path("relatorios/alunos/", relatorios_alunos, name="relatorios_alunos"),

    # Busca / Alertas
    path("buscar/", buscar_aluno, name="buscar_aluno"),
    path("alertas/", alertas_index, name="alertas_index"),
]
