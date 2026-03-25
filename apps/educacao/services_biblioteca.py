from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .services_matricula_institucional import InstitutionalEnrollmentService


class LibraryLoanService:
    @staticmethod
    def find_student_by_identifier(identifier: str):
        from apps.accounts.models import Profile
        from .models import Aluno
        from .models_biblioteca import MatriculaInstitucional

        token = (identifier or "").strip()
        if not token:
            return None

        aluno = (
            Aluno.objects.select_related("matricula_institucional")
            .filter(matricula_institucional__numero_matricula__iexact=token)
            .first()
        )
        if aluno:
            return aluno

        profile = Profile.objects.select_related("aluno").filter(codigo_acesso__iexact=token, aluno__isnull=False).first()
        if profile and profile.aluno_id:
            return profile.aluno

        return (
            Aluno.objects.select_related("matricula_institucional")
            .filter(
                Q(nome__icontains=token)
                | Q(cpf__icontains=token)
                | Q(cpf_last4__iexact=token[-4:] if len(token) >= 4 else token)
            )
            .order_by("nome")
            .first()
        )

    @classmethod
    def create_loan(
        cls,
        *,
        biblioteca,
        aluno,
        exemplar,
        usuario=None,
        data_emprestimo=None,
        data_prevista_devolucao=None,
        observacoes: str = "",
    ):
        from .models_biblioteca import (
            BibliotecaBloqueio,
            BibliotecaEmprestimo,
            BibliotecaExemplar,
            BibliotecaReserva,
            MatriculaInstitucional,
        )

        if biblioteca.status != biblioteca.Status.ATIVA:
            raise ValueError("A biblioteca selecionada está inativa para operações.")

        if exemplar.livro.biblioteca_id != biblioteca.id:
            raise ValueError("O exemplar selecionado não pertence à biblioteca informada.")
        if exemplar.status != BibliotecaExemplar.Status.DISPONIVEL:
            raise ValueError("O exemplar selecionado não está disponível para empréstimo.")

        enrollment = InstitutionalEnrollmentService.resolve_active_for_student(aluno=aluno)
        if enrollment.status != MatriculaInstitucional.Status.ATIVA:
            raise ValueError("A matrícula institucional do aluno está inativa para empréstimo.")

        active_block = (
            BibliotecaBloqueio.objects.filter(
                aluno=aluno,
                status=BibliotecaBloqueio.Status.ATIVO,
            )
            .filter(Q(biblioteca__isnull=True) | Q(biblioteca=biblioteca))
            .filter(data_inicio__lte=timezone.localdate())
            .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=timezone.localdate()))
            .order_by("-id")
            .first()
        )
        if active_block:
            raise ValueError("O aluno possui bloqueio ativo na biblioteca.")

        active_loans_qs = BibliotecaEmprestimo.objects.filter(
            biblioteca=biblioteca,
            aluno=aluno,
            status__in=[BibliotecaEmprestimo.Status.ATIVO, BibliotecaEmprestimo.Status.RENOVADO, BibliotecaEmprestimo.Status.ATRASADO],
        )
        if active_loans_qs.count() >= int(biblioteca.limite_emprestimos_ativos):
            raise ValueError("O aluno atingiu o limite de empréstimos ativos para esta biblioteca.")

        overdue_exists = active_loans_qs.filter(data_prevista_devolucao__lt=timezone.localdate()).exists()
        if overdue_exists and not biblioteca.permitir_emprestimo_com_atraso:
            raise ValueError("O aluno possui empréstimos em atraso e está impedido de novo empréstimo.")

        active_reservation_by_other = BibliotecaReserva.objects.filter(
            biblioteca=biblioteca,
            status=BibliotecaReserva.Status.ATIVA,
        ).filter(
            Q(exemplar=exemplar) | Q(exemplar__isnull=True, livro=exemplar.livro)
        ).exclude(aluno=aluno)
        if active_reservation_by_other.filter(Q(data_expiracao__isnull=True) | Q(data_expiracao__gte=timezone.localdate())).exists():
            raise ValueError("Há reserva ativa para este exemplar/livro por outro aluno.")

        loan_date = data_emprestimo or timezone.localdate()
        due_date = data_prevista_devolucao or (loan_date + timedelta(days=int(biblioteca.dias_prazo_emprestimo)))
        if due_date <= loan_date:
            raise ValueError("A data prevista de devolução deve ser posterior à data do empréstimo.")

        with transaction.atomic():
            exemplar_locked = BibliotecaExemplar.objects.select_for_update().select_related("livro").get(pk=exemplar.pk)
            if exemplar_locked.status != BibliotecaExemplar.Status.DISPONIVEL:
                raise ValueError("O exemplar ficou indisponível durante a operação.")

            loan = BibliotecaEmprestimo.objects.create(
                biblioteca=biblioteca,
                aluno=aluno,
                matricula_institucional=enrollment,
                livro=exemplar_locked.livro,
                exemplar=exemplar_locked,
                data_emprestimo=loan_date,
                data_prevista_devolucao=due_date,
                status=BibliotecaEmprestimo.Status.ATIVO,
                observacoes=(observacoes or "").strip(),
                registrado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            )
            BibliotecaReserva.objects.filter(
                biblioteca=biblioteca,
                aluno=aluno,
                status=BibliotecaReserva.Status.ATIVA,
            ).filter(
                Q(exemplar=exemplar_locked) | Q(exemplar__isnull=True, livro=exemplar_locked.livro)
            ).filter(
                Q(data_expiracao__isnull=True) | Q(data_expiracao__gte=timezone.localdate())
            ).update(
                status=BibliotecaReserva.Status.ATENDIDA,
                atualizado_em=timezone.now(),
            )
            exemplar_locked.status = BibliotecaExemplar.Status.EMPRESTADO
            exemplar_locked.save(update_fields=["status", "atualizado_em"])
            return loan

    @classmethod
    def register_return(
        cls,
        *,
        emprestimo,
        usuario=None,
        data_devolucao=None,
        observacoes: str = "",
    ):
        from .models_biblioteca import BibliotecaEmprestimo, BibliotecaExemplar

        if emprestimo.status not in {
            BibliotecaEmprestimo.Status.ATIVO,
            BibliotecaEmprestimo.Status.RENOVADO,
            BibliotecaEmprestimo.Status.ATRASADO,
        }:
            raise ValueError("Somente empréstimos ativos podem ser devolvidos.")

        return_date = data_devolucao or timezone.localdate()
        with transaction.atomic():
            loan = BibliotecaEmprestimo.objects.select_for_update().select_related("exemplar").get(pk=emprestimo.pk)
            if loan.status not in {
                BibliotecaEmprestimo.Status.ATIVO,
                BibliotecaEmprestimo.Status.RENOVADO,
                BibliotecaEmprestimo.Status.ATRASADO,
            }:
                raise ValueError("O empréstimo já foi finalizado por outro operador.")

            loan.data_devolucao_real = return_date
            loan.status = BibliotecaEmprestimo.Status.DEVOLVIDO
            if observacoes:
                loan.observacoes = (loan.observacoes or "").strip()
                loan.observacoes = f"{loan.observacoes}\n{observacoes}".strip()
            loan.devolucao_registrada_por = usuario if getattr(usuario, "is_authenticated", False) else None
            loan.save(
                update_fields=[
                    "data_devolucao_real",
                    "status",
                    "observacoes",
                    "devolucao_registrada_por",
                    "atualizado_em",
                ]
            )

            exemplar = loan.exemplar
            exemplar.status = BibliotecaExemplar.Status.DISPONIVEL
            exemplar.save(update_fields=["status", "atualizado_em"])
            return loan

    @classmethod
    def renew_loan(
        cls,
        *,
        emprestimo,
        usuario=None,
        dias_adicionais: int = 7,
        observacoes: str = "",
    ):
        from .models_biblioteca import BibliotecaEmprestimo, BibliotecaReserva

        if emprestimo.status not in {
            BibliotecaEmprestimo.Status.ATIVO,
            BibliotecaEmprestimo.Status.RENOVADO,
            BibliotecaEmprestimo.Status.ATRASADO,
        }:
            raise ValueError("Somente empréstimos ativos podem ser renovados.")
        if dias_adicionais < 1:
            raise ValueError("Informe pelo menos 1 dia adicional para renovação.")

        with transaction.atomic():
            loan = BibliotecaEmprestimo.objects.select_for_update().get(pk=emprestimo.pk)
            if loan.status not in {
                BibliotecaEmprestimo.Status.ATIVO,
                BibliotecaEmprestimo.Status.RENOVADO,
                BibliotecaEmprestimo.Status.ATRASADO,
            }:
                raise ValueError("O empréstimo já foi finalizado por outro operador.")
            active_reservation_by_other = BibliotecaReserva.objects.filter(
                biblioteca=loan.biblioteca,
                status=BibliotecaReserva.Status.ATIVA,
            ).filter(
                Q(exemplar=loan.exemplar) | Q(exemplar__isnull=True, livro=loan.livro)
            ).exclude(aluno=loan.aluno)
            if active_reservation_by_other.filter(
                Q(data_expiracao__isnull=True) | Q(data_expiracao__gte=timezone.localdate())
            ).exists():
                raise ValueError("Não é possível renovar: existe reserva ativa deste item para outro aluno.")
            loan.data_prevista_devolucao = loan.data_prevista_devolucao + timedelta(days=int(dias_adicionais))
            loan.renovacoes = int(loan.renovacoes or 0) + 1
            loan.status = BibliotecaEmprestimo.Status.RENOVADO
            if observacoes:
                loan.observacoes = (loan.observacoes or "").strip()
                loan.observacoes = f"{loan.observacoes}\nRenovação: {observacoes}".strip()
            loan.save(update_fields=["data_prevista_devolucao", "renovacoes", "status", "observacoes", "atualizado_em"])
            return loan

    @classmethod
    def refresh_overdue_statuses(cls, *, biblioteca=None) -> int:
        from .models_biblioteca import BibliotecaEmprestimo

        qs = BibliotecaEmprestimo.objects.filter(
            status__in=[BibliotecaEmprestimo.Status.ATIVO, BibliotecaEmprestimo.Status.RENOVADO],
            data_prevista_devolucao__lt=timezone.localdate(),
        )
        if biblioteca is not None:
            qs = qs.filter(biblioteca=biblioteca)
        return qs.update(status=BibliotecaEmprestimo.Status.ATRASADO, atualizado_em=timezone.now())

    @classmethod
    def refresh_expired_reservations(cls, *, biblioteca=None) -> int:
        from .models_biblioteca import BibliotecaReserva

        qs = BibliotecaReserva.objects.filter(
            status=BibliotecaReserva.Status.ATIVA,
            data_expiracao__isnull=False,
            data_expiracao__lt=timezone.localdate(),
        )
        if biblioteca is not None:
            qs = qs.filter(biblioteca=biblioteca)
        return qs.update(status=BibliotecaReserva.Status.EXPIRADA, atualizado_em=timezone.now())

    @classmethod
    def create_reservation(
        cls,
        *,
        biblioteca,
        aluno,
        livro,
        exemplar=None,
        usuario=None,
        dias_validade: int = 3,
        observacoes: str = "",
    ):
        from .models_biblioteca import BibliotecaReserva

        if biblioteca.status != biblioteca.Status.ATIVA:
            raise ValueError("A biblioteca selecionada está inativa para reservas.")
        if livro.biblioteca_id != biblioteca.id:
            raise ValueError("O livro selecionado não pertence à biblioteca informada.")
        if exemplar and exemplar.livro_id != livro.id:
            raise ValueError("O exemplar informado não pertence ao livro informado.")

        enrollment = InstitutionalEnrollmentService.resolve_active_for_student(aluno=aluno)

        active_existing = BibliotecaReserva.objects.filter(
            biblioteca=biblioteca,
            aluno=aluno,
            livro=livro,
            status=BibliotecaReserva.Status.ATIVA,
        ).filter(
            Q(exemplar=exemplar) | Q(exemplar__isnull=True)
        ).filter(
            Q(data_expiracao__isnull=True) | Q(data_expiracao__gte=timezone.localdate())
        )
        if active_existing.exists():
            raise ValueError("Já existe reserva ativa desse aluno para o item informado.")

        data_reserva = timezone.localdate()
        data_expiracao = data_reserva + timedelta(days=max(1, int(dias_validade)))
        return BibliotecaReserva.objects.create(
            biblioteca=biblioteca,
            aluno=aluno,
            matricula_institucional=enrollment,
            livro=livro,
            exemplar=exemplar,
            data_reserva=data_reserva,
            data_expiracao=data_expiracao,
            status=BibliotecaReserva.Status.ATIVA,
            observacoes=(observacoes or "").strip(),
            criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )

    @classmethod
    def cancel_reservation(cls, *, reserva, usuario=None, motivo: str = ""):
        from .models_biblioteca import BibliotecaReserva

        if reserva.status != BibliotecaReserva.Status.ATIVA:
            raise ValueError("Somente reservas ativas podem ser canceladas.")
        reserva.status = BibliotecaReserva.Status.CANCELADA
        if motivo:
            reserva.observacoes = (reserva.observacoes or "").strip()
            reserva.observacoes = f"{reserva.observacoes}\nCancelamento: {motivo}".strip()
        reserva.save(update_fields=["status", "observacoes", "atualizado_em"])
        return reserva
