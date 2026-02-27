from __future__ import annotations

from .models import AuditoriaEvento


def registrar_auditoria(
    *,
    municipio,
    modulo: str,
    evento: str,
    entidade: str,
    entidade_id,
    usuario=None,
    antes=None,
    depois=None,
    observacao: str = "",
):
    return AuditoriaEvento.objects.create(
        municipio=municipio,
        modulo=(modulo or "").upper()[:40],
        evento=(evento or "")[:80],
        entidade=(entidade or "")[:80],
        entidade_id=str(entidade_id),
        usuario=usuario,
        antes=antes or {},
        depois=depois or {},
        observacao=(observacao or "")[:200],
    )
