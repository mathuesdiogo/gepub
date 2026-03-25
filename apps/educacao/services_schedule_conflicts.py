from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

from django.core.exceptions import ValidationError

from apps.core.rbac import can


WEEKDAY_LABELS = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
}

_AULA_DIA_TO_WEEKDAY = {
    "SEG": 0,
    "TER": 1,
    "QUA": 2,
    "QUI": 3,
    "SEX": 4,
    "SAB": 5,
}


@dataclass
class ScheduleSlot:
    weekday: int
    start: time
    end: time
    frequency: str = "SEMANAL"


@dataclass
class EnrollmentScheduleContext:
    module: str
    enrollment_type: str
    enrollment_id: int | None
    offer_type: str
    offer_id: int | None
    offer_name: str
    status: str
    unit_name: str = ""
    secretaria_name: str = ""
    period_start: date | None = None
    period_end: date | None = None
    allow_overlap: bool = False
    slots: list[ScheduleSlot] = field(default_factory=list)


@dataclass
class ScheduleConflictItem:
    existing_enrollment_type: str
    existing_enrollment_id: int | None
    existing_offer_type: str
    existing_offer_id: int | None
    existing_offer_name: str
    weekday: int
    weekday_label: str
    existing_start: str
    existing_end: str
    new_start: str
    new_end: str
    unit_name: str
    secretaria_name: str
    existing_period_start: str | None
    existing_period_end: str | None
    new_offer_type: str
    new_offer_id: int | None
    new_offer_name: str
    frequency: str


@dataclass
class ScheduleValidationResult:
    has_conflict: bool
    blocking_mode: str
    message: str
    conflicts: list[ScheduleConflictItem] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_conflict": self.has_conflict,
            "blocking_mode": self.blocking_mode,
            "message": self.message,
            "suggested_actions": list(self.suggested_actions),
            "conflicts": [
                {
                    "existing_enrollment_id": item.existing_enrollment_id,
                    "existing_offer_name": item.existing_offer_name,
                    "existing_offer_type": item.existing_offer_type,
                    "weekday": item.weekday_label.lower(),
                    "existing_start": item.existing_start,
                    "existing_end": item.existing_end,
                    "new_start": item.new_start,
                    "new_end": item.new_end,
                    "unit_name": item.unit_name,
                }
                for item in self.conflicts
            ],
        }


@dataclass
class ScheduleEditImpactResult:
    has_conflict: bool
    blocking_mode: str
    message: str
    impacted_students: list[dict] = field(default_factory=list)


