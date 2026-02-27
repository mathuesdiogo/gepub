from __future__ import annotations

from .models import Matricula, MatriculaMovimentacao


def registrar_movimentacao(
    *,
    matricula: Matricula,
    tipo: str,
    usuario=None,
    turma_origem=None,
    turma_destino=None,
    situacao_anterior: str = "",
    situacao_nova: str = "",
    motivo: str = "",
) -> MatriculaMovimentacao:
    return MatriculaMovimentacao.objects.create(
        matricula=matricula,
        aluno=matricula.aluno,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        tipo=tipo,
        turma_origem=turma_origem,
        turma_destino=turma_destino,
        situacao_anterior=situacao_anterior or "",
        situacao_nova=situacao_nova or "",
        motivo=(motivo or "").strip(),
    )
