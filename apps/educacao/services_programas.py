from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models_programas import (
    ProgramaComplementar,
    ProgramaComplementarFrequencia,
    ProgramaComplementarHorario,
    ProgramaComplementarOferta,
    ProgramaComplementarParticipacao,
    ProgramaComplementarParticipacaoLog,
    calculate_age,
)
from .services_biblioteca import LibraryLoanService
from .services_matricula_institucional import InstitutionalEnrollmentService
from .services_schedule_conflicts import ScheduleConflictService


class ProgramasComplementaresService:
    @staticmethod
    def find_student_by_identifier(identifier: str):
        return LibraryLoanService.find_student_by_identifier(identifier)

    @classmethod
    def _assert_eligible(
        cls,
        *,
        aluno,
        oferta: ProgramaComplementarOferta,
        data_ingresso: date | None,
    ) -> None:
        if oferta.status != ProgramaComplementarOferta.Status.ATIVA:
            raise ValueError("A oferta selecionada não está ativa para matrícula.")
        if oferta.programa.status != ProgramaComplementar.Status.ATIVO:
            raise ValueError("O programa selecionado não está ativo para novas participações.")

        enrollment = InstitutionalEnrollmentService.resolve_active_for_student(aluno=aluno)
        if enrollment.status != enrollment.Status.ATIVA:
            raise ValueError("A matrícula institucional do aluno não está ativa.")

        requires_school_link = bool(oferta.exige_vinculo_escolar_ativo or oferta.programa.exige_vinculo_escolar_ativo)
        if requires_school_link:
            from .models import Matricula

            if not Matricula.objects.filter(aluno=aluno, situacao=Matricula.Situacao.ATIVA).exists():
                raise ValueError("Somente alunos com vínculo escolar ativo podem participar deste programa.")

        ref_date = data_ingresso or timezone.localdate()
        aluno_age = calculate_age(getattr(aluno, "data_nascimento", None), ref_date=ref_date)
        if aluno_age is not None:
            min_age = oferta.idade_minima if oferta.idade_minima is not None else oferta.programa.faixa_etaria_min
            max_age = oferta.idade_maxima if oferta.idade_maxima is not None else oferta.programa.faixa_etaria_max
            if min_age is not None and int(aluno_age) < int(min_age):
                raise ValueError("Aluno abaixo da faixa etária mínima permitida para a oferta.")
            if max_age is not None and int(aluno_age) > int(max_age):
                raise ValueError("Aluno acima da faixa etária máxima permitida para a oferta.")

        active_count = oferta.participacoes.filter(status=ProgramaComplementarParticipacao.Status.ATIVO).count()
        if active_count >= int(oferta.capacidade_maxima):
            raise ValueError("Oferta sem vagas disponíveis (capacidade máxima atingida).")

    @classmethod
    def create_participation(
        cls,
        *,
        aluno,
        oferta: ProgramaComplementarOferta,
        usuario=None,
        data_ingresso: date | None = None,
        status: str = ProgramaComplementarParticipacao.Status.ATIVO,
        escola_origem=None,
        allow_override_conflict: bool = False,
        override_justificativa: str = "",
        observacoes: str = "",
        origem_vinculo: str = "MANUAL",
    ) -> ProgramaComplementarParticipacao:
        ingresso = data_ingresso or timezone.localdate()
        cls._assert_eligible(aluno=aluno, oferta=oferta, data_ingresso=ingresso)
        enrollment = InstitutionalEnrollmentService.resolve_active_for_student(aluno=aluno)

        if not oferta.programa.permite_multiplas_participacoes:
            exists_active_same_program = ProgramaComplementarParticipacao.objects.filter(
                aluno=aluno,
                programa=oferta.programa,
                status=ProgramaComplementarParticipacao.Status.ATIVO,
            ).exists()
            if exists_active_same_program:
                raise ValueError("Aluno já possui participação ativa neste programa.")

        if allow_override_conflict and not ScheduleConflictService.can_user_override(usuario):
            raise ValueError("Seu perfil não possui permissão para forçar exceção de conflito de horário.")

        result = ScheduleConflictService.ensure_program_enrollment_allowed(
            aluno=aluno,
            oferta=oferta,
            data_ingresso=ingresso,
            allow_override=allow_override_conflict,
            override_justificativa=override_justificativa,
            usuario=usuario,
            contexto="PROGRAMA_COMPLEMENTAR",
        )
        if result.has_conflict and result.blocking_mode == "block" and not allow_override_conflict:
            raise ValueError(result.message)

        with transaction.atomic():
            participation = ProgramaComplementarParticipacao.objects.create(
                aluno=aluno,
                matricula_institucional=enrollment,
                programa=oferta.programa,
                oferta=oferta,
                escola_origem=escola_origem,
                ano_letivo=oferta.ano_letivo,
                status=(status or ProgramaComplementarParticipacao.Status.ATIVO),
                data_ingresso=ingresso,
                origem_vinculo=(origem_vinculo or "MANUAL")[:80],
                observacoes=(observacoes or "").strip(),
                criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            )
            ProgramaComplementarParticipacaoLog.objects.create(
                participacao=participation,
                acao=ProgramaComplementarParticipacaoLog.Acao.CRIACAO,
                status_anterior="",
                status_novo=participation.status,
                executado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
                notas="Participação registrada.",
            )
            return participation

    @classmethod
    def update_participation_status(
        cls,
        *,
        participacao: ProgramaComplementarParticipacao,
        novo_status: str,
        usuario=None,
        motivo: str = "",
    ) -> ProgramaComplementarParticipacao:
        novo = (novo_status or "").strip().upper()
        if novo not in set(ProgramaComplementarParticipacao.Status.values):
            raise ValueError("Status inválido para participação no programa.")
        if participacao.status == novo:
            return participacao

        old = participacao.status
        participacao.status = novo
        if novo in {
            ProgramaComplementarParticipacao.Status.CANCELADO,
            ProgramaComplementarParticipacao.Status.CONCLUIDO,
            ProgramaComplementarParticipacao.Status.DESLIGADO,
            ProgramaComplementarParticipacao.Status.TRANSFERIDO,
            ProgramaComplementarParticipacao.Status.SUSPENSO,
        } and not participacao.data_saida:
            participacao.data_saida = timezone.localdate()
        if motivo:
            participacao.motivo_saida = (motivo or "").strip()
        participacao.save(update_fields=["status", "data_saida", "motivo_saida", "atualizado_em"])
        ProgramaComplementarParticipacaoLog.objects.create(
            participacao=participacao,
            acao=ProgramaComplementarParticipacaoLog.Acao.MUDANCA_STATUS,
            status_anterior=old,
            status_novo=novo,
            executado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            notas=(motivo or "").strip(),
        )
        return participacao

    @classmethod
    def register_attendance(
        cls,
        *,
        participacao: ProgramaComplementarParticipacao,
        data_aula: date,
        status_presenca: str,
        usuario=None,
        justificativa: str = "",
        observacoes: str = "",
    ) -> ProgramaComplementarFrequencia:
        if participacao.status != ProgramaComplementarParticipacao.Status.ATIVO:
            raise ValueError("Somente participações ativas podem receber frequência.")
        status_val = (status_presenca or "").strip().upper()
        if status_val not in set(ProgramaComplementarFrequencia.StatusPresenca.values):
            raise ValueError("Status de presença inválido.")

        freq, _ = ProgramaComplementarFrequencia.objects.update_or_create(
            participacao=participacao,
            data_aula=data_aula,
            defaults={
                "status_presenca": status_val,
                "justificativa": (justificativa or "").strip(),
                "registrado_por": usuario if getattr(usuario, "is_authenticated", False) else None,
                "observacoes": (observacoes or "").strip(),
            },
        )
        ProgramaComplementarParticipacaoLog.objects.create(
            participacao=participacao,
            acao=ProgramaComplementarParticipacaoLog.Acao.FREQUENCIA,
            status_anterior=participacao.status,
            status_novo=participacao.status,
            executado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            notas=f"Frequência registrada para {data_aula:%d/%m/%Y}: {freq.get_status_presenca_display()}",
        )
        return freq

    @classmethod
    def _informatica_program_slug(cls, municipio_id: int | None) -> str:
        if municipio_id:
            return f"informatica-{municipio_id}"
        return "informatica"

    @classmethod
    def _map_informatica_status(cls, status: str) -> str:
        from .models_informatica import InformaticaMatricula

        mapping = {
            InformaticaMatricula.Status.PENDENTE: ProgramaComplementarParticipacao.Status.PRE_INSCRITO,
            InformaticaMatricula.Status.APROVADA: ProgramaComplementarParticipacao.Status.ATIVO,
            InformaticaMatricula.Status.MATRICULADO: ProgramaComplementarParticipacao.Status.ATIVO,
            InformaticaMatricula.Status.LISTA_ESPERA: ProgramaComplementarParticipacao.Status.AGUARDANDO_VAGA,
            InformaticaMatricula.Status.TRANSFERIDO: ProgramaComplementarParticipacao.Status.TRANSFERIDO,
            InformaticaMatricula.Status.CANCELADO: ProgramaComplementarParticipacao.Status.CANCELADO,
            InformaticaMatricula.Status.CONCLUIDO: ProgramaComplementarParticipacao.Status.CONCLUIDO,
        }
        return mapping.get(status, ProgramaComplementarParticipacao.Status.PRE_INSCRITO)

    @classmethod
    def sync_informatica_offer_schedule(cls, *, turma) -> ProgramaComplementarOferta | None:
        oferta = ProgramaComplementarOferta.objects.filter(legacy_informatica_turma=turma).first()
        if oferta is None:
            return None
        horarios = list(turma.encontros.filter(ativo=True).order_by("dia_semana", "hora_inicio"))
        with transaction.atomic():
            oferta.horarios.all().delete()
            novos = [
                ProgramaComplementarHorario(
                    oferta=oferta,
                    dia_semana=int(encontro.dia_semana),
                    hora_inicio=encontro.hora_inicio,
                    hora_fim=encontro.hora_fim,
                    frequencia_tipo=ProgramaComplementarHorario.FrequenciaTipo.SEMANAL,
                    turno=oferta.turno,
                    ativo=True,
                    observacoes="Sincronizado da turma de Informática.",
                )
                for encontro in horarios
            ]
            if novos:
                ProgramaComplementarHorario.objects.bulk_create(novos)
        return oferta

    @classmethod
    def sync_informatica_matricula(cls, *, matricula, usuario=None) -> ProgramaComplementarParticipacao | None:
        from .models import Matricula as MatriculaRegular
        from .models_informatica import InformaticaMatricula, InformaticaTurma

        if not matricula.aluno_id or not matricula.turma_id:
            return None
        turma: InformaticaTurma = matricula.turma
        unidade = getattr(getattr(turma, "laboratorio", None), "unidade", None)
        municipio = getattr(getattr(unidade, "secretaria", None), "municipio", None)
        secretaria = getattr(unidade, "secretaria", None)

        slug = cls._informatica_program_slug(getattr(municipio, "id", None))
        default_program_name = "Informática" if not municipio else f"Informática - {municipio.nome}"
        programa, _ = ProgramaComplementar.objects.get_or_create(
            slug=slug,
            defaults={
                "nome": default_program_name[:180],
                "tipo": ProgramaComplementar.Tipo.INFORMATICA,
                "descricao": "Programa complementar de Informática integrado ao cadastro institucional do aluno.",
                "objetivo": "Formação digital e uso pedagógico de tecnologia.",
                "exige_vinculo_escolar_ativo": True,
                "permite_multiplas_participacoes": True,
                "status": ProgramaComplementar.Status.ATIVO,
                "secretaria_responsavel": secretaria,
                "unidade_gestora": unidade,
            },
        )
        changed_program_fields = []
        if programa.tipo != ProgramaComplementar.Tipo.INFORMATICA:
            programa.tipo = ProgramaComplementar.Tipo.INFORMATICA
            changed_program_fields.append("tipo")
        if programa.status != ProgramaComplementar.Status.ATIVO:
            programa.status = ProgramaComplementar.Status.ATIVO
            changed_program_fields.append("status")
        if secretaria and programa.secretaria_responsavel_id is None:
            programa.secretaria_responsavel = secretaria
            changed_program_fields.append("secretaria_responsavel")
        if unidade and programa.unidade_gestora_id is None:
            programa.unidade_gestora = unidade
            changed_program_fields.append("unidade_gestora")
        if changed_program_fields:
            changed_program_fields.append("atualizado_em")
            programa.save(update_fields=changed_program_fields)

        offer_code = f"INF-{turma.codigo}"
        offer_name = turma.nome or turma.codigo
        oferta, created_offer = ProgramaComplementarOferta.objects.get_or_create(
            legacy_informatica_turma=turma,
            defaults={
                "programa": programa,
                "unidade": unidade,
                "ano_letivo": turma.ano_letivo,
                "codigo": slugify(offer_code).upper().replace("-", "")[:60] or offer_code[:60],
                "nome": offer_name[:180],
                "turno": turma.turno if turma.turno in ProgramaComplementarOferta.Turno.values else ProgramaComplementarOferta.Turno.FLEXIVEL,
                "capacidade_maxima": turma.max_vagas,
                "data_inicio": date(int(turma.ano_letivo), 1, 1),
                "data_fim": date(int(turma.ano_letivo), 12, 31),
                "responsavel": turma.instrutor,
                "status": (
                    ProgramaComplementarOferta.Status.ATIVA
                    if turma.status in {InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA}
                    else ProgramaComplementarOferta.Status.ENCERRADA
                ),
                "exige_vinculo_escolar_ativo": True,
                "permite_sobreposicao_horario": bool(getattr(turma, "permite_sobreposicao_horario", False)),
                "observacoes": "Oferta sincronizada automaticamente do módulo de Informática.",
            },
        )
        update_offer_fields = []
        if oferta.programa_id != programa.id:
            oferta.programa = programa
            update_offer_fields.append("programa")
        if unidade and oferta.unidade_id != unidade.id:
            oferta.unidade = unidade
            update_offer_fields.append("unidade")
        if int(oferta.ano_letivo or 0) != int(turma.ano_letivo or 0):
            oferta.ano_letivo = turma.ano_letivo
            update_offer_fields.append("ano_letivo")
        normalized_code = (slugify(offer_code).upper().replace("-", "")[:60] or offer_code[:60])
        if oferta.codigo != normalized_code:
            oferta.codigo = normalized_code
            update_offer_fields.append("codigo")
        if oferta.nome != offer_name:
            oferta.nome = offer_name
            update_offer_fields.append("nome")
        offer_turno = turma.turno if turma.turno in ProgramaComplementarOferta.Turno.values else ProgramaComplementarOferta.Turno.FLEXIVEL
        if oferta.turno != offer_turno:
            oferta.turno = offer_turno
            update_offer_fields.append("turno")
        if int(oferta.capacidade_maxima or 0) != int(turma.max_vagas or 0):
            oferta.capacidade_maxima = turma.max_vagas
            update_offer_fields.append("capacidade_maxima")
        mapped_offer_status = (
            ProgramaComplementarOferta.Status.ATIVA
            if turma.status in {InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA}
            else ProgramaComplementarOferta.Status.ENCERRADA
        )
        if oferta.status != mapped_offer_status:
            oferta.status = mapped_offer_status
            update_offer_fields.append("status")
        if oferta.permite_sobreposicao_horario != bool(getattr(turma, "permite_sobreposicao_horario", False)):
            oferta.permite_sobreposicao_horario = bool(getattr(turma, "permite_sobreposicao_horario", False))
            update_offer_fields.append("permite_sobreposicao_horario")
        if oferta.responsavel_id != getattr(turma, "instrutor_id", None):
            oferta.responsavel = getattr(turma, "instrutor", None)
            update_offer_fields.append("responsavel")
        if oferta.legacy_informatica_turma_id != turma.id:
            oferta.legacy_informatica_turma = turma
            update_offer_fields.append("legacy_informatica_turma")
        if update_offer_fields:
            update_offer_fields.append("atualizado_em")
            oferta.save(update_fields=update_offer_fields)
        if created_offer or update_offer_fields:
            cls.sync_informatica_offer_schedule(turma=turma)

        status_programa = cls._map_informatica_status(matricula.status)
        enrollment = None
        if status_programa == ProgramaComplementarParticipacao.Status.ATIVO:
            enrollment = InstitutionalEnrollmentService.resolve_active_for_student(aluno=matricula.aluno)
        else:
            enrollment = InstitutionalEnrollmentService.ensure_for_student(
                aluno=matricula.aluno,
                unidade=unidade,
                ano_referencia=turma.ano_letivo,
            )

        participation, created_part = ProgramaComplementarParticipacao.objects.get_or_create(
            legacy_informatica_matricula=matricula,
            defaults={
                "aluno": matricula.aluno,
                "matricula_institucional": enrollment,
                "programa": programa,
                "oferta": oferta,
                "escola_origem": matricula.escola_origem,
                "ano_letivo": turma.ano_letivo,
                "status": status_programa,
                "data_ingresso": matricula.data_matricula or timezone.localdate(),
                "origem_vinculo": "INFORMATICA_SYNC",
                "observacoes": "Participação sincronizada do módulo de Informática.",
                "criado_por": usuario if getattr(usuario, "is_authenticated", False) else getattr(matricula, "criado_por", None),
            },
        )

        changed = []
        if participation.aluno_id != matricula.aluno_id:
            participation.aluno = matricula.aluno
            changed.append("aluno")
        if participation.matricula_institucional_id != enrollment.id:
            participation.matricula_institucional = enrollment
            changed.append("matricula_institucional")
        if participation.programa_id != programa.id:
            participation.programa = programa
            changed.append("programa")
        if participation.oferta_id != oferta.id:
            participation.oferta = oferta
            changed.append("oferta")
        if participation.escola_origem_id != matricula.escola_origem_id:
            participation.escola_origem = matricula.escola_origem
            changed.append("escola_origem")
        if int(participation.ano_letivo or 0) != int(turma.ano_letivo or 0):
            participation.ano_letivo = turma.ano_letivo
            changed.append("ano_letivo")
        if participation.status != status_programa:
            old_status = participation.status
            participation.status = status_programa
            if status_programa in {
                ProgramaComplementarParticipacao.Status.CONCLUIDO,
                ProgramaComplementarParticipacao.Status.CANCELADO,
                ProgramaComplementarParticipacao.Status.TRANSFERIDO,
                ProgramaComplementarParticipacao.Status.DESLIGADO,
                ProgramaComplementarParticipacao.Status.SUSPENSO,
            } and not participation.data_saida:
                participation.data_saida = timezone.localdate()
                changed.append("data_saida")
            if status_programa == ProgramaComplementarParticipacao.Status.ATIVO:
                participation.data_saida = None
                changed.append("data_saida")
            changed.append("status")
            ProgramaComplementarParticipacaoLog.objects.create(
                participacao=participation,
                acao=ProgramaComplementarParticipacaoLog.Acao.MUDANCA_STATUS,
                status_anterior=old_status,
                status_novo=status_programa,
                executado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
                notas="Status sincronizado do módulo de Informática.",
            )
        if participation.origem_vinculo != "INFORMATICA_SYNC":
            participation.origem_vinculo = "INFORMATICA_SYNC"
            changed.append("origem_vinculo")
        if changed:
            changed.append("atualizado_em")
            participation.save(update_fields=changed)
        if created_part:
            ProgramaComplementarParticipacaoLog.objects.create(
                participacao=participation,
                acao=ProgramaComplementarParticipacaoLog.Acao.CRIACAO,
                status_anterior="",
                status_novo=participation.status,
                executado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
                notas="Participação criada por sincronização automática da Informática.",
            )

        return participation