class ScheduleConflictService:
    OVERRIDE_PERMISSION = "educacao.manage"

    @classmethod
    def validate_regular_enrollment(
        cls,
        *,
        aluno,
        turma,
        data_matricula: date | None = None,
        exclude_matricula_id: int | None = None,
    ) -> ScheduleValidationResult:
        candidate = cls._candidate_from_regular_turma(
            turma=turma,
            data_inicio=data_matricula,
        )
        exclude = {
            "matricula_ids": {exclude_matricula_id} if exclude_matricula_id else set(),
        }
        return cls._validate_candidate(aluno_id=aluno.id, candidate=candidate, exclude=exclude)

    @classmethod
    def validate_course_enrollment(
        cls,
        *,
        aluno,
        curso,
        turma=None,
        data_matricula: date | None = None,
        data_conclusao: date | None = None,
        exclude_matricula_curso_id: int | None = None,
    ) -> ScheduleValidationResult:
        candidate = cls._candidate_from_course_offer(
            curso=curso,
            turma=turma,
            data_inicio=data_matricula,
            data_fim=data_conclusao,
        )
        exclude = {
            "matricula_curso_ids": {exclude_matricula_curso_id} if exclude_matricula_curso_id else set(),
        }
        return cls._validate_candidate(aluno_id=aluno.id, candidate=candidate, exclude=exclude)

    @classmethod
    def validate_informatica_enrollment(
        cls,
        *,
        aluno,
        turma,
        data_matricula: date | None = None,
        exclude_informatica_matricula_id: int | None = None,
    ) -> ScheduleValidationResult:
        candidate = cls._candidate_from_informatica_turma(
            turma=turma,
            data_inicio=data_matricula,
        )
        exclude = {
            "informatica_matricula_ids": (
                {exclude_informatica_matricula_id} if exclude_informatica_matricula_id else set()
            ),
        }
        return cls._validate_candidate(aluno_id=aluno.id, candidate=candidate, exclude=exclude)

    @classmethod
    def validate_program_enrollment(
        cls,
        *,
        aluno,
        oferta,
        data_ingresso: date | None = None,
        exclude_programa_participacao_id: int | None = None,
    ) -> ScheduleValidationResult:
        candidate = cls._candidate_from_program_offer(
            oferta=oferta,
            data_inicio=data_ingresso,
        )
        exclude = {
            "programa_participacao_ids": (
                {exclude_programa_participacao_id} if exclude_programa_participacao_id else set()
            ),
        }
        return cls._validate_candidate(aluno_id=aluno.id, candidate=candidate, exclude=exclude)

    @classmethod
    def ensure_regular_enrollment_allowed(
        cls,
        *,
        aluno,
        turma,
        data_matricula: date | None = None,
        exclude_matricula_id: int | None = None,
        allow_override: bool = False,
        override_justificativa: str = "",
        usuario=None,
        contexto: str = "",
        ip_origem: str = "",
    ) -> ScheduleValidationResult:
        result = cls.validate_regular_enrollment(
            aluno=aluno,
            turma=turma,
            data_matricula=data_matricula,
            exclude_matricula_id=exclude_matricula_id,
        )
        cls._enforce_result(
            result=result,
            aluno=aluno,
            allow_override=allow_override,
            override_justificativa=override_justificativa,
            usuario=usuario,
            contexto=contexto,
            ip_origem=ip_origem,
        )
        return result

    @classmethod
    def ensure_course_enrollment_allowed(
        cls,
        *,
        aluno,
        curso,
        turma=None,
        data_matricula: date | None = None,
        data_conclusao: date | None = None,
        exclude_matricula_curso_id: int | None = None,
        allow_override: bool = False,
        override_justificativa: str = "",
        usuario=None,
        contexto: str = "",
        ip_origem: str = "",
    ) -> ScheduleValidationResult:
        result = cls.validate_course_enrollment(
            aluno=aluno,
            curso=curso,
            turma=turma,
            data_matricula=data_matricula,
            data_conclusao=data_conclusao,
            exclude_matricula_curso_id=exclude_matricula_curso_id,
        )
        cls._enforce_result(
            result=result,
            aluno=aluno,
            allow_override=allow_override,
            override_justificativa=override_justificativa,
            usuario=usuario,
            contexto=contexto,
            ip_origem=ip_origem,
        )
        return result

    @classmethod
    def ensure_informatica_enrollment_allowed(
        cls,
        *,
        aluno,
        turma,
        data_matricula: date | None = None,
        exclude_informatica_matricula_id: int | None = None,
        allow_override: bool = False,
        override_justificativa: str = "",
        usuario=None,
        contexto: str = "",
        ip_origem: str = "",
    ) -> ScheduleValidationResult:
        result = cls.validate_informatica_enrollment(
            aluno=aluno,
            turma=turma,
            data_matricula=data_matricula,
            exclude_informatica_matricula_id=exclude_informatica_matricula_id,
        )
        cls._enforce_result(
            result=result,
            aluno=aluno,
            allow_override=allow_override,
            override_justificativa=override_justificativa,
            usuario=usuario,
            contexto=contexto,
            ip_origem=ip_origem,
        )
        return result

    @classmethod
    def ensure_program_enrollment_allowed(
        cls,
        *,
        aluno,
        oferta,
        data_ingresso: date | None = None,
        exclude_programa_participacao_id: int | None = None,
        allow_override: bool = False,
        override_justificativa: str = "",
        usuario=None,
        contexto: str = "",
        ip_origem: str = "",
    ) -> ScheduleValidationResult:
        result = cls.validate_program_enrollment(
            aluno=aluno,
            oferta=oferta,
            data_ingresso=data_ingresso,
            exclude_programa_participacao_id=exclude_programa_participacao_id,
        )
        cls._enforce_result(
            result=result,
            aluno=aluno,
            allow_override=allow_override,
            override_justificativa=override_justificativa,
            usuario=usuario,
            contexto=contexto,
            ip_origem=ip_origem,
        )
        return result

    @classmethod
    def validate_regular_turma_slot_change(
        cls,
        *,
        turma,
        dia_semana_codigo: str,
        hora_inicio: time,
        hora_fim: time,
    ) -> ScheduleEditImpactResult:
        setting = cls._resolve_setting()
        if not bool(getattr(setting, "validar_edicao_grade", True)):
            return ScheduleEditImpactResult(
                has_conflict=False,
                blocking_mode=cls._normalize_mode(getattr(setting, "blocking_mode", "")),
                message="Validação de conflito em edição de grade está desativada.",
            )

        weekday = _AULA_DIA_TO_WEEKDAY.get((dia_semana_codigo or "").upper())
        if weekday is None:
            return ScheduleEditImpactResult(
                has_conflict=False,
                blocking_mode=cls._normalize_mode(getattr(setting, "blocking_mode", "")),
                message="Dia da semana inválido para validação de conflito.",
            )

        from .models import Matricula

        impacts: list[dict] = []
        active_matriculas = Matricula.objects.select_related("aluno").filter(
            turma=turma,
            situacao=Matricula.Situacao.ATIVA,
        )
        for matricula in active_matriculas:
            candidate = cls._candidate_from_regular_turma(
                turma=turma,
                data_inicio=matricula.data_matricula,
                slots_override=[ScheduleSlot(weekday=weekday, start=hora_inicio, end=hora_fim)],
            )
            result = cls._validate_candidate(
                aluno_id=matricula.aluno_id,
                candidate=candidate,
                exclude={"offer_keys": {("TURMA", turma.id), ("ATIVIDADE_COMPLEMENTAR", turma.id)}},
            )
            if not result.has_conflict:
                continue
            impacts.append(
                {
                    "aluno_id": matricula.aluno_id,
                    "aluno_nome": matricula.aluno.nome,
                    "message": result.message,
                    "conflicts": result.conflicts[:3],
                }
            )

        mode = cls._normalize_mode(getattr(setting, "blocking_mode", ""))
        if not impacts:
            return ScheduleEditImpactResult(
                has_conflict=False,
                blocking_mode=mode,
                message="Nenhum conflito de horário foi identificado para os alunos da turma.",
            )

        return ScheduleEditImpactResult(
            has_conflict=True,
            blocking_mode=mode,
            message=(
                "A alteração proposta na grade criará conflito de horário para "
                f"{len(impacts)} aluno(s)."
            ),
            impacted_students=impacts,
        )

    @classmethod
    def validate_informatica_grade_change(
        cls,
        *,
        grade,
    ) -> ScheduleEditImpactResult:
        setting = cls._resolve_setting()
        if not bool(getattr(setting, "validar_edicao_grade", True)):
            return ScheduleEditImpactResult(
                has_conflict=False,
                blocking_mode=cls._normalize_mode(getattr(setting, "blocking_mode", "")),
                message="Validação de conflito em edição de grade está desativada.",
            )

        slots = cls._slots_from_informatica_grade(grade)
        if not slots:
            return ScheduleEditImpactResult(
                has_conflict=False,
                blocking_mode=cls._normalize_mode(getattr(setting, "blocking_mode", "")),
                message="A grade informada não possui blocos válidos para validação.",
            )

        from .models_informatica import InformaticaMatricula, InformaticaTurma

        impacts: list[dict] = []
        turmas_afetadas = grade.turmas.filter(
            status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA]
        ).select_related("curso", "laboratorio", "laboratorio__unidade", "laboratorio__unidade__secretaria")
        for turma in turmas_afetadas:
            matriculas_ativas = turma.matriculas.select_related("aluno").filter(
                status__in=InformaticaMatricula.statuses_ativos()
            )
            for matricula in matriculas_ativas:
                candidate = cls._candidate_from_informatica_turma(
                    turma=turma,
                    data_inicio=matricula.data_matricula,
                    slots_override=slots,
                )
                result = cls._validate_candidate(
                    aluno_id=matricula.aluno_id,
                    candidate=candidate,
                    exclude={"offer_keys": {("INFORMATICA_TURMA", turma.id)}},
                )
                if not result.has_conflict:
                    continue
                impacts.append(
                    {
                        "aluno_id": matricula.aluno_id,
                        "aluno_nome": matricula.aluno.nome,
                        "turma_codigo": turma.codigo,
                        "message": result.message,
                        "conflicts": result.conflicts[:3],
                    }
                )

        mode = cls._normalize_mode(getattr(setting, "blocking_mode", ""))
        if not impacts:
            return ScheduleEditImpactResult(
                has_conflict=False,
                blocking_mode=mode,
                message="Nenhum conflito identificado para alunos vinculados às turmas da grade.",
            )

        return ScheduleEditImpactResult(
            has_conflict=True,
            blocking_mode=mode,
            message=(
                "A alteração da grade de informática gerará conflito de horário para "
                f"{len(impacts)} matrícula(s) ativa(s)."
            ),
            impacted_students=impacts,
        )

    @classmethod
    def can_user_override(cls, user, setting=None) -> bool:
        if setting is None:
            setting = cls._resolve_setting()
        if not bool(getattr(setting, "permitir_excecao", True)):
            return False
        return bool(user and can(user, cls.OVERRIDE_PERMISSION))

    @classmethod
    def register_override(
        cls,
        *,
        aluno,
        usuario,
        justificativa: str,
        contexto: str,
        result: ScheduleValidationResult,
        ip_origem: str = "",
    ) -> list:
        from .models_schedule_conflicts import ScheduleConflictOverride

        if not result.has_conflict:
            return []

        justificativa = (justificativa or "").strip()
        created = []
        for item in result.conflicts:
            created.append(
                ScheduleConflictOverride.objects.create(
                    aluno=aluno,
                    usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
                    contexto=(contexto or "").strip().upper()[:80],
                    modo_aplicado=(result.blocking_mode or "block").upper()[:10],
                    justificativa=justificativa,
                    ip_origem=(ip_origem or "").strip()[:64],
                    nova_oferta_tipo=item.new_offer_type,
                    nova_oferta_id=item.new_offer_id,
                    nova_oferta_nome=item.new_offer_name[:220],
                    oferta_conflitante_tipo=item.existing_offer_type,
                    oferta_conflitante_id=item.existing_offer_id,
                    oferta_conflitante_nome=item.existing_offer_name[:220],
                    unidade_nome=(item.unit_name or "")[:180],
                    secretaria_nome=(item.secretaria_name or "")[:180],
                    payload_resumo={
                        "weekday": item.weekday_label,
                        "existing_start": item.existing_start,
                        "existing_end": item.existing_end,
                        "new_start": item.new_start,
                        "new_end": item.new_end,
                        "frequency": item.frequency,
                    },
                )
            )
        return created

    @classmethod
    def describe_conflicts(cls, result: ScheduleValidationResult, *, max_items: int = 3) -> list[str]:
        if not result.has_conflict:
            return []
        lines = [result.message]
        for item in result.conflicts[:max_items]:
            lines.append(
                (
                    f"{item.weekday_label} {item.new_start}-{item.new_end} conflita com "
                    f"{item.existing_offer_name} ({item.existing_start}-{item.existing_end})."
                )
            )
        if len(result.conflicts) > max_items:
            lines.append(f"... e mais {len(result.conflicts) - max_items} conflito(s).")
        return lines

    @classmethod
    def raise_if_blocking(
        cls,
        *,
        result: ScheduleValidationResult,
        field: str = "turma",
    ) -> None:
        if result.has_conflict and result.blocking_mode == "block":
            raise ValidationError({field: result.message})

    @classmethod
    def _enforce_result(
        cls,
        *,
        result: ScheduleValidationResult,
        aluno,
        allow_override: bool,
        override_justificativa: str,
        usuario,
        contexto: str,
        ip_origem: str,
    ) -> None:
        if not result.has_conflict or result.blocking_mode != "block":
            return

        setting = cls._resolve_setting()
        if allow_override and cls.can_user_override(usuario, setting=setting):
            justificativa = (override_justificativa or "").strip()
            if bool(getattr(setting, "exigir_justificativa_excecao", True)) and not justificativa:
                raise ValueError("Informe justificativa para forçar matrícula com conflito de horário.")
            cls.register_override(
                aluno=aluno,
                usuario=usuario,
                justificativa=justificativa,
                contexto=contexto,
                result=result,
                ip_origem=ip_origem,
            )
            return

        raise ValueError("\n".join(cls.describe_conflicts(result, max_items=2)))

    @classmethod
    def _validate_candidate(
        cls,
        *,
        aluno_id: int,
        candidate: EnrollmentScheduleContext,
        exclude: dict | None = None,
    ) -> ScheduleValidationResult:
        setting = cls._resolve_setting()
        mode = cls._normalize_mode(getattr(setting, "blocking_mode", ""))

        if candidate.allow_overlap:
            return ScheduleValidationResult(
                has_conflict=False,
                blocking_mode=mode,
                message="Oferta configurada para permitir sobreposição de horário.",
            )
        if not candidate.slots:
            return ScheduleValidationResult(
                has_conflict=False,
                blocking_mode=mode,
                message="Oferta sem grade horária estruturada para comparação.",
            )

        existing_contexts = cls._load_existing_contexts(aluno_id=aluno_id, exclude=exclude or {})
        conflicts: list[ScheduleConflictItem] = []
        seen: set[tuple] = set()
        for existing in existing_contexts:
            if existing.allow_overlap:
                continue
            if not bool(getattr(setting, "considerar_conflito_entre_modulos", True)):
                if existing.module != candidate.module:
                    continue
            if not cls._periods_overlap(
                candidate.period_start,
                candidate.period_end,
                existing.period_start,
                existing.period_end,
            ):
                continue
            for new_slot in candidate.slots:
                for old_slot in existing.slots:
                    if int(new_slot.weekday) != int(old_slot.weekday):
                        continue
                    if not cls._times_overlap(
                        new_slot.start,
                        new_slot.end,
                        old_slot.start,
                        old_slot.end,
                        allow_touching=bool(getattr(setting, "considerar_intervalos_encostados_validos", True)),
                    ):
                        continue
                    key = (
                        existing.enrollment_type,
                        existing.enrollment_id,
                        existing.offer_type,
                        existing.offer_id,
                        new_slot.weekday,
                        new_slot.start,
                        new_slot.end,
                        old_slot.start,
                        old_slot.end,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    conflicts.append(
                        ScheduleConflictItem(
                            existing_enrollment_type=existing.enrollment_type,
                            existing_enrollment_id=existing.enrollment_id,
                            existing_offer_type=existing.offer_type,
                            existing_offer_id=existing.offer_id,
                            existing_offer_name=existing.offer_name,
                            weekday=int(new_slot.weekday),
                            weekday_label=WEEKDAY_LABELS.get(int(new_slot.weekday), str(new_slot.weekday)),
                            existing_start=old_slot.start.strftime("%H:%M"),
                            existing_end=old_slot.end.strftime("%H:%M"),
                            new_start=new_slot.start.strftime("%H:%M"),
                            new_end=new_slot.end.strftime("%H:%M"),
                            unit_name=existing.unit_name,
                            secretaria_name=existing.secretaria_name,
                            existing_period_start=(
                                existing.period_start.isoformat() if existing.period_start else None
                            ),
                            existing_period_end=existing.period_end.isoformat() if existing.period_end else None,
                            new_offer_type=candidate.offer_type,
                            new_offer_id=candidate.offer_id,
                            new_offer_name=candidate.offer_name,
                            frequency=new_slot.frequency,
                        )
                    )

        if not conflicts:
            return ScheduleValidationResult(
                has_conflict=False,
                blocking_mode=mode,
                message="Nenhum conflito de horário encontrado.",
            )

        msg = "Conflito de horário encontrado com outra matrícula ativa do aluno."
        if mode == "warn":
            msg = "Conflito de horário identificado. Revise antes de confirmar."
        elif mode == "allow":
            msg = "Conflito de horário identificado (modo apenas aviso)."

        return ScheduleValidationResult(
            has_conflict=True,
            blocking_mode=mode,
            message=msg,
            conflicts=conflicts,
            suggested_actions=[
                "Cancelar matrícula",
                "Selecionar outra turma/oferta",
                "Solicitar exceção com justificativa",
                "Visualizar agenda consolidada do aluno",
            ],
        )

    @classmethod
    def _resolve_setting(cls):
        from .models_schedule_conflicts import ScheduleConflictSetting

        return ScheduleConflictSetting.resolve()

    @classmethod
    def _load_existing_contexts(cls, *, aluno_id: int, exclude: dict) -> list[EnrollmentScheduleContext]:
        from .models import Matricula, MatriculaCurso, Turma
        from .models_informatica import InformaticaMatricula
        from .models_programas import ProgramaComplementarParticipacao

        contexts: list[EnrollmentScheduleContext] = []
        exclude_matricula_ids = set(exclude.get("matricula_ids") or [])
        exclude_matricula_curso_ids = set(exclude.get("matricula_curso_ids") or [])
        exclude_informatica_ids = set(exclude.get("informatica_matricula_ids") or [])
        exclude_programa_participacao_ids = set(exclude.get("programa_participacao_ids") or [])
        exclude_offer_keys = set(exclude.get("offer_keys") or [])

        regular_qs = Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
        ).prefetch_related("turma__grade_horario__aulas").filter(
            aluno_id=aluno_id,
            situacao=Matricula.Situacao.ATIVA,
        )
        if exclude_matricula_ids:
            regular_qs = regular_qs.exclude(id__in=exclude_matricula_ids)
        for item in regular_qs:
            context = cls._context_from_regular_matricula(item)
            if not context.slots:
                continue
            if (context.offer_type, context.offer_id) in exclude_offer_keys:
                continue
            contexts.append(context)

        curso_qs = MatriculaCurso.objects.select_related(
            "curso",
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
        ).prefetch_related("turma__grade_horario__aulas").filter(
            aluno_id=aluno_id,
            situacao__in=[MatriculaCurso.Situacao.MATRICULADO, MatriculaCurso.Situacao.EM_ANDAMENTO],
        )
        if exclude_matricula_curso_ids:
            curso_qs = curso_qs.exclude(id__in=exclude_matricula_curso_ids)
        for item in curso_qs:
            context = cls._context_from_course_matricula(item)
            if not context.slots:
                continue
            if (context.offer_type, context.offer_id) in exclude_offer_keys:
                continue
            contexts.append(context)

        info_qs = InformaticaMatricula.objects.select_related(
            "turma",
            "turma__curso",
            "turma__laboratorio",
            "turma__laboratorio__unidade",
            "turma__laboratorio__unidade__secretaria",
        ).prefetch_related("turma__encontros").filter(
            aluno_id=aluno_id,
            status__in=InformaticaMatricula.statuses_ativos(),
        )
        if exclude_informatica_ids:
            info_qs = info_qs.exclude(id__in=exclude_informatica_ids)
        for item in info_qs:
            context = cls._context_from_informatica_matricula(item)
            if not context.slots:
                continue
            if (context.offer_type, context.offer_id) in exclude_offer_keys:
                continue
            contexts.append(context)

        programa_qs = ProgramaComplementarParticipacao.objects.select_related(
            "programa",
            "oferta",
            "oferta__unidade",
            "oferta__unidade__secretaria",
        ).prefetch_related("oferta__horarios").filter(
            aluno_id=aluno_id,
            status__in=ProgramaComplementarParticipacao.statuses_ativos(),
        )
        if exclude_programa_participacao_ids:
            programa_qs = programa_qs.exclude(id__in=exclude_programa_participacao_ids)
        for item in programa_qs:
            context = cls._context_from_program_participacao(item)
            if not context.slots:
                continue
            if (context.offer_type, context.offer_id) in exclude_offer_keys:
                continue
            contexts.append(context)

        return contexts

    @classmethod
    def _context_from_regular_matricula(cls, matricula) -> EnrollmentScheduleContext:
        from .models import Turma

        turma = matricula.turma
        offer_type = (
            "ATIVIDADE_COMPLEMENTAR"
            if getattr(turma, "modalidade", "") == Turma.Modalidade.ATIVIDADE_COMPLEMENTAR
            else "TURMA"
        )
        return EnrollmentScheduleContext(
            module="EDUCACAO",
            enrollment_type="MATRICULA",
            enrollment_id=matricula.id,
            offer_type=offer_type,
            offer_id=turma.id,
            offer_name=turma.nome,
            status=matricula.situacao,
            unit_name=getattr(getattr(turma, "unidade", None), "nome", "") or "",
            secretaria_name=getattr(getattr(getattr(turma, "unidade", None), "secretaria", None), "nome", "") or "",
            period_start=matricula.data_matricula or cls._year_start(turma.ano_letivo),
            period_end=cls._year_end(turma.ano_letivo),
            allow_overlap=bool(getattr(turma, "permite_sobreposicao_horario", False)),
            slots=cls._slots_from_regular_turma(turma),
        )

    @classmethod
    def _context_from_course_matricula(cls, matricula_curso) -> EnrollmentScheduleContext:
        turma = getattr(matricula_curso, "turma", None)
        unit_name = getattr(getattr(turma, "unidade", None), "nome", "") if turma else ""
        secretaria_name = (
            getattr(getattr(getattr(turma, "unidade", None), "secretaria", None), "nome", "") if turma else ""
        )
        period_end = None
        if getattr(matricula_curso, "data_conclusao", None):
            period_end = matricula_curso.data_conclusao
        elif turma is not None:
            period_end = cls._year_end(turma.ano_letivo)
        return EnrollmentScheduleContext(
            module="EDUCACAO",
            enrollment_type="MATRICULA_CURSO",
            enrollment_id=matricula_curso.id,
            offer_type="CURSO",
            offer_id=getattr(matricula_curso, "curso_id", None),
            offer_name=getattr(getattr(matricula_curso, "curso", None), "nome", "Curso"),
            status=matricula_curso.situacao,
            unit_name=unit_name or "",
            secretaria_name=secretaria_name or "",
            period_start=matricula_curso.data_matricula,
            period_end=period_end,
            allow_overlap=bool(getattr(turma, "permite_sobreposicao_horario", False)),
            slots=cls._slots_from_regular_turma(turma) if turma else [],
        )

    @classmethod
    def _context_from_informatica_matricula(cls, matricula_info) -> EnrollmentScheduleContext:
        turma = matricula_info.turma
        unidade = getattr(getattr(turma, "laboratorio", None), "unidade", None)
        return EnrollmentScheduleContext(
            module="INFORMATICA",
            enrollment_type="INFORMATICA_MATRICULA",
            enrollment_id=matricula_info.id,
            offer_type="INFORMATICA_TURMA",
            offer_id=turma.id,
            offer_name=turma.codigo,
            status=matricula_info.status,
            unit_name=getattr(unidade, "nome", "") or "",
            secretaria_name=getattr(getattr(unidade, "secretaria", None), "nome", "") or "",
            period_start=matricula_info.data_matricula or cls._year_start(turma.ano_letivo),
            period_end=cls._year_end(turma.ano_letivo),
            allow_overlap=bool(getattr(turma, "permite_sobreposicao_horario", False)),
            slots=cls._slots_from_informatica_turma(turma),
        )

    @classmethod
    def _context_from_program_participacao(cls, participacao) -> EnrollmentScheduleContext:
        oferta = participacao.oferta
        unidade = getattr(oferta, "unidade", None)
        return EnrollmentScheduleContext(
            module="PROGRAMAS",
            enrollment_type="PROGRAMA_PARTICIPACAO",
            enrollment_id=participacao.id,
            offer_type="PROGRAMA_OFERTA",
            offer_id=oferta.id,
            offer_name=oferta.nome,
            status=participacao.status,
            unit_name=getattr(unidade, "nome", "") or "",
            secretaria_name=getattr(getattr(unidade, "secretaria", None), "nome", "") or "",
            period_start=participacao.data_ingresso or oferta.data_inicio or cls._year_start(oferta.ano_letivo),
            period_end=participacao.data_saida or oferta.data_fim or cls._year_end(oferta.ano_letivo),
            allow_overlap=bool(getattr(oferta, "permite_sobreposicao_horario", False)),
            slots=cls._slots_from_program_offer(oferta),
        )

    @classmethod
    def _candidate_from_regular_turma(
        cls,
        *,
        turma,
        data_inicio: date | None,
        slots_override: list[ScheduleSlot] | None = None,
    ) -> EnrollmentScheduleContext:
        from .models import Turma

        offer_type = (
            "ATIVIDADE_COMPLEMENTAR"
            if getattr(turma, "modalidade", "") == Turma.Modalidade.ATIVIDADE_COMPLEMENTAR
            else "TURMA"
        )
        return EnrollmentScheduleContext(
            module="EDUCACAO",
            enrollment_type="CANDIDATA",
            enrollment_id=None,
            offer_type=offer_type,
            offer_id=turma.id,
            offer_name=turma.nome,
            status="ATIVA",
            unit_name=getattr(getattr(turma, "unidade", None), "nome", "") or "",
            secretaria_name=getattr(getattr(getattr(turma, "unidade", None), "secretaria", None), "nome", "") or "",
            period_start=data_inicio or cls._year_start(turma.ano_letivo),
            period_end=cls._year_end(turma.ano_letivo),
            allow_overlap=bool(getattr(turma, "permite_sobreposicao_horario", False)),
            slots=slots_override if slots_override is not None else cls._slots_from_regular_turma(turma),
        )

    @classmethod
    def _candidate_from_course_offer(
        cls,
        *,
        curso,
        turma,
        data_inicio: date | None,
        data_fim: date | None,
    ) -> EnrollmentScheduleContext:
        period_end = data_fim
        if period_end is None and turma is not None:
            period_end = cls._year_end(turma.ano_letivo)
        return EnrollmentScheduleContext(
            module="EDUCACAO",
            enrollment_type="CANDIDATA_CURSO",
            enrollment_id=None,
            offer_type="CURSO",
            offer_id=getattr(curso, "id", None),
            offer_name=getattr(curso, "nome", "Curso"),
            status="ATIVA",
            unit_name=getattr(getattr(turma, "unidade", None), "nome", "") if turma else "",
            secretaria_name=(
                getattr(getattr(getattr(turma, "unidade", None), "secretaria", None), "nome", "") if turma else ""
            ),
            period_start=data_inicio,
            period_end=period_end,
            allow_overlap=bool(getattr(turma, "permite_sobreposicao_horario", False)) if turma else False,
            slots=cls._slots_from_regular_turma(turma) if turma else [],
        )

    @classmethod
    def _candidate_from_informatica_turma(
        cls,
        *,
        turma,
        data_inicio: date | None,
        slots_override: list[ScheduleSlot] | None = None,
    ) -> EnrollmentScheduleContext:
        unidade = getattr(getattr(turma, "laboratorio", None), "unidade", None)
        return EnrollmentScheduleContext(
            module="INFORMATICA",
            enrollment_type="CANDIDATA_INFORMATICA",
            enrollment_id=None,
            offer_type="INFORMATICA_TURMA",
            offer_id=turma.id,
            offer_name=turma.codigo,
            status="MATRICULADO",
            unit_name=getattr(unidade, "nome", "") or "",
            secretaria_name=getattr(getattr(unidade, "secretaria", None), "nome", "") or "",
            period_start=data_inicio or cls._year_start(turma.ano_letivo),
            period_end=cls._year_end(turma.ano_letivo),
            allow_overlap=bool(getattr(turma, "permite_sobreposicao_horario", False)),
            slots=slots_override if slots_override is not None else cls._slots_from_informatica_turma(turma),
        )

    @classmethod
    def _candidate_from_program_offer(
        cls,
        *,
        oferta,
        data_inicio: date | None,
    ) -> EnrollmentScheduleContext:
        unidade = getattr(oferta, "unidade", None)
        return EnrollmentScheduleContext(
            module="PROGRAMAS",
            enrollment_type="CANDIDATA_PROGRAMA",
            enrollment_id=None,
            offer_type="PROGRAMA_OFERTA",
            offer_id=oferta.id,
            offer_name=oferta.nome,
            status="ATIVO",
            unit_name=getattr(unidade, "nome", "") or "",
            secretaria_name=getattr(getattr(unidade, "secretaria", None), "nome", "") or "",
            period_start=data_inicio or oferta.data_inicio or cls._year_start(oferta.ano_letivo),
            period_end=oferta.data_fim or cls._year_end(oferta.ano_letivo),
            allow_overlap=bool(getattr(oferta, "permite_sobreposicao_horario", False)),
            slots=cls._slots_from_program_offer(oferta),
        )

    @classmethod
    def _slots_from_regular_turma(cls, turma) -> list[ScheduleSlot]:
        if turma is None:
            return []
        try:
            grade = turma.grade_horario
        except Exception:
            grade = None
        if grade is None:
            return []
        aulas = getattr(grade, "aulas", None)
        if aulas is None:
            return []
        slots: list[ScheduleSlot] = []
        for aula in aulas.all():
            weekday = _AULA_DIA_TO_WEEKDAY.get((getattr(aula, "dia", "") or "").upper())
            if weekday is None:
                continue
            if not getattr(aula, "inicio", None) or not getattr(aula, "fim", None):
                continue
            slots.append(
                ScheduleSlot(
                    weekday=weekday,
                    start=aula.inicio,
                    end=aula.fim,
                    frequency="SEMANAL",
                )
            )
        return slots

    @classmethod
    def _slots_from_informatica_turma(cls, turma) -> list[ScheduleSlot]:
        if turma is None:
            return []
        encontros = getattr(turma, "encontros", None)
        if encontros is None:
            return []
        slots: list[ScheduleSlot] = []
        for encontro in encontros.filter(ativo=True):
            if not getattr(encontro, "hora_inicio", None) or not getattr(encontro, "hora_fim", None):
                continue
            slots.append(
                ScheduleSlot(
                    weekday=int(encontro.dia_semana),
                    start=encontro.hora_inicio,
                    end=encontro.hora_fim,
                    frequency="SEMANAL",
                )
            )
        return slots

    @classmethod
    def _slots_from_program_offer(cls, oferta) -> list[ScheduleSlot]:
        if oferta is None:
            return []
        horarios = getattr(oferta, "horarios", None)
        if horarios is None:
            return []
        slots: list[ScheduleSlot] = []
        for horario in horarios.filter(ativo=True):
            if not getattr(horario, "hora_inicio", None) or not getattr(horario, "hora_fim", None):
                continue
            slots.append(
                ScheduleSlot(
                    weekday=int(horario.dia_semana),
                    start=horario.hora_inicio,
                    end=horario.hora_fim,
                    frequency=(getattr(horario, "frequencia_tipo", "SEMANAL") or "SEMANAL"),
                )
            )
        return slots

    @classmethod
    def _slots_from_informatica_grade(cls, grade) -> list[ScheduleSlot]:
        slots: list[ScheduleSlot] = []
        dias = [grade.dia_semana_1]
        if grade.dia_semana_2 is not None:
            dias.append(grade.dia_semana_2)
        for dia in dias:
            if dia is None:
                continue
            slots.append(
                ScheduleSlot(
                    weekday=int(dia),
                    start=grade.hora_inicio,
                    end=grade.hora_fim,
                    frequency="SEMANAL",
                )
            )
        return slots

    @staticmethod
    def _normalize_mode(raw_mode: str) -> str:
        mode = (raw_mode or "").strip().upper()
        if mode == "WARN":
            return "warn"
        if mode == "ALLOW":
            return "allow"
        return "block"

    @staticmethod
    def _times_overlap(
        start_a: time,
        end_a: time,
        start_b: time,
        end_b: time,
        *,
        allow_touching: bool,
    ) -> bool:
        if allow_touching:
            return start_a < end_b and end_a > start_b
        return start_a <= end_b and end_a >= start_b

    @staticmethod
    def _periods_overlap(
        start_a: date | None,
        end_a: date | None,
        start_b: date | None,
        end_b: date | None,
    ) -> bool:
        if start_a and end_b and start_a > end_b:
            return False
        if start_b and end_a and start_b > end_a:
            return False
        return True

    @staticmethod
    def _year_start(ano_letivo: int | None) -> date | None:
        if not ano_letivo:
            return None
        try:
            return date(int(ano_letivo), 1, 1)
        except Exception:
            return None

    @staticmethod
    def _year_end(ano_letivo: int | None) -> date | None:
        if not ano_letivo:
            return None
        try:
            return date(int(ano_letivo), 12, 31)
        except Exception:
            return None
