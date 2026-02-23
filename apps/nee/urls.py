from __future__ import annotations

from django.urls import path

from .views_dashboard import index
from .views_busca import buscar_aluno, buscar_aluno_autocomplete
from .views_alertas import alertas_index, alertas_lista

from .views_relatorios import (
    relatorios_index,
    relatorios_por_tipo,
    relatorios_por_municipio,
    relatorios_por_unidade,
    relatorios_alunos,
)

from .views_relatorio_clinico import aluno_relatorio_clinico_pdf

from .views_plano import (
    aluno_hub,
    aluno_plano_clinico,
    ObjetivoListView,
    ObjetivoCreateView,
    ObjetivoUpdateView,
    ObjetivoDetailView,
    EvolucaoCreateView,
)

from .views_timeline import timeline_unificada

from .views_tipos import (
    TipoListView,
    TipoCreateView,
    TipoUpdateView,
)
try:
    from .views_tipos import TipoDetailView
except Exception:
    TipoDetailView = TipoUpdateView

from .views_necessidades import (
    AlunoNecessidadeListView,
    AlunoNecessidadeCreateView,
    AlunoNecessidadeUpdateView,
    AlunoNecessidadeDetailView,
)

from .views_laudos import (
    LaudoListView,
    LaudoCreateView,
    LaudoUpdateView,
    LaudoDetailView,
)

from .views_recursos import (
    RecursoListView,
    RecursoCreateView,
    RecursoUpdateView,
    RecursoDetailView,
)

from .views_apoios import (
    ApoioListView,
    ApoioCreateView,
    ApoioUpdateView,
    ApoioDetailView,
)

from .views_acompanhamentos import (
    AcompanhamentoListView,
    AcompanhamentoCreateView,
    AcompanhamentoUpdateView,
    AcompanhamentoDetailView,
)

app_name = "nee"

urlpatterns = [
    # DASH do NEE
    path("", index, name="index"),

    # BUSCA / ALERTAS
    path("buscar/", buscar_aluno, name="buscar_aluno"),
    path("buscar/autocomplete/", buscar_aluno_autocomplete, name="buscar_aluno_autocomplete"),
    path("alertas/", alertas_index, name="alertas_index"),
    path("alertas/<slug:kind>/", alertas_lista, name="alertas_lista"),
    path("aluno-search/", buscar_aluno, name="aluno_search"),

    # RELATÓRIOS
    path("relatorios/", relatorios_index, name="relatorios_index"),
    path("relatorios/por-tipo/", relatorios_por_tipo, name="relatorios_por_tipo"),
    path("relatorios/por-municipio/", relatorios_por_municipio, name="relatorios_por_municipio"),
    path("relatorios/por-unidade/", relatorios_por_unidade, name="relatorios_por_unidade"),
    path("relatorios/alunos/", relatorios_alunos, name="relatorios_alunos"),

    # TIPOS
    path("tipos/", TipoListView.as_view(), name="tipo_list"),
    path("tipos/novo/", TipoCreateView.as_view(), name="tipo_create"),
    path("tipos/<int:pk>/", TipoDetailView.as_view(), name="tipo_detail"),
    path("tipos/<int:pk>/editar/", TipoUpdateView.as_view(), name="tipo_update"),

    # ============================================================
    # HUB DO ALUNO + PDF CLÍNICO
    # ============================================================
    path("aluno/<int:aluno_id>/", aluno_hub, name="aluno_hub"),
    path("aluno/<int:aluno_id>/relatorio/", aluno_relatorio_clinico_pdf, name="aluno_relatorio_clinico_pdf"),

    # ============================================================
    # PLANO CLÍNICO (PEI)
    # ============================================================
    path("aluno/<int:aluno_id>/plano/", aluno_plano_clinico, name="aluno_plano_clinico"),

    # OBJETIVOS (do plano)
    path("aluno/<int:aluno_id>/objetivos/", ObjetivoListView.as_view(), name="aluno_objetivos"),
    path("objetivo/novo/<int:aluno_id>/", ObjetivoCreateView.as_view(), name="objetivo_create"),
    path("objetivo/<int:pk>/", ObjetivoDetailView.as_view(), name="objetivo_detail"),
    path("objetivo/<int:pk>/editar/", ObjetivoUpdateView.as_view(), name="objetivo_update"),

    # EVOLUÇÕES (por objetivo)
    path("evolucao/novo/<int:objetivo_id>/", EvolucaoCreateView.as_view(), name="evolucao_create"),

    # ============================================================
    # LISTAS (por aluno)
    # ============================================================
    path("aluno/<int:aluno_id>/necessidades/", AlunoNecessidadeListView.as_view(), name="aluno_necessidades"),
    path("aluno/<int:aluno_id>/laudos/", LaudoListView.as_view(), name="aluno_laudos"),
    path("aluno/<int:aluno_id>/recursos/", RecursoListView.as_view(), name="aluno_recursos"),
    path("aluno/<int:aluno_id>/apoios/", ApoioListView.as_view(), name="aluno_apoios"),
    path("aluno/<int:aluno_id>/acompanhamentos/", AcompanhamentoListView.as_view(), name="aluno_acompanhamentos"),
    path("aluno/<int:aluno_id>/timeline/", timeline_unificada, name="aluno_timeline"),

    # ============================================================
    # CRUD NECESSIDADES
    # ============================================================
    path("necessidade/novo/<int:aluno_id>/", AlunoNecessidadeCreateView.as_view(), name="necessidade_create"),
    path("necessidade/<int:pk>/", AlunoNecessidadeDetailView.as_view(), name="necessidade_detail"),
    path("necessidade/<int:pk>/editar/", AlunoNecessidadeUpdateView.as_view(), name="necessidade_update"),

    # ============================================================
    # CRUD LAUDOS
    # ============================================================
    path("laudo/novo/<int:aluno_id>/", LaudoCreateView.as_view(), name="laudo_create"),
    path("laudo/<int:pk>/", LaudoDetailView.as_view(), name="laudo_detail"),
    path("laudo/<int:pk>/editar/", LaudoUpdateView.as_view(), name="laudo_update"),

    # ============================================================
    # CRUD RECURSOS
    # ============================================================
    path("recurso/novo/<int:aluno_id>/", RecursoCreateView.as_view(), name="recurso_create"),
    path("recurso/<int:pk>/", RecursoDetailView.as_view(), name="recurso_detail"),
    path("recurso/<int:pk>/editar/", RecursoUpdateView.as_view(), name="recurso_update"),

    # ============================================================
    # CRUD ACOMPANHAMENTOS
    # ============================================================
    path("acompanhamento/novo/<int:aluno_id>/", AcompanhamentoCreateView.as_view(), name="acompanhamento_create"),
    path("acompanhamento/<int:pk>/", AcompanhamentoDetailView.as_view(), name="acompanhamento_detail"),
    path("acompanhamento/<int:pk>/editar/", AcompanhamentoUpdateView.as_view(), name="acompanhamento_update"),

    # ============================================================
    # CRUD APOIOS
    # ============================================================
    path("apoio/novo/<int:aluno_id>/", ApoioCreateView.as_view(), name="apoio_create"),
    path("apoio/<int:pk>/", ApoioDetailView.as_view(), name="apoio_detail"),
    path("apoio/<int:pk>/editar/", ApoioUpdateView.as_view(), name="apoio_update"),
]