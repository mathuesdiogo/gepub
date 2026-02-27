from __future__ import annotations

from decimal import Decimal

from .models import TransparenciaEventoPublico


def publicar_evento_transparencia(
    *,
    municipio,
    modulo: str,
    tipo_evento: str,
    titulo: str,
    descricao: str = "",
    referencia: str = "",
    valor=None,
    dados=None,
    publico: bool = True,
    data_evento=None,
):
    val = None
    if valor is not None and str(valor) != "":
        val = Decimal(str(valor))

    payload = dados or {}
    payload = dict(payload)

    create_kwargs = {
        "municipio": municipio,
        "modulo": (modulo or TransparenciaEventoPublico.Modulo.OUTROS).upper(),
        "tipo_evento": (tipo_evento or "")[:80],
        "titulo": (titulo or "")[:220],
        "descricao": descricao or "",
        "referencia": (referencia or "")[:120],
        "valor": val,
        "dados": payload,
        "publico": bool(publico),
    }
    if data_evento is not None:
        create_kwargs["data_evento"] = data_evento

    return TransparenciaEventoPublico.objects.create(
        **create_kwargs,
    )
