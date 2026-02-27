from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, URLPattern, URLResolver, get_resolver, reverse

from apps.core.rbac import can, is_admin


NAMESPACE_CONFIG = {
    "core": {
        "start": 1,
        "end": 99,
        "setor": "Sistema",
        "perm": None,
        "priority": ["dashboard", "guia_telas", "institutional_admin"],
    },
    "org": {
        "start": 100,
        "end": 199,
        "setor": "Administrativo",
        "perm": "org.view",
        "priority": [
            "index",
            "onboarding_painel",
            "secretaria_governanca_hub",
            "municipio_list",
            "secretaria_list",
            "unidade_list",
            "setor_list",
            "municipio_create",
            "secretaria_create",
            "unidade_create",
            "setor_create",
        ],
    },
    "saude": {
        "start": 200,
        "end": 299,
        "setor": "Saude",
        "perm": "saude.view",
        "priority": [
            "index",
            "atendimento_list",
            "agenda_list",
            "paciente_list",
            "profissional_list",
            "unidade_list",
            "relatorio_mensal",
        ],
    },
    "educacao": {
        "start": 300,
        "end": 399,
        "setor": "Educacao",
        "perm": "educacao.view",
        "priority": [
            "index",
            "aluno_list",
            "turma_list",
            "matricula_create",
            "meus_diarios",
            "calendario_index",
            "relatorio_mensal",
            "indicadores_gerenciais",
        ],
    },
    "nee": {
        "start": 400,
        "end": 499,
        "setor": "Educacao",
        "perm": "nee.view",
        "priority": [
            "index",
            "relatorios_index",
            "tipo_list",
            "buscar_aluno",
            "alertas_index",
        ],
    },
    "financeiro": {
        "start": 500,
        "end": 599,
        "setor": "Administrativo",
        "perm": "financeiro.view",
        "priority": [
            "index",
            "exercicio_list",
            "ug_list",
            "conta_list",
            "dotacao_list",
            "empenho_list",
            "resto_list",
            "receita_list",
            "extrato_list",
            "log_list",
        ],
    },
    "processos": {
        "start": 600,
        "end": 699,
        "setor": "Administrativo",
        "perm": "processos.view",
        "priority": ["index", "list", "create"],
    },
    "compras": {
        "start": 700,
        "end": 799,
        "setor": "Administrativo",
        "perm": "compras.view",
        "priority": ["index", "requisicao_list", "requisicao_create", "licitacao_list", "licitacao_create"],
    },
    "contratos": {
        "start": 800,
        "end": 899,
        "setor": "Administrativo",
        "perm": "contratos.view",
        "priority": ["index", "list", "create"],
    },
    "rh": {
        "start": 900,
        "end": 999,
        "setor": "Administrativo",
        "perm": "rh.view",
        "priority": [
            "index",
            "servidor_list",
            "servidor_create",
            "movimentacao_list",
            "movimentacao_create",
            "documento_list",
            "documento_create",
        ],
    },
    "ponto": {
        "start": 1000,
        "end": 1099,
        "setor": "Administrativo",
        "perm": "ponto.view",
        "priority": [
            "index",
            "escala_list",
            "escala_create",
            "vinculo_list",
            "vinculo_create",
            "ocorrencia_list",
            "ocorrencia_create",
            "competencia_list",
            "competencia_create",
        ],
    },
    "folha": {
        "start": 1100,
        "end": 1199,
        "setor": "Administrativo",
        "perm": "folha.view",
        "priority": [
            "index",
            "rubrica_list",
            "rubrica_create",
            "competencia_list",
            "competencia_create",
            "lancamento_list",
            "lancamento_create",
        ],
    },
    "patrimonio": {
        "start": 1200,
        "end": 1299,
        "setor": "Administrativo",
        "perm": "patrimonio.view",
        "priority": [
            "index",
            "bem_list",
            "bem_create",
            "movimentacao_list",
            "movimentacao_create",
            "inventario_list",
            "inventario_create",
        ],
    },
    "almoxarifado": {
        "start": 1300,
        "end": 1399,
        "setor": "Administrativo",
        "perm": "almoxarifado.view",
        "priority": [
            "index",
            "item_list",
            "item_create",
            "movimento_list",
            "movimento_create",
            "requisicao_list",
            "requisicao_create",
        ],
    },
    "frota": {
        "start": 1400,
        "end": 1499,
        "setor": "Administrativo",
        "perm": "frota.view",
        "priority": [
            "index",
            "veiculo_list",
            "veiculo_create",
            "abastecimento_list",
            "abastecimento_create",
            "manutencao_list",
            "manutencao_create",
            "viagem_list",
            "viagem_create",
        ],
    },
    "ouvidoria": {
        "start": 1500,
        "end": 1599,
        "setor": "Administrativo",
        "perm": "ouvidoria.view",
        "priority": [
            "index",
            "chamado_list",
            "chamado_create",
            "tramitacao_list",
            "tramitacao_create",
            "resposta_list",
            "resposta_create",
        ],
    },
    "tributos": {
        "start": 1600,
        "end": 1699,
        "setor": "Administrativo",
        "perm": "tributos.view",
        "priority": [
            "index",
            "contribuinte_list",
            "contribuinte_create",
            "lancamento_list",
            "lancamento_create",
        ],
    },
    "integracoes": {
        "start": 1700,
        "end": 1799,
        "setor": "Administrativo",
        "perm": "integracoes.view",
        "priority": ["index", "conector_create", "execucao_create"],
    },
    "paineis": {
        "start": 1800,
        "end": 1849,
        "setor": "Administrativo",
        "perm": "paineis.view",
        "priority": ["index", "dataset_list", "dataset_create", "dashboard"],
    },
    "conversor": {
        "start": 1850,
        "end": 1889,
        "setor": "Administrativo",
        "perm": "conversor.view",
        "priority": ["index", "download"],
    },
    "avaliacoes": {
        "start": 1890,
        "end": 1899,
        "setor": "Educacao",
        "perm": "avaliacoes.view",
        "priority": [
            "avaliacao_list",
            "avaliacao_create",
            "avaliacao_detail",
            "resultados",
            "folha_corrigir",
        ],
    },
    "billing": {
        "start": 1900,
        "end": 1949,
        "setor": "Administrativo",
        "perm": "billing.view",
        "priority": ["index", "meu_plano", "simulador", "assinaturas_admin"],
    },
    "accounts": {
        "start": 1950,
        "end": 1999,
        "setor": "Acesso",
        "perm": "accounts.view",
        "priority": ["meu_perfil", "alterar_senha", "usuarios_list", "usuario_create"],
    },
}

