from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can, scope_filter_alunos, scope_filter_matriculas, scope_filter_turmas
from apps.nee.forms import AlunoNecessidadeForm, ApoioMatriculaForm
from apps.nee.models import AlunoNecessidade, ApoioMatricula

from .forms import AlunoCertificadoForm, AlunoDocumentoForm, MatriculaCursoForm, MatriculaForm
from .models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    CarteiraEstudantil,
    Matricula,
    MatriculaCurso,
    MatriculaMovimentacao,
    Turma,
)
from .services_matricula import (
    aplicar_movimentacao_matricula,
    desfazer_movimentacao_matricula,
    desfazer_ultima_movimentacao_matricula,
    registrar_movimentacao,
)
from .services_requisitos import (
    avaliar_requisitos_matricula,
    registrar_override_requisitos_matricula,
)


def _municipio_id_from_turma(turma: Turma | None) -> int | None:
    if turma is None:
        return None
    unidade = getattr(turma, "unidade", None)
    secretaria = getattr(unidade, "secretaria", None)
    return getattr(secretaria, "municipio_id", None)


class MatriculaMovimentacaoForm(forms.Form):
    matricula = forms.ModelChoiceField(queryset=Matricula.objects.none(), label="Matrícula")
    tipo = forms.ChoiceField(
        label="Tipo de movimentação",
        choices=[
            (MatriculaMovimentacao.Tipo.REMANEJAMENTO, "Remanejamento de turma"),
            (MatriculaMovimentacao.Tipo.TRANSFERENCIA, "Transferência"),
            (MatriculaMovimentacao.Tipo.CANCELAMENTO, "Cancelamento"),
            (MatriculaMovimentacao.Tipo.TRANCAMENTO, "Trancamento"),
            (MatriculaMovimentacao.Tipo.REATIVACAO, "Reativação"),
            (MatriculaMovimentacao.Tipo.DESFAZER, "Desfazer último procedimento"),
        ],
    )
    turma_destino = forms.ModelChoiceField(
        queryset=Turma.objects.none(),
        label="Turma de destino",
        required=False,
    )
    motivo = forms.CharField(
        label="Motivo",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    data_referencia = forms.DateField(
        label="Data do procedimento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    tipo_trancamento = forms.ChoiceField(
        label="Tipo de trancamento",
        required=False,
        choices=[("", "Selecione")] + list(MatriculaMovimentacao.TipoTrancamento.choices),
    )
    override_requisitos = forms.BooleanField(
        label="Forçar movimentação ignorando pré-requisitos",
        required=False,
    )
    override_justificativa = forms.CharField(
        label="Justificativa do override",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, aluno: Aluno, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aluno = aluno
        self.user = user

        self.fields["matricula"].queryset = (
            Matricula.objects.select_related("turma", "turma__unidade")
            .filter(aluno=aluno)
            .order_by("-id")
        )

        turma_qs = scope_filter_turmas(
            user,
            Turma.objects.select_related("unidade", "unidade__secretaria").filter(ativo=True),
        ).order_by("-ano_letivo", "nome")
        self.fields["turma_destino"].queryset = turma_qs
        can_override = bool(can(user, "educacao.manage"))
        if not can_override:
            self.fields["override_requisitos"].widget = forms.HiddenInput()
            self.fields["override_justificativa"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        matricula = cleaned.get("matricula")
        tipo = cleaned.get("tipo")
        turma_destino = cleaned.get("turma_destino")
        wants_override = bool(cleaned.get("override_requisitos"))
        justificativa = (cleaned.get("override_justificativa") or "").strip()

        if not matricula:
            return cleaned

        if tipo in {
            MatriculaMovimentacao.Tipo.REMANEJAMENTO,
            MatriculaMovimentacao.Tipo.TRANSFERENCIA,
        }:
            if not turma_destino:
                self.add_error("turma_destino", "Selecione a turma de destino.")
            elif turma_destino == matricula.turma:
                self.add_error("turma_destino", "A turma de destino deve ser diferente da turma atual.")
            else:
                municipio_origem = _municipio_id_from_turma(matricula.turma)
                municipio_destino = _municipio_id_from_turma(turma_destino)
                if municipio_origem and municipio_destino and municipio_origem != municipio_destino:
                    self.add_error(
                        "turma_destino",
                        "Transferências/remanejamentos internos exigem turma no mesmo município.",
                    )

        if wants_override and not justificativa:
            self.add_error("override_justificativa", "Informe a justificativa para registrar o override.")
        if not wants_override:
            cleaned["override_justificativa"] = ""
        if tipo == MatriculaMovimentacao.Tipo.TRANCAMENTO and not cleaned.get("tipo_trancamento"):
            self.add_error("tipo_trancamento", "Informe o tipo de trancamento.")
        if tipo == MatriculaMovimentacao.Tipo.TRANCAMENTO and not cleaned.get("data_referencia"):
            self.add_error("data_referencia", "Informe a data do trancamento.")
        if tipo != MatriculaMovimentacao.Tipo.TRANCAMENTO:
            cleaned["tipo_trancamento"] = ""
        if tipo == MatriculaMovimentacao.Tipo.DESFAZER:
            cleaned["turma_destino"] = None
            cleaned["tipo_trancamento"] = ""

        return cleaned


def aluno_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = Aluno.objects.only("id", "nome", "cpf", "nis", "nome_mae", "ativo")

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        )

    qs = scope_filter_alunos(request.user, qs)

    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(qs.order_by("nome").values_list("nome", "cpf", "nis", "ativo"))
        headers_export = ["Nome", "CPF", "NIS", "Ativo"]
        rows_export = [[nome or "", cpf or "", nis or "", "Sim" if ativo else "Não"] for (nome, cpf, nis, ativo) in items]

        if export == "csv":
            return export_csv("alunos.csv", headers_export, rows_export)

        filtros = f"Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="alunos.pdf",
            title="Relatório — Alunos",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_edu_manage = can(request.user, "educacao.manage")

    base_q = f"q={escape(q)}" if q else ""
    actions = [
        {"label": "Exportar CSV", "url": f"?{base_q + ('&' if base_q else '')}export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": f"?{base_q + ('&' if base_q else '')}export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_edu_manage:
        actions.append({"label": "Novo Aluno", "url": reverse("educacao:aluno_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Nome"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
        {"label": "Ativo", "width": "140px"},
    ]

    rows = []
    for a in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                    {"text": a.cpf or "—"},
                    {"text": a.nis or "—"},
                    {"text": "Sim" if a.ativo else "Não"},
                ],
                "can_edit": bool(can_edu_manage and a.pk),
                "edit_url": reverse("educacao:aluno_update", args=[a.pk]) if a.pk else "",
            }
        )

    return render(
        request,
        "educacao/aluno_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("educacao:aluno_list"),
            "clear_url": reverse("educacao:aluno_list"),
            "autocomplete_url": reverse("educacao:api_alunos_suggest"),
            "autocomplete_href": reverse("educacao:aluno_list") + "?q={q}",
        },
    )


def aluno_detail(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    try:
        aluno = get_object_or_404(aluno_qs, pk=pk)
    except Http404:
        recent = request.session.get("recent_alunos", [])
        if pk in recent and can(request.user, "educacao.manage"):
            aluno = get_object_or_404(Aluno.objects.all(), pk=pk)
            if Matricula.objects.filter(aluno=aluno).exists():
                raise
        else:
            raise

    can_edu_manage = can(request.user, "educacao.manage")
    can_nee_manage = can(request.user, "nee.manage") or can_edu_manage

    matriculas_qs = (
        Matricula.objects.select_related(
            "aluno",
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno=aluno)
        .order_by("-id")
    )
    matriculas_qs = scope_filter_matriculas(request.user, matriculas_qs)
    matriculas = matriculas_qs

    necessidades = AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno).order_by("-id")

    apoios_qs = (
        ApoioMatricula.objects.select_related(
            "matricula",
            "matricula__turma",
            "matricula__turma__unidade",
            "matricula__turma__unidade__secretaria",
            "matricula__turma__unidade__secretaria__municipio",
        )
        .filter(matricula__aluno=aluno)
        .order_by("-id")
    )

    allowed_matriculas = scope_filter_matriculas(request.user, Matricula.objects.filter(aluno=aluno)).values_list("id", flat=True)

    apoios = apoios_qs.filter(matricula_id__in=allowed_matriculas)
    documentos = AlunoDocumento.objects.filter(aluno=aluno).order_by("-criado_em", "-id")
    certificados = AlunoCertificado.objects.select_related("matricula", "curso").filter(aluno=aluno).order_by(
        "-data_emissao", "-id"
    )
    carteiras_estudantis = CarteiraEstudantil.objects.filter(aluno=aluno).order_by("-emitida_em", "-id")
    matriculas_cursos = MatriculaCurso.objects.select_related("curso", "turma", "turma__unidade").filter(
        aluno=aluno
    ).order_by("-data_matricula", "-id")
    movimentacoes_qs = (
        MatriculaMovimentacao.objects.select_related("usuario", "turma_origem", "turma_destino", "matricula")
        .filter(aluno=aluno)
        .order_by("-criado_em", "-id")[:50]
    )

    atendimentos_saude = []
    agendamentos_saude = []
    beneficios_entregas = []
    beneficios_inscricoes = []
    try:
        from apps.saude.models import AtendimentoSaude, AgendamentoSaude

        atendimentos_saude = list(
            AtendimentoSaude.objects.select_related("profissional", "unidade")
            .filter(aluno=aluno)
            .order_by("-data", "-id")[:10]
        )
        agendamentos_saude = list(
            AgendamentoSaude.objects.select_related("profissional", "unidade")
            .filter(aluno=aluno)
            .order_by("-inicio", "-id")[:10]
        )
    except Exception:
        atendimentos_saude = []
        agendamentos_saude = []

    try:
        from .models_beneficios import BeneficioEntrega, BeneficioEditalInscricao

        beneficios_entregas = list(
            BeneficioEntrega.objects.select_related("beneficio", "campanha")
            .filter(aluno=aluno)
            .order_by("-data_hora", "-id")[:12]
        )
        beneficios_inscricoes = list(
            BeneficioEditalInscricao.objects.select_related("edital")
            .filter(aluno=aluno)
            .order_by("-data_hora", "-id")[:10]
        )
    except Exception:
        beneficios_entregas = []
        beneficios_inscricoes = []

    form_matricula = MatriculaForm(user=request.user)
    form_nee = AlunoNecessidadeForm(aluno=aluno)
    form_apoio = ApoioMatriculaForm(aluno=aluno)
    form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
    form_documento = AlunoDocumentoForm()
    form_certificado = AlunoCertificadoForm(aluno=aluno)
    form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        if action in {
            "add_matricula",
            "add_nee",
            "add_apoio",
            "mov_matricula",
            "undo_mov_matricula",
            "add_documento",
            "add_certificado",
            "add_matricula_curso",
        } and not can_edu_manage:
            return HttpResponseForbidden("403 — Você não tem permissão para alterar dados de Educação.")

        if action == "add_matricula":
            form_matricula = MatriculaForm(request.POST, user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            if form_matricula.is_valid():
                m = form_matricula.save(commit=False)
                m.aluno = aluno

                turma_ok = scope_filter_turmas(request.user, Turma.objects.filter(pk=m.turma_id)).exists()
                if not turma_ok:
                    return HttpResponseForbidden("403 — Turma fora do seu escopo.")

                avaliacao_requisitos = avaliar_requisitos_matricula(aluno=aluno, turma=m.turma)
                if avaliacao_requisitos.bloqueado:
                    wants_override = bool(form_matricula.cleaned_data.get("override_requisitos"))
                    justificativa = (form_matricula.cleaned_data.get("override_justificativa") or "").strip()
                    if wants_override and justificativa:
                        registrar_override_requisitos_matricula(
                            usuario=request.user,
                            aluno=aluno,
                            turma=m.turma,
                            justificativa=justificativa,
                            pendencias=avaliacao_requisitos.pendencias,
                            origem="ALUNO_DETAIL_MATRICULA",
                        )
                        messages.warning(request, "Matrícula liberada por override com auditoria.")
                    else:
                        for pendencia in avaliacao_requisitos.pendencias:
                            messages.error(request, pendencia)
                        return redirect("educacao:aluno_detail", pk=aluno.pk)
                for aviso in avaliacao_requisitos.avisos:
                    messages.warning(request, aviso)

                if not m.data_matricula:
                    m.data_matricula = timezone.localdate()

                m.save()
                registrar_movimentacao(
                    matricula=m,
                    tipo=MatriculaMovimentacao.Tipo.CRIACAO,
                    usuario=request.user,
                    turma_destino=m.turma,
                    situacao_nova=m.situacao,
                    motivo="Matrícula criada pelo detalhe do aluno.",
                )
                messages.success(request, "Matrícula adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da matrícula.")

        elif action == "add_nee":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            if form_nee.is_valid():
                nee = form_nee.save(commit=False)
                nee.aluno = aluno
                nee.save()
                messages.success(request, "Necessidade adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da necessidade.")

        elif action == "add_apoio":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(request.POST, aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            if form_apoio.is_valid():
                apoio = form_apoio.save(commit=False)

                matricula_ok = scope_filter_matriculas(
                    request.user,
                    Matricula.objects.filter(pk=apoio.matricula_id, aluno=aluno),
                ).exists()
                if not matricula_ok:
                    return HttpResponseForbidden("403 — Matrícula fora do seu escopo.")

                apoio.save()
                messages.success(request, "Apoio adicionado com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros do apoio.")

        elif action == "undo_mov_matricula":
            try:
                movimentacao_id = int(request.POST.get("movimentacao_id") or 0)
            except (TypeError, ValueError):
                movimentacao_id = 0
            try:
                matricula_id = int(request.POST.get("matricula_id") or 0)
            except (TypeError, ValueError):
                matricula_id = 0
            motivo = (request.POST.get("motivo") or "").strip()

            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            matricula_undo = Matricula.objects.filter(aluno=aluno, pk=matricula_id).first()
            if movimentacao_id <= 0 or matricula_undo is None:
                messages.error(request, "Não foi possível localizar o procedimento para desfazer.")
            else:
                try:
                    desfazer_movimentacao_matricula(
                        matricula=matricula_undo,
                        usuario=request.user,
                        motivo=motivo,
                        movimentacao_id=movimentacao_id,
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "Procedimento desfeito com sucesso.")
                    return redirect("educacao:aluno_detail", pk=aluno.pk)

        elif action == "mov_matricula":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user, request.POST)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            if form_movimentacao.is_valid():
                matricula = form_movimentacao.cleaned_data["matricula"]
                tipo = form_movimentacao.cleaned_data["tipo"]
                turma_destino = form_movimentacao.cleaned_data.get("turma_destino")
                motivo = form_movimentacao.cleaned_data.get("motivo") or ""
                data_referencia = form_movimentacao.cleaned_data.get("data_referencia")
                tipo_trancamento = form_movimentacao.cleaned_data.get("tipo_trancamento") or ""
                if tipo in {
                    MatriculaMovimentacao.Tipo.REMANEJAMENTO,
                    MatriculaMovimentacao.Tipo.TRANSFERENCIA,
                } and turma_destino:
                    avaliacao_requisitos = avaliar_requisitos_matricula(aluno=aluno, turma=turma_destino)
                    wants_override = bool(form_movimentacao.cleaned_data.get("override_requisitos"))
                    justificativa = (form_movimentacao.cleaned_data.get("override_justificativa") or "").strip()
                    if avaliacao_requisitos.bloqueado:
                        if wants_override and justificativa:
                            registrar_override_requisitos_matricula(
                                usuario=request.user,
                                aluno=aluno,
                                turma=turma_destino,
                                justificativa=justificativa,
                                pendencias=avaliacao_requisitos.pendencias,
                                origem=f"ALUNO_DETAIL_{tipo}",
                            )
                            messages.warning(request, "Movimentação liberada por override com auditoria.")
                        else:
                            for pendencia in avaliacao_requisitos.pendencias:
                                form_movimentacao.add_error("turma_destino", pendencia)
                            messages.error(request, "Movimentação bloqueada por pré-requisito.")
                            turma_destino = None
                    else:
                        for aviso in avaliacao_requisitos.avisos:
                            messages.warning(request, aviso)

                if tipo == MatriculaMovimentacao.Tipo.DESFAZER:
                    try:
                        desfazer_ultima_movimentacao_matricula(
                            matricula=matricula,
                            usuario=request.user,
                            motivo=motivo,
                        )
                    except ValueError as exc:
                        form_movimentacao.add_error(None, str(exc))
                        messages.error(request, str(exc))
                    else:
                        messages.success(request, "Último procedimento desfeito com sucesso.")
                        return redirect("educacao:aluno_detail", pk=aluno.pk)
                elif tipo in {
                    MatriculaMovimentacao.Tipo.REMANEJAMENTO,
                    MatriculaMovimentacao.Tipo.TRANSFERENCIA,
                    MatriculaMovimentacao.Tipo.CANCELAMENTO,
                    MatriculaMovimentacao.Tipo.TRANCAMENTO,
                    MatriculaMovimentacao.Tipo.REATIVACAO,
                }:
                    try:
                        aplicar_movimentacao_matricula(
                            matricula=matricula,
                            tipo=tipo,
                            usuario=request.user,
                            turma_destino=turma_destino,
                            data_referencia=data_referencia,
                            tipo_trancamento=tipo_trancamento,
                            motivo=motivo,
                        )
                    except ValueError as exc:
                        form_movimentacao.add_error("turma_destino", str(exc))
                        messages.error(request, str(exc))
                    else:
                        messages_map = {
                            MatriculaMovimentacao.Tipo.REMANEJAMENTO: "Remanejamento realizado com sucesso.",
                            MatriculaMovimentacao.Tipo.TRANSFERENCIA: "Transferência realizada com sucesso.",
                            MatriculaMovimentacao.Tipo.CANCELAMENTO: "Matrícula cancelada com sucesso.",
                            MatriculaMovimentacao.Tipo.TRANCAMENTO: "Matrícula trancada com sucesso.",
                            MatriculaMovimentacao.Tipo.REATIVACAO: "Matrícula reativada com sucesso.",
                        }
                        messages.success(request, messages_map.get(tipo, "Movimentação realizada com sucesso."))
                        return redirect("educacao:aluno_detail", pk=aluno.pk)
                else:
                    messages.error(request, "Não foi possível concluir a movimentação informada.")

            else:
                messages.error(request, "Corrija os erros da movimentação.")

        elif action == "add_documento":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm(request.POST, request.FILES)
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            if form_documento.is_valid():
                documento = form_documento.save(commit=False)
                documento.aluno = aluno
                documento.enviado_por = request.user
                documento.save()
                messages.success(request, "Documento do aluno adicionado com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros do documento.")

        elif action == "add_certificado":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(request.POST, request.FILES, aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(user=request.user, aluno=aluno)

            if form_certificado.is_valid():
                certificado = form_certificado.save(commit=False)
                certificado.aluno = aluno
                certificado.emitido_por = request.user
                if certificado.matricula_id and not certificado.curso_id:
                    curso_turma = getattr(getattr(certificado.matricula, "turma", None), "curso", None)
                    if curso_turma:
                        certificado.curso = curso_turma
                certificado.save()
                messages.success(
                    request,
                    f"Certificado registrado com sucesso. Código: {certificado.codigo_verificacao}",
                )
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros do certificado.")

        elif action == "add_matricula_curso":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user)
            form_documento = AlunoDocumentoForm()
            form_certificado = AlunoCertificadoForm(aluno=aluno)
            form_matricula_curso = MatriculaCursoForm(request.POST, user=request.user, aluno=aluno)

            if form_matricula_curso.is_valid():
                matricula_curso = form_matricula_curso.save(commit=False)
                matricula_curso.aluno = aluno
                matricula_curso.cadastrado_por = request.user
                matricula_curso.save()
                messages.success(request, "Aluno matriculado na atividade extracurricular com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da matrícula em atividade extracurricular.")

    else:
        pass

    fields = [
        {"label": "CPF", "value": aluno.cpf or "—"},
        {"label": "NIS", "value": aluno.nis or "—"},
        {"label": "Nascimento", "value": aluno.data_nascimento.strftime("%d/%m/%Y") if aluno.data_nascimento else "—"},
        {"label": "Mãe", "value": aluno.nome_mae or "—"},
        {"label": "Pai", "value": aluno.nome_pai or "—"},
        {"label": "Telefone", "value": aluno.telefone or "—"},
        {"label": "E-mail", "value": aluno.email or "—"},
        {"label": "Endereço", "value": aluno.endereco or "—"},
    ]

    pills = [{"label": "Status", "value": "Ativo" if aluno.ativo else "Inativo", "variant": "success" if aluno.ativo else "danger"}]
    pills.append({"label": "Documentos", "value": str(documentos.count())})
    pills.append({"label": "Certificados", "value": str(certificados.count())})
    pills.append({"label": "Carteiras", "value": str(carteiras_estudantis.count())})
    pills.append({"label": "Atividades extras", "value": str(matriculas_cursos.count())})
    pills.append({"label": "Benefícios", "value": str(len(beneficios_entregas))})

    headers_matriculas = [
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Ano", "width": "120px"},
        {"label": "Situação", "width": "140px"},
        {"label": "Data", "width": "140px"},
    ]

    rows_matriculas = []
    for m in matriculas:
        rows_matriculas.append(
            {
                "cells": [
                    {"text": m.turma.nome, "url": reverse("educacao:turma_detail", args=[m.turma.pk])},
                    {"text": m.turma.unidade.nome},
                    {"text": str(m.turma.ano_letivo)},
                    {"text": m.get_situacao_display()},
                    {"text": m.data_matricula.strftime("%d/%m/%Y") if m.data_matricula else "—"},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    headers_movimentacoes = [
        {"label": "Data/Hora", "width": "160px"},
        {"label": "Tipo", "width": "150px"},
        {"label": "Matrícula", "width": "90px"},
        {"label": "Origem"},
        {"label": "Destino"},
        {"label": "Situação"},
        {"label": "Referência", "width": "180px"},
        {"label": "Usuário", "width": "180px"},
        {"label": "Motivo"},
    ]
    latest_mov_por_matricula: dict[int, int] = {}
    for _mov in (
        MatriculaMovimentacao.objects.filter(aluno=aluno)
        .exclude(tipo=MatriculaMovimentacao.Tipo.CRIACAO)
        .exclude(tipo=MatriculaMovimentacao.Tipo.DESFAZER)
        .order_by("matricula_id", "-criado_em", "-id")
    ):
        latest_mov_por_matricula.setdefault(_mov.matricula_id, _mov.id)

    rows_movimentacoes = []
    for mov in movimentacoes_qs:
        referencia = []
        if mov.data_referencia:
            referencia.append(mov.data_referencia.strftime("%d/%m/%Y"))
        if mov.tipo_trancamento:
            referencia.append(mov.get_tipo_trancamento_display())
        if mov.movimentacao_desfeita_id:
            referencia.append(f"Desfez #{mov.movimentacao_desfeita_id}")
        referencia_txt = " • ".join(referencia) if referencia else "—"
        can_undo = (
            can_edu_manage
            and mov.tipo
            in {
                MatriculaMovimentacao.Tipo.REMANEJAMENTO,
                MatriculaMovimentacao.Tipo.CANCELAMENTO,
                MatriculaMovimentacao.Tipo.TRANCAMENTO,
                MatriculaMovimentacao.Tipo.REATIVACAO,
                MatriculaMovimentacao.Tipo.SITUACAO,
            }
            and latest_mov_por_matricula.get(mov.matricula_id) == mov.id
        )
        rows_movimentacoes.append(
            {
                "cells": [
                    {"text": mov.criado_em.strftime("%d/%m/%Y %H:%M")},
                    {"text": mov.get_tipo_display()},
                    {"text": str(mov.matricula_id)},
                    {"text": getattr(mov.turma_origem, "nome", "—")},
                    {"text": getattr(mov.turma_destino, "nome", "—")},
                    {"text": f"{mov.situacao_anterior or '—'} → {mov.situacao_nova or '—'}"},
                    {"text": referencia_txt},
                    {"text": getattr(getattr(mov, "usuario", None), "username", "—")},
                    {"text": mov.motivo or "—"},
                ],
                "movimentacao_id": mov.id,
                "matricula_id": mov.matricula_id,
                "can_undo": can_undo,
                "can_edit": False,
                "edit_url": "",
            }
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:aluno_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Meus dados do aluno", "url": reverse("educacao:aluno_meus_dados", args=[aluno.pk]), "icon": "fa-solid fa-user-graduate", "variant": "btn--ghost"},
        {"label": "Histórico Escolar", "url": reverse("educacao:historico_aluno", args=[aluno.pk]), "icon": "fa-solid fa-scroll", "variant": "btn--ghost"},
        {
            "label": "Declaração de Vínculo",
            "url": reverse("educacao:declaracao_vinculo_pdf", args=[aluno.pk]),
            "icon": "fa-solid fa-file-signature",
            "variant": "btn--ghost",
        },
    ]
    if can_edu_manage:
        actions.append(
            {
                "label": "Carteira PDF",
                "url": reverse("educacao:carteira_emitir_pdf", args=[aluno.pk]),
                "icon": "fa-solid fa-id-card",
                "variant": "btn--ghost",
            }
        )
        actions.append({"label": "Editar", "url": reverse("educacao:aluno_update", args=[aluno.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    return render(
        request,
        "educacao/aluno_detail.html",
        {
            "actions": actions,
            "aluno": aluno,
            "fields": fields,
            "pills": pills,
            "headers_matriculas": headers_matriculas,
            "rows_matriculas": rows_matriculas,
            "matriculas": matriculas,
            "form_matricula": form_matricula,
            "necessidades": necessidades,
            "form_nee": form_nee,
            "apoios": apoios,
            "acompanhamentos": apoios,
            "form_apoio": form_apoio,
            "form_movimentacao": form_movimentacao,
            "matriculas_cursos": matriculas_cursos,
            "documentos": documentos,
            "certificados": certificados,
            "carteiras_estudantis": carteiras_estudantis,
            "form_documento": form_documento,
            "form_certificado": form_certificado,
            "form_matricula_curso": form_matricula_curso,
            "headers_movimentacoes": headers_movimentacoes,
            "rows_movimentacoes": rows_movimentacoes,
            "movimentacoes_actions_partial": "educacao/partials/movimentacao_actions.html",
            "allowed_matriculas": list(allowed_matriculas),
            "can_edu_manage": can_edu_manage,
            "can_nee_manage": can_nee_manage,
            "can_emitir_declaracao": can(request.user, "educacao.view"),
            "atendimentos_saude": atendimentos_saude,
            "agendamentos_saude": agendamentos_saude,
            "beneficios_entregas": beneficios_entregas,
            "beneficios_inscricoes": beneficios_inscricoes,
        },
    )
