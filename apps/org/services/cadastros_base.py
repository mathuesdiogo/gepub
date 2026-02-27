from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from apps.org.models import SecretariaCadastroBase


def listar_cadastros_base(
    *,
    municipio_id: int | None = None,
    secretaria_id: int | None = None,
    categoria: str | None = None,
    ativo: bool = True,
):
    qs = SecretariaCadastroBase.objects.select_related("secretaria", "secretaria__municipio")
    if ativo:
        qs = qs.filter(ativo=True)
    if secretaria_id:
        qs = qs.filter(secretaria_id=secretaria_id)
    elif municipio_id:
        qs = qs.filter(secretaria__municipio_id=municipio_id)
    if categoria:
        qs = qs.filter(categoria=categoria)
    return qs.order_by("categoria", "ordem", "nome")


def mapear_sugestoes_por_categoria(
    *,
    categorias: Iterable[str],
    municipio_id: int | None = None,
    secretaria_id: int | None = None,
    limit_por_categoria: int = 8,
) -> dict[str, list[str]]:
    categorias = [c for c in categorias if c]
    if not categorias:
        return {}

    qs = listar_cadastros_base(
        municipio_id=municipio_id,
        secretaria_id=secretaria_id,
    ).filter(categoria__in=categorias)

    result: dict[str, list[str]] = {c: [] for c in categorias}
    vistos: dict[str, set[str]] = defaultdict(set)

    for item in qs:
        if len(result[item.categoria]) >= limit_por_categoria:
            continue
        valor = (item.nome or "").strip()
        if not valor or valor in vistos[item.categoria]:
            continue
        vistos[item.categoria].add(valor)
        result[item.categoria].append(valor)

    return {k: v for k, v in result.items() if v}


def aplicar_sugestoes_em_campo(
    form,
    field_name: str,
    sugestoes: Iterable[str] | None,
    *,
    titulo: str = "Sugestões do cadastro-base",
) -> None:
    if field_name not in form.fields:
        return

    sugestoes = [s for s in (sugestoes or []) if s]
    if not sugestoes:
        return

    field = form.fields[field_name]
    texto = f"{titulo}: {', '.join(sugestoes)}."
    field.help_text = f"{field.help_text} {texto}".strip() if field.help_text else texto

    widget_attrs = getattr(field.widget, "attrs", None)
    if isinstance(widget_attrs, dict) and not widget_attrs.get("placeholder"):
        widget_attrs["placeholder"] = sugestoes[0]
