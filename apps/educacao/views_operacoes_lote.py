from __future__ import annotations

import os
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_template
from apps.core.rbac import scope_filter_matriculas, scope_filter_turmas
from apps.org.models import Unidade

from .models import Matricula, Turma


class OperacoesLoteForm(forms.Form):
    class EstrategiaNomeFoto:
        ALUNO_ID = "ALUNO_ID"
        CPF = "CPF"
        CHOICES = [
            (ALUNO_ID, "Nome do arquivo = ID do aluno (ex.: 123.jpg)"),
            (CPF, "Nome do arquivo = CPF (somente dígitos, ex.: 12345678900.png)"),
        ]

    turma = forms.ModelChoiceField(
        label="Turma",
        queryset=Turma.objects.none(),
        required=True,
    )
    incluir_inativos = forms.BooleanField(
        label="Incluir matrículas não ativas",
        required=False,
        initial=False,
    )
    estrategia_foto = forms.ChoiceField(
        label="Estratégia de identificação das fotos no ZIP",
        choices=EstrategiaNomeFoto.CHOICES,
        initial=EstrategiaNomeFoto.ALUNO_ID,
    )
    arquivo_zip = forms.FileField(
        label="Arquivo ZIP com fotos (opcional)",
        required=False,
        help_text="Envie imagens .jpg/.jpeg/.png/.webp nomeadas conforme a estratégia selecionada.",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        turmas_qs = scope_filter_turmas(
            user,
            Turma.objects.select_related("unidade", "unidade__secretaria").filter(unidade__tipo=Unidade.Tipo.EDUCACAO),
        ).order_by("-ano_letivo", "nome")
        self.fields["turma"].queryset = turmas_qs


def _matriculas_turma_scope(user, *, turma: Turma, incluir_inativos: bool):
    qs = scope_filter_matriculas(
        user,
        Matricula.objects.select_related("aluno", "turma", "turma__unidade").filter(turma=turma),
    ).order_by("aluno__nome", "id")
    if not incluir_inativos:
        qs = qs.filter(situacao=Matricula.Situacao.ATIVA)
    return qs


def _preview_rows(matriculas):
    rows = []
    for m in matriculas:
        rows.append(
            {
                "cells": [
                    {"text": m.aluno.nome},
                    {"text": m.turma.nome},
                    {"text": m.get_situacao_display()},
                    {"text": m.aluno.cpf or "—"},
                    {"text": str(m.aluno_id)},
                ]
            }
        )
    return rows


def _build_pdf_payload(request, matriculas):
    payload = []
    for m in matriculas:
        foto_url = ""
        if getattr(m.aluno, "foto", None):
            try:
                foto_url = request.build_absolute_uri(m.aluno.foto.url)
            except Exception:
                foto_url = ""
        payload.append(
            {
                "aluno_id": m.aluno_id,
                "nome": m.aluno.nome,
                "cpf": m.aluno.cpf or "",
                "turma": m.turma.nome,
                "situacao": m.get_situacao_display(),
                "foto_url": foto_url,
            }
        )
    return payload


def _apply_photos_zip(*, upload, matriculas, strategy: str):
    image_ext = {".jpg", ".jpeg", ".png", ".webp"}
    mapa = {}
    for m in matriculas:
        aluno = m.aluno
        if strategy == OperacoesLoteForm.EstrategiaNomeFoto.CPF:
            chave = "".join(ch for ch in getattr(aluno, "cpf_digits", "") if ch.isdigit())
            if len(chave) == 11:
                mapa[chave] = aluno
            continue
        mapa[str(aluno.id)] = aluno

    atualizados = 0
    ignorados = []
    nao_mapeados = []

    raw = upload.read()
    with ZipFile(BytesIO(raw)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            _, ext = os.path.splitext(info.filename)
            ext = ext.lower()
            if ext not in image_ext:
                ignorados.append(info.filename)
                continue

            nome_arquivo = os.path.basename(info.filename)
            token, _ = os.path.splitext(nome_arquivo)
            token = "".join(ch for ch in token if ch.isdigit())
            if not token:
                nao_mapeados.append(nome_arquivo)
                continue

            aluno = mapa.get(token)
            if aluno is None:
                nao_mapeados.append(nome_arquivo)
                continue

            try:
                content = zf.read(info)
            except Exception:
                ignorados.append(info.filename)
                continue

            if not content:
                ignorados.append(info.filename)
                continue

            aluno.foto = SimpleUploadedFile(nome_arquivo, content)
            aluno.save()
            atualizados += 1

    return {
        "atualizados": atualizados,
        "ignorados": ignorados,
        "nao_mapeados": nao_mapeados,
    }


@login_required
@require_perm("educacao.manage")
def operacoes_lote(request):
    form = OperacoesLoteForm(request.POST or None, request.FILES or None, user=request.user)
    preview_rows = []
    preview_total = 0
    preview_headers = [
        {"label": "Aluno"},
        {"label": "Turma"},
        {"label": "Situação"},
        {"label": "CPF", "width": "160px"},
        {"label": "ID Aluno", "width": "120px"},
    ]
    actions = [
        {
            "label": "Voltar ao módulo",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    if request.method == "POST" and form.is_valid():
        action = (request.POST.get("_action") or "").strip().lower()
        turma: Turma = form.cleaned_data["turma"]
        incluir_inativos = bool(form.cleaned_data.get("incluir_inativos"))
        matriculas_qs = _matriculas_turma_scope(
            request.user,
            turma=turma,
            incluir_inativos=incluir_inativos,
        )
        matriculas = list(matriculas_qs)
        preview_rows = _preview_rows(matriculas)
        preview_total = len(preview_rows)

        if action == "preview":
            pass
        elif action in {"carometro_pdf", "etiquetas_pdf"}:
            if not matriculas:
                messages.warning(request, "Nenhuma matrícula encontrada para gerar o PDF.")
            else:
                payload = _build_pdf_payload(request, matriculas)
                now = timezone.localtime().strftime("%Y%m%d_%H%M")
                if action == "carometro_pdf":
                    return export_pdf_template(
                        request,
                        filename=f"carometro_{turma.id}_{now}.pdf",
                        title=f"Carômetro • {turma.nome}",
                        template_name="educacao/pdf/carometro_lote.html",
                        hash_payload=f"carometro|turma:{turma.id}|total:{len(payload)}",
                        context={"turma": turma, "alunos": payload},
                    )
                return export_pdf_template(
                    request,
                    filename=f"etiquetas_{turma.id}_{now}.pdf",
                    title=f"Etiquetas • {turma.nome}",
                    template_name="educacao/pdf/etiquetas_lote.html",
                    hash_payload=f"etiquetas|turma:{turma.id}|total:{len(payload)}",
                    context={"turma": turma, "alunos": payload},
                )
        elif action == "aplicar_fotos":
            upload = form.cleaned_data.get("arquivo_zip")
            if upload is None:
                form.add_error("arquivo_zip", "Selecione um arquivo ZIP para aplicar as fotos.")
            else:
                try:
                    result = _apply_photos_zip(
                        upload=upload,
                        matriculas=matriculas,
                        strategy=form.cleaned_data["estrategia_foto"],
                    )
                except BadZipFile:
                    form.add_error("arquivo_zip", "Arquivo inválido. Envie um ZIP válido.")
                except Exception:
                    form.add_error("arquivo_zip", "Não foi possível processar o ZIP informado.")
                else:
                    messages.success(
                        request,
                        f"Fotos atualizadas com sucesso: {result['atualizados']} aluno(s).",
                    )
                    if result["nao_mapeados"]:
                        sample = ", ".join(result["nao_mapeados"][:6])
                        messages.warning(
                            request,
                            "Arquivos sem correspondência: "
                            f"{sample}{' ...' if len(result['nao_mapeados']) > 6 else ''}",
                        )
                    if result["ignorados"]:
                        sample = ", ".join(result["ignorados"][:6])
                        messages.info(
                            request,
                            "Arquivos ignorados (extensão inválida ou corrompidos): "
                            f"{sample}{' ...' if len(result['ignorados']) > 6 else ''}",
                        )
                    return redirect("educacao:operacoes_lote")

    elif request.method == "GET":
        turma_id = (request.GET.get("turma") or "").strip()
        if turma_id.isdigit():
            form = OperacoesLoteForm(
                initial={"turma": int(turma_id)},
                user=request.user,
            )
            turma = form.fields["turma"].queryset.filter(pk=int(turma_id)).first()
            if turma:
                matriculas = list(
                    _matriculas_turma_scope(
                        request.user,
                        turma=turma,
                        incluir_inativos=False,
                    )
                )
                preview_rows = _preview_rows(matriculas)
                preview_total = len(preview_rows)

    return render(
        request,
        "educacao/operacoes_lote.html",
        {
            "form": form,
            "actions": actions,
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
        },
    )
