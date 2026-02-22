"""Compat layer (Enterprise)

Este módulo existe para manter estabilidade de imports: urls.py e templates
podem referenciar `apps.nee.views.*` mesmo quando o código estiver dividido
em subarquivos (views_dashboard.py, views_tipos.py, views_relatorios.py, ...).
"""
from __future__ import annotations

# Dashboard
try:
    from .views_dashboard import index  # type: ignore
except Exception:  # pragma: no cover
    index = None  # type: ignore

# Alguns patches antigos importam index_simple
index_simple = index  # type: ignore

# Tipos (CBVs)
try:
    from .views_tipos import TipoListView, TipoCreateView, TipoUpdateView  # type: ignore
    # Detail pode não existir; se não existir, usamos Update como detail
    try:
        from .views_tipos import TipoDetailView  # type: ignore
    except Exception:  # pragma: no cover
        TipoDetailView = TipoUpdateView  # type: ignore
except Exception:  # pragma: no cover
    TipoListView = TipoCreateView = TipoUpdateView = TipoDetailView = None  # type: ignore

# Relatórios (FBVs)
try:
    from .views_relatorios import (
        relatorios_index,
        relatorio_por_tipo,
        relatorio_por_municipio,
        relatorio_por_unidade,
    )  # type: ignore
except Exception:  # pragma: no cover
    relatorios_index = relatorio_por_tipo = relatorio_por_municipio = relatorio_por_unidade = None  # type: ignore

# Aliases (plural) para compat com urls/templates antigos
relatorios_por_tipo = relatorio_por_tipo  # type: ignore
relatorios_por_municipio = relatorio_por_municipio  # type: ignore
relatorios_por_unidade = relatorio_por_unidade  # type: ignore


# Busca / Alertas
try:
    from .views_busca import buscar_aluno  # type: ignore
except Exception:  # pragma: no cover
    buscar_aluno = None  # type: ignore

try:
    from .views_alertas import alertas_index  # type: ignore
except Exception:  # pragma: no cover
    alertas_index = None  # type: ignore

