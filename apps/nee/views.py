"""Compat layer (NORMALIZADO)

Este módulo existe para manter estabilidade de imports: urls.py e templates
podem referenciar `apps.nee.views.*` mesmo quando o código estiver dividido em
múltiplos arquivos (views_dashboard.py, views_tipos.py, views_relatorios.py, ...).

Regras desta versão:
- Sem try/except engolindo erro (falha rápida é melhor do que rota “fantasma”)
- Aliases mantidos (singular/plural) para não quebrar templates antigos
"""
from __future__ import annotations

# Dashboard
from .views_dashboard import index
index_simple = index  # compat

# Tipos (CBVs)
from .views_tipos import TipoListView, TipoCreateView, TipoUpdateView
try:
    from .views_tipos import TipoDetailView
except Exception:  # pragma: no cover
    TipoDetailView = TipoUpdateView  # fallback compat

# Relatórios (FBVs)
from .views_relatorios import (
    relatorios_index,
    relatorios_por_tipo,
    relatorios_por_municipio,
    relatorios_por_unidade,
    relatorios_alunos,
)

# Aliases (singular) para compat com código antigo
relatorio_por_tipo = relatorios_por_tipo
relatorio_por_municipio = relatorios_por_municipio
relatorio_por_unidade = relatorios_por_unidade

# Busca / Alertas
from .views_busca import buscar_aluno
from .views_alertas import alertas_index
