from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet

from apps.core.models import (
    AuditoriaEvento,
    OperacaoRegistroAnexo,
    OperacaoRegistroComentario,
    OperacaoRegistroTag,
)
from apps.core.rbac import get_profile, is_admin


@dataclass(frozen=True)
class RegistroEntitySpec:
    modulo: str
    entidade: str
    model_path: str
    manage_perm: str
    view_perm: str


REGISTRO_ENTITY_SPECS: dict[tuple[str, str], RegistroEntitySpec] = {
    ("PROCESSOS", "ProcessoAdministrativo"): RegistroEntitySpec(
        modulo="PROCESSOS",
        entidade="ProcessoAdministrativo",
        model_path="apps.processos.models.ProcessoAdministrativo",
        manage_perm="processos.manage",
        view_perm="processos.view",
    ),
    ("COMPRAS", "RequisicaoCompra"): RegistroEntitySpec(
        modulo="COMPRAS",
        entidade="RequisicaoCompra",
        model_path="apps.compras.models.RequisicaoCompra",
        manage_perm="compras.manage",
        view_perm="compras.view",
    ),
    ("CONTRATOS", "ContratoAdministrativo"): RegistroEntitySpec(
        modulo="CONTRATOS",
        entidade="ContratoAdministrativo",
        model_path="apps.contratos.models.ContratoAdministrativo",
        manage_perm="contratos.manage",
        view_perm="contratos.view",
    ),
    ("FINANCEIRO", "DespEmpenho"): RegistroEntitySpec(
        modulo="FINANCEIRO",
        entidade="DespEmpenho",
        model_path="apps.financeiro.models.DespEmpenho",
        manage_perm="financeiro.manage",
        view_perm="financeiro.view",
    ),
    ("FINANCEIRO", "DespRestosPagar"): RegistroEntitySpec(
        modulo="FINANCEIRO",
        entidade="DespRestosPagar",
        model_path="apps.financeiro.models.DespRestosPagar",
        manage_perm="financeiro.manage",
        view_perm="financeiro.view",
    ),
    ("FINANCEIRO", "TesExtratoImportacao"): RegistroEntitySpec(
        modulo="FINANCEIRO",
        entidade="TesExtratoImportacao",
        model_path="apps.financeiro.models.TesExtratoImportacao",
        manage_perm="financeiro.tesouraria",
        view_perm="financeiro.tesouraria",
    ),
}


def normalize_modulo(value: str | None) -> str:
    return (value or "").strip().upper()


def normalize_entidade(value: str | None) -> str:
    return (value or "").strip()


def _import_string(path: str):
    module_name, attr_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[attr_name])
    return getattr(module, attr_name)


def get_entity_spec(modulo: str, entidade: str) -> RegistroEntitySpec | None:
    return REGISTRO_ENTITY_SPECS.get((normalize_modulo(modulo), normalize_entidade(entidade)))


def user_has_scope_for_municipio(user, municipio_id: int | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_admin(user):
        return True
    profile = get_profile(user)
    if not profile or not getattr(profile, "ativo", True):
        return False
    return bool(municipio_id and profile.municipio_id == municipio_id)


def resolve_entity_instance(modulo: str, entidade: str, entidade_id: int | str):
    spec = get_entity_spec(modulo, entidade)
    if not spec:
        return None
    model = _import_string(spec.model_path)
    return model.objects.filter(pk=entidade_id).first()


def build_registro_context(*, municipio, modulo: str, entidade: str, entidade_id: int | str, limit: int = 80) -> dict[str, Any]:
    entidade_id_str = str(entidade_id)
    tags_qs = OperacaoRegistroTag.objects.filter(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=entidade_id_str,
    ).order_by("tag")
    comentarios_qs = OperacaoRegistroComentario.objects.filter(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=entidade_id_str,
    ).select_related("criado_por").order_by("-criado_em")
    anexos_qs = OperacaoRegistroAnexo.objects.filter(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=entidade_id_str,
    ).select_related("criado_por").order_by("-criado_em")
    auditoria_qs = AuditoriaEvento.objects.filter(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=entidade_id_str,
    ).select_related("usuario").order_by("-criado_em")[:limit]

    timeline = []
    for row in auditoria_qs:
        timeline.append(
            {
                "tipo": "auditoria",
                "quando": row.criado_em,
                "titulo": row.evento,
                "descricao": row.observacao or "",
                "usuario": row.usuario,
            }
        )
    for row in comentarios_qs[:limit]:
        timeline.append(
            {
                "tipo": "comentario",
                "quando": row.criado_em,
                "titulo": "Comentario interno" if row.interno else "Comentario publico",
                "descricao": row.comentario,
                "usuario": row.criado_por,
            }
        )
    for row in anexos_qs[:limit]:
        timeline.append(
            {
                "tipo": "anexo",
                "quando": row.criado_em,
                "titulo": row.titulo or row.arquivo.name.split("/")[-1],
                "descricao": row.tipo or "",
                "usuario": row.criado_por,
            }
        )
    timeline.sort(key=lambda item: item["quando"], reverse=True)

    return {
        "registro_modulo": modulo,
        "registro_entidade": entidade,
        "registro_entidade_id": entidade_id_str,
        "registro_tags": tags_qs,
        "registro_comentarios": comentarios_qs[:limit],
        "registro_anexos": anexos_qs[:limit],
        "registro_timeline": timeline[:limit],
    }


def save_registro_tag(*, municipio, modulo: str, entidade: str, entidade_id: int | str, tag: str, user=None):
    value = (tag or "").strip()
    if not value:
        return None
    obj, _created = OperacaoRegistroTag.objects.get_or_create(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id),
        tag=value,
        defaults={"criado_por": user},
    )
    return obj


def save_registro_comentario(
    *,
    municipio,
    modulo: str,
    entidade: str,
    entidade_id: int | str,
    comentario: str,
    interno: bool = True,
    user=None,
):
    text = (comentario or "").strip()
    if not text:
        return None
    return OperacaoRegistroComentario.objects.create(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id),
        comentario=text,
        interno=bool(interno),
        criado_por=user,
    )


def save_registro_anexo(
    *,
    municipio,
    modulo: str,
    entidade: str,
    entidade_id: int | str,
    arquivo,
    tipo: str = "",
    titulo: str = "",
    observacao: str = "",
    user=None,
):
    if not arquivo:
        return None
    return OperacaoRegistroAnexo.objects.create(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id),
        arquivo=arquivo,
        tipo=(tipo or "").strip(),
        titulo=(titulo or "").strip(),
        observacao=(observacao or "").strip(),
        criado_por=user,
    )


def get_registro_events_queryset(*, municipio, modulo: str, entidade: str, entidade_id: int | str) -> QuerySet[AuditoriaEvento]:
    return AuditoriaEvento.objects.filter(
        municipio=municipio,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id),
    ).order_by("-criado_em")
