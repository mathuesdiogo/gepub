from __future__ import annotations

import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade

from .forms_biblioteca import (
    BibliotecaBloqueioForm,
    BibliotecaDevolucaoForm,
    BibliotecaEmprestimoCreateForm,
    BibliotecaReservaCancelForm,
    BibliotecaReservaCreateForm,
    BibliotecaRenovacaoForm,
    BibliotecaEscolarForm,
    BibliotecaExemplarForm,
    BibliotecaLivroForm,
)
from .models_biblioteca import (
    BibliotecaBloqueio,
    BibliotecaEmprestimo,
    BibliotecaEscolar,
    BibliotecaExemplar,
    BibliotecaLivro,
    BibliotecaReserva,
)
from .services_biblioteca import LibraryLoanService


def _bibliotecas_scope(user):
    unidades_ids = scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    ).values_list("id", flat=True)
    return BibliotecaEscolar.objects.select_related("unidade", "unidade__secretaria").filter(unidade_id__in=unidades_ids)


@login_required
@require_perm("educacao.view")
def biblioteca_dashboard(request):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    biblioteca_id = (request.GET.get("biblioteca") or "").strip()
    biblioteca = None
    if biblioteca_id:
        biblioteca = bibliotecas_qs.filter(pk=biblioteca_id).first()
    if biblioteca is None:
        biblioteca = bibliotecas_qs.order_by("nome").first()

    if biblioteca:
        LibraryLoanService.refresh_overdue_statuses(biblioteca=biblioteca)
        LibraryLoanService.refresh_expired_reservations(biblioteca=biblioteca)
        livros_qs = BibliotecaLivro.objects.filter(biblioteca=biblioteca)
        exemplares_qs = BibliotecaExemplar.objects.filter(livro__biblioteca=biblioteca)
        emprestimos_qs = BibliotecaEmprestimo.objects.filter(biblioteca=biblioteca)
        reservas_qs = BibliotecaReserva.objects.filter(biblioteca=biblioteca)
        bloqueios_ativos = BibliotecaBloqueio.objects.filter(
            status=BibliotecaBloqueio.Status.ATIVO,
        ).filter(Q(biblioteca=biblioteca) | Q(biblioteca__isnull=True))
    else:
        livros_qs = BibliotecaLivro.objects.none()
        exemplares_qs = BibliotecaExemplar.objects.none()
        emprestimos_qs = BibliotecaEmprestimo.objects.none()
        reservas_qs = BibliotecaReserva.objects.none()
        bloqueios_ativos = BibliotecaBloqueio.objects.none()

    context = {
        "title": "Biblioteca Escolar",
        "subtitle": "Gestão de acervo, empréstimos e devoluções vinculados à matrícula institucional.",
        "biblioteca": biblioteca,
        "bibliotecas": list(bibliotecas_qs.order_by("nome")[:30]),
        "kpis": {
            "livros_total": livros_qs.count(),
            "exemplares_disponiveis": exemplares_qs.filter(status=BibliotecaExemplar.Status.DISPONIVEL).count(),
            "emprestimos_ativos": emprestimos_qs.filter(
                status__in=[
                    BibliotecaEmprestimo.Status.ATIVO,
                    BibliotecaEmprestimo.Status.RENOVADO,
                    BibliotecaEmprestimo.Status.ATRASADO,
                ]
            ).count(),
            "emprestimos_atrasados": emprestimos_qs.filter(status=BibliotecaEmprestimo.Status.ATRASADO).count(),
            "reservas_ativas": reservas_qs.filter(status=BibliotecaReserva.Status.ATIVA).count(),
            "bloqueios_ativos": bloqueios_ativos.count(),
        },
        "ultimos_emprestimos": emprestimos_qs.select_related("aluno", "exemplar", "livro").order_by("-id")[:10],
        "reservas_pendentes": reservas_qs.select_related("aluno", "matricula_institucional", "livro", "exemplar")
        .filter(status=BibliotecaReserva.Status.ATIVA)
        .order_by("data_reserva", "id")[:10],
        "livros_populares": list(
            livros_qs.annotate(total_emprestimos=Count("emprestimos")).order_by("-total_emprestimos", "titulo")[:10]
        ),
        "alunos_destaque": list(
            emprestimos_qs.values("aluno_id", "aluno__nome", "matricula_institucional__numero_matricula")
            .annotate(total=Count("id"))
            .order_by("-total", "aluno__nome")[:10]
        ),
        "actions": [
            {
                "label": "Nova biblioteca",
                "url": reverse("educacao:biblioteca_create"),
                "icon": "fa-solid fa-building-columns",
                "variant": "gp-button--outline",
            },
            {
                "label": "Novo livro",
                "url": reverse("educacao:biblioteca_livro_create"),
                "icon": "fa-solid fa-book",
                "variant": "gp-button--outline",
            },
            {
                "label": "Novo exemplar",
                "url": reverse("educacao:biblioteca_exemplar_create"),
                "icon": "fa-solid fa-barcode",
                "variant": "gp-button--outline",
            },
            {
                "label": "Registrar empréstimo",
                "url": reverse("educacao:biblioteca_emprestimo_create"),
                "icon": "fa-solid fa-right-left",
                "variant": "gp-button--primary",
            },
            {
                "label": "Registrar reserva",
                "url": reverse("educacao:biblioteca_reserva_create"),
                "icon": "fa-solid fa-bookmark",
                "variant": "gp-button--outline",
            },
            {
                "label": "Relatórios",
                "url": reverse("educacao:biblioteca_relatorios"),
                "icon": "fa-solid fa-chart-line",
                "variant": "gp-button--outline",
            },
        ],
    }
    return render(request, "educacao/biblioteca/dashboard.html", context)


