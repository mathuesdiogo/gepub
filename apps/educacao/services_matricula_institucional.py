from __future__ import annotations

import re

from django.db import transaction
from django.utils import timezone


PREFIX_FALLBACK = "GEPUB"


class InstitutionalEnrollmentService:
    @classmethod
    def ensure_for_student(
        cls,
        *,
        aluno,
        unidade=None,
        ano_referencia: int | None = None,
        usuario=None,
        status: str | None = None,
    ):
        from .models_biblioteca import MatriculaInstitucional, MatriculaInstitucionalHistorico

        ano = int(ano_referencia or timezone.localdate().year)
        unidade = unidade or cls._resolve_unidade_from_student(aluno)
        municipio = cls._resolve_municipio_from_unidade(unidade)
        target_status = None
        if status:
            target_status = (status or "").upper()
            if target_status not in set(MatriculaInstitucional.Status.values):
                target_status = MatriculaInstitucional.Status.ATIVA

        with transaction.atomic():
            enrollment = (
                MatriculaInstitucional.objects.select_for_update()
                .select_related("aluno")
                .filter(aluno=aluno)
                .first()
            )
            if enrollment:
                updated_fields = []
                if unidade and enrollment.unidade_origem_id is None:
                    enrollment.unidade_origem = unidade
                    updated_fields.append("unidade_origem")
                if municipio and enrollment.municipio_id is None:
                    enrollment.municipio = municipio
                    updated_fields.append("municipio")
                if target_status and enrollment.status != target_status:
                    old_status = enrollment.status
                    enrollment.status = target_status
                    if target_status == MatriculaInstitucional.Status.ATIVA and not enrollment.data_ativacao:
                        enrollment.data_ativacao = timezone.localdate()
                        updated_fields.append("data_ativacao")
                    if target_status != MatriculaInstitucional.Status.ATIVA and not enrollment.data_encerramento:
                        enrollment.data_encerramento = timezone.localdate()
                        updated_fields.append("data_encerramento")
                    updated_fields.append("status")
                    MatriculaInstitucionalHistorico.objects.create(
                        matricula_institucional=enrollment,
                        status_anterior=old_status,
                        status_novo=target_status,
                        contexto="AUTO_STATUS",
                        motivo="Atualização automática de status da matrícula institucional.",
                        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
                    )
                if updated_fields:
                    updated_fields.append("atualizado_em")
                    enrollment.save(update_fields=updated_fields)
                return enrollment

            prefix = cls._resolve_prefix(unidade=unidade, municipio=municipio)
            numero = cls._generate_number(prefix=prefix, ano=ano)
            create_status = target_status or MatriculaInstitucional.Status.ATIVA
            enrollment = MatriculaInstitucional.objects.create(
                aluno=aluno,
                numero_matricula=numero,
                ano_referencia=ano,
                municipio=municipio,
                unidade_origem=unidade,
                status=create_status,
                data_ativacao=timezone.localdate(),
                criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            )
            MatriculaInstitucionalHistorico.objects.create(
                matricula_institucional=enrollment,
                status_anterior="",
                status_novo=create_status,
                contexto="CRIACAO_AUTOMATICA",
                motivo="Geração automática da matrícula institucional.",
                usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
            )
            return enrollment

    @classmethod
    def resolve_active_for_student(cls, *, aluno):
        from .models_biblioteca import MatriculaInstitucional

        enrollment = MatriculaInstitucional.objects.select_related("aluno").filter(aluno=aluno).first()
        if enrollment is None:
            enrollment = cls.ensure_for_student(aluno=aluno)
        if enrollment.status != MatriculaInstitucional.Status.ATIVA:
            raise ValueError("A matrícula institucional do aluno não está ativa.")
        return enrollment

    @classmethod
    def sync_status_from_student(cls, *, aluno, usuario=None, contexto: str = "AUTO_SYNC"):
        from .models import Matricula
        from .models_biblioteca import MatriculaInstitucional, MatriculaInstitucionalHistorico

        enrollment = MatriculaInstitucional.objects.select_for_update().filter(aluno=aluno).first()
        if enrollment is None:
            return None

        has_active = Matricula.objects.filter(
            aluno=aluno,
            situacao=Matricula.Situacao.ATIVA,
        ).exists()

        target_status = enrollment.status
        if enrollment.status == MatriculaInstitucional.Status.BLOQUEADA:
            return enrollment
        if has_active and enrollment.status in {
            MatriculaInstitucional.Status.INATIVA,
            MatriculaInstitucional.Status.TRANSFERIDA,
            MatriculaInstitucional.Status.CONCLUIDA,
            MatriculaInstitucional.Status.CANCELADA,
        }:
            target_status = MatriculaInstitucional.Status.ATIVA
        elif not has_active and enrollment.status == MatriculaInstitucional.Status.ATIVA:
            target_status = MatriculaInstitucional.Status.INATIVA

        if target_status == enrollment.status:
            return enrollment

        old_status = enrollment.status
        enrollment.status = target_status
        if target_status == MatriculaInstitucional.Status.ATIVA:
            if not enrollment.data_ativacao:
                enrollment.data_ativacao = timezone.localdate()
            enrollment.data_encerramento = None
        elif target_status != MatriculaInstitucional.Status.ATIVA and not enrollment.data_encerramento:
            enrollment.data_encerramento = timezone.localdate()
        enrollment.save(update_fields=["status", "data_ativacao", "data_encerramento", "atualizado_em"])
        MatriculaInstitucionalHistorico.objects.create(
            matricula_institucional=enrollment,
            status_anterior=old_status,
            status_novo=target_status,
            contexto=(contexto or "AUTO_SYNC")[:80],
            motivo="Sincronização automática de status com base no vínculo escolar.",
            usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
        return enrollment

    @classmethod
    def _resolve_unidade_from_student(cls, aluno):
        from .models import Matricula

        mat = (
            Matricula.objects.select_related("turma", "turma__unidade")
            .filter(aluno=aluno, situacao=Matricula.Situacao.ATIVA)
            .order_by("-id")
            .first()
        )
        if mat and mat.turma_id:
            return mat.turma.unidade
        return None

    @staticmethod
    def _resolve_municipio_from_unidade(unidade):
        if unidade is None:
            return None
        secretaria = getattr(unidade, "secretaria", None)
        return getattr(secretaria, "municipio", None)

    @classmethod
    def _resolve_prefix(cls, *, unidade=None, municipio=None) -> str:
        sigla = ""
        if unidade is not None:
            secretaria = getattr(unidade, "secretaria", None)
            sigla = (getattr(secretaria, "sigla", "") or "").strip().upper()
        if not sigla and municipio is not None:
            sigla = (getattr(municipio, "slug_site", "") or "").strip().upper()
        if not sigla:
            sigla = PREFIX_FALLBACK
        sigla = re.sub(r"[^A-Z0-9]+", "", sigla)
        if len(sigla) < 2:
            return PREFIX_FALLBACK
        return sigla[:10]

    @classmethod
    def _generate_number(cls, *, prefix: str, ano: int) -> str:
        from .models_biblioteca import MatriculaInstitucional

        base = f"{prefix}-{ano}-"
        last = (
            MatriculaInstitucional.objects.select_for_update()
            .filter(numero_matricula__startswith=base)
            .order_by("-id")
            .values_list("numero_matricula", flat=True)
            .first()
        )
        seq = 1
        if last:
            match = re.match(rf"^{re.escape(base)}(\d+)$", last)
            if match:
                seq = int(match.group(1)) + 1
        return f"{base}{seq:06d}"
