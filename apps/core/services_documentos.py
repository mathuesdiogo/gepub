from __future__ import annotations

from apps.core.models import DocumentoEmitido


def registrar_documento_emitido(*, tipo: str, titulo: str, gerado_por=None, origem_url: str = "", ativo: bool = True) -> DocumentoEmitido:
    """
    Cria um registro padrão de validação pública para documentos do GEPUB,
    preenchendo assinatura do emissor no momento da emissão.
    """
    return DocumentoEmitido.objects.create(
        tipo=tipo,
        titulo=titulo,
        gerado_por=gerado_por,
        assinatura_emitente=DocumentoEmitido._resolve_emitente_nome(gerado_por),
        assinatura_cargo=DocumentoEmitido._resolve_emitente_cargo(gerado_por),
        origem_url=origem_url,
        ativo=ativo,
    )