@login_required
@require_perm("educacao.manage")
def biblioteca_create(request):
    form = BibliotecaEscolarForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Biblioteca escolar cadastrada com sucesso.")
        return redirect("educacao:biblioteca_dashboard")
    return render(
        request,
        "educacao/biblioteca/form.html",
        {
            "title": "Nova biblioteca escolar",
            "subtitle": "Vincule a biblioteca a uma unidade da rede.",
            "form": form,
            "submit_label": "Salvar biblioteca",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_dashboard"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def biblioteca_livro_list(request):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    qs = BibliotecaLivro.objects.select_related("biblioteca", "biblioteca__unidade").filter(biblioteca__in=bibliotecas_qs)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q)
            | Q(autor__icontains=q)
            | Q(isbn__icontains=q)
            | Q(categoria__icontains=q)
        )
    context = {
        "title": "Acervo da biblioteca",
        "subtitle": "Livros cadastrados por unidade escolar.",
        "livros": qs.order_by("titulo")[:300],
        "q": q,
        "actions": [
            {
                "label": "Novo livro",
                "url": reverse("educacao:biblioteca_livro_create"),
                "icon": "fa-solid fa-plus",
                "variant": "gp-button--primary",
            },
            {
                "label": "Voltar",
                "url": reverse("educacao:biblioteca_dashboard"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "gp-button--ghost",
            },
        ],
    }
    return render(request, "educacao/biblioteca/livro_list.html", context)


@login_required
@require_perm("educacao.manage")
def biblioteca_livro_create(request):
    form = BibliotecaLivroForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Livro cadastrado no acervo com sucesso.")
        return redirect("educacao:biblioteca_livro_list")
    return render(
        request,
        "educacao/biblioteca/form.html",
        {
            "title": "Novo livro",
            "subtitle": "Cadastre os dados bibliográficos da obra.",
            "form": form,
            "submit_label": "Salvar livro",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_livro_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def biblioteca_exemplar_create(request):
    form = BibliotecaExemplarForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exemplar cadastrado com sucesso.")
        return redirect("educacao:biblioteca_livro_list")
    return render(
        request,
        "educacao/biblioteca/form.html",
        {
            "title": "Novo exemplar",
            "subtitle": "Registre o exemplar físico (tombo, localização e condição).",
            "form": form,
            "submit_label": "Salvar exemplar",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_livro_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def biblioteca_emprestimo_list(request):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    qs = (
        BibliotecaEmprestimo.objects.select_related(
            "biblioteca",
            "aluno",
            "matricula_institucional",
            "livro",
            "exemplar",
        )
        .filter(biblioteca__in=bibliotecas_qs)
        .order_by("-id")
    )
    status = (request.GET.get("status") or "").strip().upper()
    if status:
        qs = qs.filter(status=status)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(matricula_institucional__numero_matricula__icontains=q)
            | Q(exemplar__codigo_exemplar__icontains=q)
            | Q(livro__titulo__icontains=q)
        )
    context = {
        "title": "Empréstimos da biblioteca",
        "subtitle": "Acompanhe empréstimos ativos, devolvidos e atrasados.",
        "emprestimos": qs[:300],
        "status": status,
        "q": q,
        "actions": [
            {
                "label": "Registrar empréstimo",
                "url": reverse("educacao:biblioteca_emprestimo_create"),
                "icon": "fa-solid fa-right-left",
                "variant": "gp-button--primary",
            },
            {
                "label": "Reservas",
                "url": reverse("educacao:biblioteca_reserva_list"),
                "icon": "fa-solid fa-bookmark",
                "variant": "gp-button--outline",
            },
            {
                "label": "Relatórios",
                "url": reverse("educacao:biblioteca_relatorios"),
                "icon": "fa-solid fa-chart-line",
                "variant": "gp-button--outline",
            },
            {
                "label": "Voltar",
                "url": reverse("educacao:biblioteca_dashboard"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "gp-button--ghost",
            },
        ],
    }
    return render(request, "educacao/biblioteca/emprestimo_list.html", context)


@login_required
@require_perm("educacao.manage")
def biblioteca_emprestimo_create(request):
    form = BibliotecaEmprestimoCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            loan = LibraryLoanService.create_loan(
                biblioteca=form.cleaned_data["biblioteca"],
                aluno=form.aluno,
                exemplar=form.cleaned_data["exemplar"],
                usuario=request.user,
                data_emprestimo=form.cleaned_data.get("data_emprestimo"),
                data_prevista_devolucao=form.cleaned_data.get("data_prevista_devolucao"),
                observacoes=form.cleaned_data.get("observacoes") or "",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Empréstimo registrado para {loan.aluno.nome} ({loan.matricula_institucional.numero_matricula}).",
            )
            return redirect("educacao:biblioteca_emprestimo_list")
    return render(
        request,
        "educacao/biblioteca/form.html",
        {
            "title": "Registrar empréstimo",
            "subtitle": "Localize o aluno por matrícula/código de acesso e selecione o exemplar.",
            "form": form,
            "submit_label": "Confirmar empréstimo",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_emprestimo_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def biblioteca_emprestimo_devolver(request, pk: int):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    emprestimo = get_object_or_404(
        BibliotecaEmprestimo.objects.select_related("biblioteca", "aluno", "matricula_institucional", "livro", "exemplar"),
        pk=pk,
        biblioteca__in=bibliotecas_qs,
    )
    form = BibliotecaDevolucaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            LibraryLoanService.register_return(
                emprestimo=emprestimo,
                usuario=request.user,
                data_devolucao=form.cleaned_data["data_devolucao"],
                observacoes=form.cleaned_data.get("observacoes") or "",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Devolução registrada com sucesso.")
            return redirect("educacao:biblioteca_emprestimo_list")
    return render(
        request,
        "educacao/biblioteca/devolucao_form.html",
        {
            "title": "Registrar devolução",
            "subtitle": f"Aluno: {emprestimo.aluno.nome} • Matrícula: {emprestimo.matricula_institucional.numero_matricula}",
            "emprestimo": emprestimo,
            "form": form,
            "submit_label": "Confirmar devolução",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_emprestimo_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def biblioteca_emprestimo_renovar(request, pk: int):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    emprestimo = get_object_or_404(
        BibliotecaEmprestimo.objects.select_related("biblioteca", "aluno", "matricula_institucional", "livro", "exemplar"),
        pk=pk,
        biblioteca__in=bibliotecas_qs,
    )
    form = BibliotecaRenovacaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            LibraryLoanService.renew_loan(
                emprestimo=emprestimo,
                usuario=request.user,
                dias_adicionais=form.cleaned_data["dias_adicionais"],
                observacoes=form.cleaned_data.get("observacoes") or "",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Empréstimo renovado com sucesso.")
            return redirect("educacao:biblioteca_emprestimo_list")
    return render(
        request,
        "educacao/biblioteca/devolucao_form.html",
        {
            "title": "Renovar empréstimo",
            "subtitle": f"Aluno: {emprestimo.aluno.nome} • Matrícula: {emprestimo.matricula_institucional.numero_matricula}",
            "emprestimo": emprestimo,
            "form": form,
            "submit_label": "Confirmar renovação",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_emprestimo_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def biblioteca_reserva_list(request):
    LibraryLoanService.refresh_expired_reservations()
    bibliotecas_qs = _bibliotecas_scope(request.user)
    qs = (
        BibliotecaReserva.objects.select_related(
            "biblioteca",
            "aluno",
            "matricula_institucional",
            "livro",
            "exemplar",
        )
        .filter(biblioteca__in=bibliotecas_qs)
        .order_by("-id")
    )
    status = (request.GET.get("status") or "").strip().upper()
    if status:
        qs = qs.filter(status=status)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(matricula_institucional__numero_matricula__icontains=q)
            | Q(exemplar__codigo_exemplar__icontains=q)
            | Q(livro__titulo__icontains=q)
        )
    context = {
        "title": "Reservas da biblioteca",
        "subtitle": "Gerencie reservas ativas, atendidas, canceladas e expiradas.",
        "reservas": qs[:300],
        "status": status,
        "q": q,
        "actions": [
            {
                "label": "Nova reserva",
                "url": reverse("educacao:biblioteca_reserva_create"),
                "icon": "fa-solid fa-plus",
                "variant": "gp-button--primary",
            },
            {
                "label": "Empréstimos",
                "url": reverse("educacao:biblioteca_emprestimo_list"),
                "icon": "fa-solid fa-right-left",
                "variant": "gp-button--outline",
            },
            {
                "label": "Voltar",
                "url": reverse("educacao:biblioteca_dashboard"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "gp-button--ghost",
            },
        ],
    }
    return render(request, "educacao/biblioteca/reserva_list.html", context)


@login_required
@require_perm("educacao.manage")
def biblioteca_reserva_create(request):
    form = BibliotecaReservaCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            reserva = LibraryLoanService.create_reservation(
                biblioteca=form.cleaned_data["biblioteca"],
                aluno=form.aluno,
                livro=form.cleaned_data["livro"],
                exemplar=form.cleaned_data.get("exemplar"),
                usuario=request.user,
                dias_validade=form.cleaned_data["dias_validade"],
                observacoes=form.cleaned_data.get("observacoes") or "",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Reserva registrada para {reserva.aluno.nome} ({reserva.matricula_institucional.numero_matricula}).",
            )
            return redirect("educacao:biblioteca_reserva_list")
    return render(
        request,
        "educacao/biblioteca/form.html",
        {
            "title": "Registrar reserva",
            "subtitle": "Localize o aluno e selecione o livro (ou exemplar específico).",
            "form": form,
            "submit_label": "Confirmar reserva",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_reserva_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def biblioteca_reserva_cancel(request, pk: int):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    reserva = get_object_or_404(
        BibliotecaReserva.objects.select_related("biblioteca", "aluno", "matricula_institucional", "livro", "exemplar"),
        pk=pk,
        biblioteca__in=bibliotecas_qs,
    )
    form = BibliotecaReservaCancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            LibraryLoanService.cancel_reservation(
                reserva=reserva,
                usuario=request.user,
                motivo=form.cleaned_data.get("motivo") or "",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Reserva cancelada com sucesso.")
            return redirect("educacao:biblioteca_reserva_list")
    return render(
        request,
        "educacao/biblioteca/reserva_cancelar_form.html",
        {
            "title": "Cancelar reserva",
            "subtitle": f"Aluno: {reserva.aluno.nome} • Matrícula: {reserva.matricula_institucional.numero_matricula}",
            "reserva": reserva,
            "form": form,
            "submit_label": "Confirmar cancelamento",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_reserva_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def biblioteca_bloqueio_list(request):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    qs = BibliotecaBloqueio.objects.select_related("aluno", "matricula_institucional", "biblioteca").filter(
        Q(biblioteca__in=bibliotecas_qs) | Q(biblioteca__isnull=True)
    )
    context = {
        "title": "Bloqueios de biblioteca",
        "subtitle": "Controle de alunos com restrição para novos empréstimos.",
        "bloqueios": qs.order_by("-id")[:300],
        "actions": [
            {
                "label": "Novo bloqueio",
                "url": reverse("educacao:biblioteca_bloqueio_create"),
                "icon": "fa-solid fa-ban",
                "variant": "gp-button--primary",
            },
            {
                "label": "Relatórios",
                "url": reverse("educacao:biblioteca_relatorios"),
                "icon": "fa-solid fa-chart-line",
                "variant": "gp-button--outline",
            },
            {
                "label": "Voltar",
                "url": reverse("educacao:biblioteca_dashboard"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "gp-button--ghost",
            },
        ],
    }
    return render(request, "educacao/biblioteca/bloqueio_list.html", context)


@login_required
@require_perm("educacao.manage")
def biblioteca_bloqueio_create(request):
    form = BibliotecaBloqueioForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Bloqueio registrado com sucesso.")
        return redirect("educacao:biblioteca_bloqueio_list")
    return render(
        request,
        "educacao/biblioteca/form.html",
        {
            "title": "Novo bloqueio",
            "subtitle": "Registre bloqueios administrativos, atraso, perda ou dano.",
            "form": form,
            "submit_label": "Salvar bloqueio",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:biblioteca_bloqueio_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def biblioteca_relatorios(request):
    bibliotecas_qs = _bibliotecas_scope(request.user)
    biblioteca_id = (request.GET.get("biblioteca") or "").strip()
    tipo = (request.GET.get("tipo") or "ativos").strip().lower()
    export = (request.GET.get("export") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()

    emprestimos_qs = BibliotecaEmprestimo.objects.select_related(
        "biblioteca",
        "aluno",
        "matricula_institucional",
        "livro",
        "exemplar",
    ).filter(biblioteca__in=bibliotecas_qs)
    reservas_qs = BibliotecaReserva.objects.select_related(
        "biblioteca",
        "aluno",
        "matricula_institucional",
        "livro",
        "exemplar",
    ).filter(biblioteca__in=bibliotecas_qs)

    if biblioteca_id:
        emprestimos_qs = emprestimos_qs.filter(biblioteca_id=biblioteca_id)
        reservas_qs = reservas_qs.filter(biblioteca_id=biblioteca_id)
    if q:
        emprestimos_qs = emprestimos_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(matricula_institucional__numero_matricula__icontains=q)
            | Q(livro__titulo__icontains=q)
            | Q(exemplar__codigo_exemplar__icontains=q)
        )
        reservas_qs = reservas_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(matricula_institucional__numero_matricula__icontains=q)
            | Q(livro__titulo__icontains=q)
            | Q(exemplar__codigo_exemplar__icontains=q)
        )

    dataset_kind = "emprestimos"
    if tipo == "reservas":
        LibraryLoanService.refresh_expired_reservations()
        dataset_qs = reservas_qs.order_by("-data_reserva", "-id")
        dataset_kind = "reservas"
    elif tipo == "atrasados":
        dataset_qs = emprestimos_qs.filter(status=BibliotecaEmprestimo.Status.ATRASADO)
    elif tipo == "devolvidos":
        dataset_qs = emprestimos_qs.filter(status=BibliotecaEmprestimo.Status.DEVOLVIDO)
    elif tipo == "historico":
        dataset_qs = emprestimos_qs
    else:
        dataset_qs = emprestimos_qs.filter(
            status__in=[
                BibliotecaEmprestimo.Status.ATIVO,
                BibliotecaEmprestimo.Status.RENOVADO,
                BibliotecaEmprestimo.Status.ATRASADO,
            ]
        )

    if dataset_kind == "emprestimos":
        dataset_qs = dataset_qs.order_by("-data_emprestimo", "-id")

    if export == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="biblioteca_{tipo}.csv"'
        writer = csv.writer(response)
        if dataset_kind == "reservas":
            writer.writerow(
                [
                    "biblioteca",
                    "aluno",
                    "matricula",
                    "livro",
                    "exemplar",
                    "status",
                    "data_reserva",
                    "data_expiracao",
                ]
            )
            for item in dataset_qs[:5000]:
                writer.writerow(
                    [
                        item.biblioteca.nome,
                        item.aluno.nome,
                        item.matricula_institucional.numero_matricula,
                        item.livro.titulo,
                        item.exemplar.codigo_exemplar if item.exemplar else "",
                        item.get_status_display(),
                        item.data_reserva.strftime("%Y-%m-%d") if item.data_reserva else "",
                        item.data_expiracao.strftime("%Y-%m-%d") if item.data_expiracao else "",
                    ]
                )
        else:
            writer.writerow(
                [
                    "biblioteca",
                    "aluno",
                    "matricula",
                    "livro",
                    "exemplar",
                    "status",
                    "data_emprestimo",
                    "data_prevista_devolucao",
                    "data_devolucao_real",
                ]
            )
            for item in dataset_qs[:5000]:
                writer.writerow(
                    [
                        item.biblioteca.nome,
                        item.aluno.nome,
                        item.matricula_institucional.numero_matricula,
                        item.livro.titulo,
                        item.exemplar.codigo_exemplar,
                        item.get_status_display(),
                        item.data_emprestimo.strftime("%Y-%m-%d") if item.data_emprestimo else "",
                        item.data_prevista_devolucao.strftime("%Y-%m-%d") if item.data_prevista_devolucao else "",
                        item.data_devolucao_real.strftime("%Y-%m-%d") if item.data_devolucao_real else "",
                    ]
                )
        return response

    export_query = urlencode(
        {
            "tipo": tipo,
            "biblioteca": biblioteca_id or "",
            "q": q,
            "export": "csv",
        }
    )
    context = {
        "title": "Relatórios da Biblioteca",
        "subtitle": "Relatórios operacionais por status, aluno e acervo com exportação CSV.",
        "dataset": dataset_qs[:300],
        "dataset_kind": dataset_kind,
        "tipo": tipo,
        "q": q,
        "bibliotecas": list(bibliotecas_qs.order_by("nome")[:30]),
        "biblioteca_id": biblioteca_id,
        "actions": [
            {
                "label": "Exportar CSV",
                "url": f"{reverse('educacao:biblioteca_relatorios')}?{export_query}",
                "icon": "fa-solid fa-file-csv",
                "variant": "gp-button--outline",
            },
            {
                "label": "Voltar",
                "url": reverse("educacao:biblioteca_dashboard"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "gp-button--ghost",
            },
        ],
    }
    return render(request, "educacao/biblioteca/relatorios.html", context)
