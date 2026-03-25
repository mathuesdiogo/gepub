from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.educacao.models_informatica import InformaticaMatricula, InformaticaTurma
from apps.educacao.services_programas import ProgramasComplementaresService


class Command(BaseCommand):
    help = (
        "Sincroniza dados legados do módulo de Informática com o núcleo de "
        "Programas Complementares (ofertas, horários e participações)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Inclui matrículas canceladas/concluídas. Por padrão sincroniza status ativos e pendentes.",
        )

    def handle(self, *args, **options):
        include_all = bool(options.get("all"))

        turmas_qs = InformaticaTurma.objects.select_related("curso", "laboratorio", "laboratorio__unidade")
        matriculas_qs = InformaticaMatricula.objects.select_related(
            "aluno",
            "turma",
            "turma__curso",
            "turma__laboratorio",
            "turma__laboratorio__unidade",
            "escola_origem",
        )
        if not include_all:
            matriculas_qs = matriculas_qs.filter(
                status__in=[
                    InformaticaMatricula.Status.PENDENTE,
                    InformaticaMatricula.Status.APROVADA,
                    InformaticaMatricula.Status.MATRICULADO,
                    InformaticaMatricula.Status.LISTA_ESPERA,
                ]
            )

        turmas_sync = 0
        participacoes_sync = 0
        errors = 0

        for turma in turmas_qs.iterator():
            try:
                ProgramasComplementaresService.sync_informatica_offer_schedule(turma=turma)
                turmas_sync += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(self.style.ERROR(f"[TURMA {turma.id}] {exc}"))

        for matricula in matriculas_qs.iterator():
            try:
                ProgramasComplementaresService.sync_informatica_matricula(matricula=matricula, usuario=matricula.criado_por)
                participacoes_sync += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(self.style.ERROR(f"[MATRICULA {matricula.id}] {exc}"))

        self.stdout.write(self.style.SUCCESS("Sincronização de programas complementares finalizada."))
        self.stdout.write(
            f"Turmas processadas: {turmas_sync} | Matrículas processadas: {participacoes_sync} | Erros: {errors}"
        )
