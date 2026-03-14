from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from .models import Matricula, MatriculaMovimentacao


@dataclass
class MovimentacaoResultado:
    matricula: Matricula
    movimentacao: MatriculaMovimentacao
    matricula_destino: Matricula | None = None


def registrar_movimentacao(
    *,
    matricula: Matricula,
    tipo: str,
    usuario=None,
    turma_origem=None,
    turma_destino=None,
    situacao_anterior: str = "",
    situacao_nova: str = "",
    data_referencia=None,
    tipo_trancamento: str = "",
    movimentacao_desfeita=None,
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
        data_referencia=data_referencia,
        tipo_trancamento=(tipo_trancamento or "").strip(),
        movimentacao_desfeita=movimentacao_desfeita,
        motivo=(motivo or "").strip(),
    )


@transaction.atomic
def aplicar_movimentacao_matricula(
    *,
    matricula: Matricula,
    tipo: str,
    usuario=None,
    turma_destino=None,
    data_referencia=None,
    tipo_trancamento: str = "",
    motivo: str = "",
) -> MovimentacaoResultado:
    tipo = (tipo or "").strip()
    motivo = (motivo or "").strip()
    turma_origem = matricula.turma
    situacao_anterior = matricula.situacao

    if tipo == MatriculaMovimentacao.Tipo.REMANEJAMENTO:
        if turma_destino is None:
            raise ValueError("Selecione a turma de destino para o remanejamento.")
        if turma_destino == turma_origem:
            raise ValueError("A turma de destino deve ser diferente da turma atual.")
        if Matricula.objects.filter(aluno=matricula.aluno, turma=turma_destino).exclude(pk=matricula.pk).exists():
            raise ValueError("Já existe matrícula deste aluno na turma de destino.")

        matricula.turma = turma_destino
        matricula.situacao = Matricula.Situacao.ATIVA
        matricula.save(update_fields=["turma", "situacao"])
        mov = registrar_movimentacao(
            matricula=matricula,
            tipo=tipo,
            usuario=usuario,
            turma_origem=turma_origem,
            turma_destino=turma_destino,
            situacao_anterior=situacao_anterior,
            situacao_nova=matricula.situacao,
            data_referencia=data_referencia,
            motivo=motivo,
        )
        return MovimentacaoResultado(matricula=matricula, movimentacao=mov)

    if tipo == MatriculaMovimentacao.Tipo.TRANSFERENCIA:
        if turma_destino is None:
            raise ValueError("Selecione a turma de destino para a transferência.")
        if turma_destino == turma_origem:
            raise ValueError("A turma de destino deve ser diferente da turma atual.")
        if Matricula.objects.filter(aluno=matricula.aluno, turma=turma_destino).exists():
            raise ValueError("Já existe matrícula deste aluno na turma de destino.")

        matricula.situacao = Matricula.Situacao.TRANSFERIDO
        matricula.save(update_fields=["situacao"])
        mov = registrar_movimentacao(
            matricula=matricula,
            tipo=tipo,
            usuario=usuario,
            turma_origem=turma_origem,
            turma_destino=turma_destino,
            situacao_anterior=situacao_anterior,
            situacao_nova=matricula.situacao,
            data_referencia=data_referencia,
            motivo=motivo,
        )
        nova_matricula = Matricula.objects.create(
            aluno=matricula.aluno,
            turma=turma_destino,
            data_matricula=data_referencia or date.today(),
            situacao=Matricula.Situacao.ATIVA,
            observacao=(f"Transferência da matrícula #{matricula.pk}. {motivo}".strip()),
        )
        registrar_movimentacao(
            matricula=nova_matricula,
            tipo=MatriculaMovimentacao.Tipo.CRIACAO,
            usuario=usuario,
            turma_origem=turma_origem,
            turma_destino=turma_destino,
            data_referencia=data_referencia,
            situacao_nova=nova_matricula.situacao,
            motivo="Matrícula de destino criada automaticamente por transferência.",
        )
        return MovimentacaoResultado(
            matricula=matricula,
            movimentacao=mov,
            matricula_destino=nova_matricula,
        )

    if tipo == MatriculaMovimentacao.Tipo.CANCELAMENTO:
        matricula.situacao = Matricula.Situacao.CANCELADO
    elif tipo == MatriculaMovimentacao.Tipo.TRANCAMENTO:
        if not tipo_trancamento:
            raise ValueError("Selecione o tipo de trancamento.")
        matricula.situacao = Matricula.Situacao.TRANCADO
    elif tipo == MatriculaMovimentacao.Tipo.REATIVACAO:
        matricula.situacao = Matricula.Situacao.ATIVA
    else:
        raise ValueError("Tipo de movimentação inválido.")

    matricula.save(update_fields=["situacao"])
    mov = registrar_movimentacao(
        matricula=matricula,
        tipo=tipo,
        usuario=usuario,
        turma_origem=turma_origem,
        turma_destino=turma_origem,
        situacao_anterior=situacao_anterior,
        situacao_nova=matricula.situacao,
        data_referencia=data_referencia,
        tipo_trancamento=tipo_trancamento if tipo == MatriculaMovimentacao.Tipo.TRANCAMENTO else "",
        motivo=motivo,
    )
    return MovimentacaoResultado(matricula=matricula, movimentacao=mov)

