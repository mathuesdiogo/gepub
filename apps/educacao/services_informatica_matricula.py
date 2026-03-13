from __future__ import annotations

from .models_informatica import InformaticaMatricula, InformaticaMatriculaMovimentacao


def registrar_movimentacao_informatica(
    *,
    matricula: InformaticaMatricula,
    tipo: str,
    usuario=None,
    turma_origem=None,
    turma_destino=None,
    status_anterior: str = "",
    status_novo: str = "",
    motivo: str = "",
) -> InformaticaMatriculaMovimentacao:
    return InformaticaMatriculaMovimentacao.objects.create(
        matricula=matricula,
        aluno=matricula.aluno,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        tipo=tipo,
        turma_origem=turma_origem,
        turma_destino=turma_destino,
        status_anterior=status_anterior or "",
        status_novo=status_novo or "",
        motivo=(motivo or "").strip(),
    )