DEFAULT_NAMESPACE_CONFIG = {
    "start": 9000,
    "end": 9999,
    "setor": "Outros",
    "perm": None,
    "priority": ["index", "list", "create"],
}

SKIP_SUFFIXES = ("_suggest", "_autocomplete", "_delete", "_toggle_ativo", "_toggle_bloqueio")
SKIP_PREFIXES = ("api_",)
SKIP_EXACT_NAMES = {
    "core:home",
    "core:institucional_public",
    "core:documentacao_public",
    "core:transparencia_public",
    "core:go_code",
    "core:go_code_path",
    "accounts:login",
    "accounts:logout",
}


def _iter_named_routes(patterns, namespaces=()):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            next_namespaces = namespaces
            if pattern.namespace:
                next_namespaces = (*namespaces, pattern.namespace)
            yield from _iter_named_routes(pattern.url_patterns, next_namespaces)
            continue

        if isinstance(pattern, URLPattern) and pattern.name:
            if namespaces:
                yield ":".join([*namespaces, pattern.name])
            else:
                yield pattern.name


def _split_url_name(url_name: str) -> tuple[str, str]:
    if ":" not in url_name:
        return "", url_name
    ns, route_name = url_name.split(":", 1)
    return ns, route_name


def _namespace_config(namespace: str) -> dict:
    return NAMESPACE_CONFIG.get(namespace, DEFAULT_NAMESPACE_CONFIG)


def _is_navigable_route(url_name: str) -> bool:
    if url_name in SKIP_EXACT_NAMES:
        return False

    namespace, route_name = _split_url_name(url_name)
    if not namespace:
        return False

    if route_name.startswith(SKIP_PREFIXES):
        return False
    if route_name.endswith(SKIP_SUFFIXES):
        return False
    if "autocomplete" in route_name or route_name.startswith("api_"):
        return False
    return True


def _can_reverse_without_args(url_name: str) -> bool:
    try:
        reverse(url_name)
        return True
    except NoReverseMatch:
        return False


def _label_from_url_name(url_name: str) -> str:
    _namespace, route_name = _split_url_name(url_name)
    raw = route_name.replace("_", " ").strip()
    label = raw.title()

    replacements = {
        "Nee": "NEE",
        "Cid": "CID",
        "Cpf": "CPF",
        "Api": "API",
        "Rbac": "RBAC",
        "Sus": "SUS",
        "Govbr": "GovBR",
    }
    for src, dst in replacements.items():
        label = label.replace(src, dst)
    return label