def _ultima_movimentacao_desfazivel(matricula: Matricula) -> MatriculaMovimentacao | None:
    return (
        MatriculaMovimentacao.objects.filter(matricula=matricula)
        .exclude(tipo=MatriculaMovimentacao.Tipo.CRIACAO)
        .exclude(tipo=MatriculaMovimentacao.Tipo.DESFAZER)
        .order_by("-criado_em", "-id")
        .first()
    )


@transaction.atomic
def desfazer_movimentacao_matricula(
    *,
    matricula: Matricula,
    usuario=None,
    motivo: str = "",
    movimentacao_id: int | None = None,
) -> MovimentacaoResultado:
    ultima = _ultima_movimentacao_desfazivel(matricula)
    target = ultima

    if movimentacao_id is not None:
        target = (
            MatriculaMovimentacao.objects.filter(
                matricula=matricula,
                id=movimentacao_id,
            )
            .exclude(tipo=MatriculaMovimentacao.Tipo.CRIACAO)
            .exclude(tipo=MatriculaMovimentacao.Tipo.DESFAZER)
            .first()
        )
    if target is None:
        raise ValueError("Nenhuma movimentação elegível para desfazer.")
    if ultima is None or target.id != ultima.id:
        raise ValueError("Só é possível desfazer o último procedimento.")

    ultima = target
    if ultima is None:
        raise ValueError("Nenhuma movimentação elegível para desfazer.")
    if ultima.tipo == MatriculaMovimentacao.Tipo.TRANSFERENCIA:
        raise ValueError("Transferência não pode ser desfeita automaticamente.")
    if ultima.tipo not in {
        MatriculaMovimentacao.Tipo.REMANEJAMENTO,
        MatriculaMovimentacao.Tipo.CANCELAMENTO,
        MatriculaMovimentacao.Tipo.TRANCAMENTO,
        MatriculaMovimentacao.Tipo.REATIVACAO,
        MatriculaMovimentacao.Tipo.SITUACAO,
    }:
        raise ValueError("Este tipo de movimentação não suporta desfazer.")

    turma_atual = matricula.turma
    situacao_atual = matricula.situacao
    turma_restaurada = ultima.turma_origem or turma_atual
    situacao_restaurada = ultima.situacao_anterior or Matricula.Situacao.ATIVA

    update_fields: list[str] = []
    if matricula.turma_id != getattr(turma_restaurada, "id", None):
        matricula.turma = turma_restaurada
        update_fields.append("turma")
    if matricula.situacao != situacao_restaurada:
        matricula.situacao = situacao_restaurada
        update_fields.append("situacao")
    if update_fields:
        matricula.save(update_fields=update_fields)

    mov = registrar_movimentacao(
        matricula=matricula,
        tipo=MatriculaMovimentacao.Tipo.DESFAZER,
        usuario=usuario,
        turma_origem=turma_atual,
        turma_destino=turma_restaurada,
        situacao_anterior=situacao_atual,
        situacao_nova=matricula.situacao,
        data_referencia=ultima.data_referencia,
        movimentacao_desfeita=ultima,
        motivo=f"Desfeito movimento #{ultima.id}. {(motivo or '').strip()}".strip(),
    )
    return MovimentacaoResultado(matricula=matricula, movimentacao=mov)


@transaction.atomic
def desfazer_ultima_movimentacao_matricula(
    *,
    matricula: Matricula,
    usuario=None,
    motivo: str = "",
) -> MovimentacaoResultado:
    return desfazer_movimentacao_matricula(
        matricula=matricula,
        usuario=usuario,
        motivo=motivo,
        movimentacao_id=None,
    )