def _route_sort_key(namespace: str, route_name: str):
    cfg = _namespace_config(namespace)
    priority = cfg.get("priority", [])
    if route_name in priority:
        return (0, priority.index(route_name), route_name)
    if route_name == "index":
        return (1, 0, route_name)
    if route_name.endswith("_list"):
        return (1, 1, route_name)
    if route_name.endswith("_create"):
        return (1, 2, route_name)
    if route_name.endswith("_update"):
        return (1, 3, route_name)
    if route_name.endswith("_detail"):
        return (1, 4, route_name)
    return (2, 0, route_name)


@lru_cache(maxsize=1)
def get_code_routes():
    grouped: dict[str, list[str]] = defaultdict(list)
    discovered = sorted(set(_iter_named_routes(get_resolver().url_patterns)))

    for url_name in discovered:
        if not _is_navigable_route(url_name):
            continue
        if not _can_reverse_without_args(url_name):
            continue
        namespace, _route_name = _split_url_name(url_name)
        if not namespace:
            continue
        grouped[namespace].append(url_name)

    routes: dict[str, dict] = {}

    for namespace in sorted(grouped.keys(), key=lambda ns: _namespace_config(ns)["start"]):
        cfg = _namespace_config(namespace)
        start = int(cfg["start"])
        end = int(cfg["end"])
        next_code = start

        ordered_names = sorted(
            grouped[namespace],
            key=lambda name: _route_sort_key(namespace, _split_url_name(name)[1]),
        )

        for url_name in ordered_names:
            while str(next_code) in routes and next_code <= end:
                next_code += 1
            if next_code > end:
                break

            code = str(next_code)
            routes[code] = {
                "label": _label_from_url_name(url_name),
                "url_name": url_name,
                "perm": cfg.get("perm"),
                "namespace": namespace,
                "setor": cfg.get("setor", "Outros"),
                "faixa": f"{start}-{end}",
            }
            next_code += 1

    return routes


def _resolve_code_to_url(user, code: str):
    if not code:
        return None

    code = (code or "").strip().upper()
    if code.startswith("#"):
        code = code[1:]
    if code.startswith("COD"):
        code = code[3:].strip()

    entry = get_code_routes().get(code)
    if not entry:
        return None

    perm = entry.get("perm")
    if perm and not (
        can(user, perm)
        or is_admin(user)
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    ):
        return None

    try:
        return reverse(entry["url_name"], args=entry.get("args", None), kwargs=entry.get("kwargs", None))
    except Exception:
        return None


@login_required
def go_code(request, codigo: str = ""):
    code = (codigo or request.GET.get("c") or request.POST.get("c") or "").strip()
    url = _resolve_code_to_url(request.user, code)

    if url:
        return redirect(url)

    messages.error(request, "Codigo invalido ou sem permissao para acessar.")
    back = request.META.get("HTTP_REFERER")
    return redirect(back or "core:dashboard")


@login_required
def guia_telas(request):
    q = (request.GET.get("q") or "").strip()

    actions = [
        {
            "label": "Voltar",
            "url": reverse("core:dashboard"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    headers = [
        {"label": "Codigo", "width": "120px"},
        {"label": "Tela"},
        {"label": "Modulo", "width": "160px"},
        {"label": "Setor", "width": "180px"},
        {"label": "Faixa", "width": "130px"},
    ]

    rows = []

    def _sort_key(item):
        code = item[0]
        try:
            return int(code)
        except Exception:
            return 999999

    for code, entry in sorted(get_code_routes().items(), key=_sort_key):
        url = _resolve_code_to_url(request.user, code)
        if not url:
            continue

        label = entry.get("label") or "-"
        url_name = entry.get("url_name") or ""
        modulo = (entry.get("namespace") or "").upper() or "CORE"
        setor = entry.get("setor") or "Outros"
        faixa = entry.get("faixa") or "-"

        if q:
            hay = f"{code} {label} {modulo} {setor} {faixa} {url_name}".lower()
            if q.lower() not in hay:
                continue

        rows.append(
            {
                "cells": [
                    {"text": code, "url": url},
                    {"text": label, "url": url},
                    {"text": modulo, "url": url},
                    {"text": setor, "url": url},
                    {"text": faixa, "url": url},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    action_url = reverse("core:guia_telas")
    clear_url = reverse("core:guia_telas")
    has_filters = bool(q)

    return render(
        request,
        "core/guia_telas.html",
        {
            "actions": actions,
            "q": q,
            "action_url": action_url,
            "clear_url": clear_url,
            "has_filters": has_filters,
            "headers": headers,
            "rows": rows,
        },
    )
