from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify

from apps.core.decorators import require_perm
from apps.core.exports import _try_make_qr_data_uri, export_csv, export_pdf_template
from apps.core.rbac import is_admin
from apps.core.services_auditoria import registrar_auditoria
from apps.org.models import Municipio

from .forms import (
    AvaliacaoProvaForm,
    CorrecaoFolhaForm,
    QuestaoProvaForm,
    RespostasObjetivasForm,
    TokenLookupForm,
)
from .models import AplicacaoAvaliacao, AvaliacaoProva, FolhaResposta, GabaritoProva
from .omr import OMRDetectionError, suggest_answers_from_omr_image
from .services import (
    build_validation_url,
    corrigir_folha_manual,
    ensure_aplicacoes_da_avaliacao,
    ensure_gabaritos_basicos,
    gabarito_para_versao,
    normalize_respostas,
    public_validation_payload,
    resultados_por_questao,
    versoes_da_avaliacao,
)


def _resolve_municipio(request, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None


def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")


def _avaliacoes_queryset(request):
    qs = AvaliacaoProva.objects.select_related(
        "municipio",
        "secretaria",
        "unidade",
        "setor",
        "turma",
        "turma__unidade",
        "turma__unidade__secretaria",
        "turma__unidade__secretaria__municipio",
        "avaliacao_diario",
    )

    user = request.user
    if is_admin(user):
        return qs

    profile = getattr(user, "profile", None)
    if not profile or not profile.municipio_id:
        return qs.none()

    qs = qs.filter(municipio_id=profile.municipio_id)
    role = (getattr(profile, "role", "") or "").upper()

    if role == "SECRETARIA" and profile.secretaria_id:
        qs = qs.filter(turma__unidade__secretaria_id=profile.secretaria_id)
    elif role == "UNIDADE" and profile.unidade_id:
        qs = qs.filter(turma__unidade_id=profile.unidade_id)
    elif role == "PROFESSOR":
        qs = qs.filter(turma__professores=user).distinct()

    return qs


@login_required
@require_perm("avaliacoes.view")
def index(request):
    return redirect("avaliacoes:avaliacao_list")


@login_required
@require_perm("avaliacoes.view")
def avaliacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para acessar Avaliações.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    turma_id = (request.GET.get("turma") or "").strip()

    qs = _avaliacoes_queryset(request).filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(disciplina__icontains=q) | Q(turma__nome__icontains=q))
    if tipo:
        qs = qs.filter(tipo=tipo)
    if turma_id.isdigit():
        qs = qs.filter(turma_id=int(turma_id))

    items = list(
        qs.annotate(
            total_aplicacoes=Count("aplicacoes", distinct=True),
            total_corrigidas=Count(
                "aplicacoes",
                filter=Q(aplicacoes__status=AplicacaoAvaliacao.Status.CORRIGIDA),
                distinct=True,
            ),
            media=Avg("aplicacoes__nota"),
        ).order_by("-data_aplicacao", "-id")
    )

    turmas = (
        qs.values("turma_id", "turma__nome", "turma__ano_letivo")
        .order_by("-turma__ano_letivo", "turma__nome")
        .distinct()
    )

    return render(
        request,
        "avaliacoes/list.html",
        {
            "title": "Provas e Gabarito",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": items,
            "q": q,
            "tipo": tipo,
            "turma_id": turma_id,
            "turmas": turmas,
            "tipo_choices": AvaliacaoProva.Tipo.choices,
            "actions": [
                {
                    "label": "Nova avaliação",
                    "url": reverse("avaliacoes:avaliacao_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Portal",
                    "url": reverse("portal"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("avaliacoes.manage")
def avaliacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar avaliações.")
        return redirect("avaliacoes:avaliacao_list")

    form = AvaliacaoProvaForm(request.POST or None, municipio=municipio, user=request.user)

    if request.method == "POST" and form.is_valid():
        avaliacao = form.save(commit=False)

        turma = form.cleaned_data["turma"]
        unidade = turma.unidade
        secretaria = unidade.secretaria if unidade else None
        municipio_scope = secretaria.municipio if secretaria else municipio

        avaliacao.municipio = municipio_scope
        if not avaliacao.secretaria_id:
            avaliacao.secretaria = secretaria
        if not avaliacao.unidade_id:
            avaliacao.unidade = unidade
        avaliacao.criado_por = request.user
        avaliacao.save()

        ensure_gabaritos_basicos(avaliacao, actor=request.user)
        sync_info = ensure_aplicacoes_da_avaliacao(avaliacao, actor=request.user)

        registrar_auditoria(
            municipio=avaliacao.municipio,
            modulo="AVALIACOES",
            evento="AVALIACAO_CRIADA",
            entidade="AvaliacaoProva",
            entidade_id=avaliacao.pk,
            usuario=request.user,
            depois={
                "turma": avaliacao.turma_id,
                "qtd_questoes": avaliacao.qtd_questoes,
                "aplicacoes": sync_info,
            },
        )

        messages.success(
            request,
            f"Avaliação criada. Aplicações sincronizadas: {sync_info['total']} (novas: {sync_info['criadas']}).",
        )
        return redirect(reverse("avaliacoes:avaliacao_detail", args=[avaliacao.pk]) + f"?municipio={avaliacao.municipio_id}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova avaliação",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("avaliacoes:avaliacao_list") + f"?municipio={municipio.pk}",
            "submit_label": "Criar avaliação",
        },
    )


@login_required
@require_perm("avaliacoes.view")
def avaliacao_detail(request, pk: int):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=pk)

    aplicacoes = (
        avaliacao.aplicacoes.select_related("aluno", "matricula", "folha")
        .order_by("aluno__nome")
    )
    stats = aplicacoes.aggregate(
        total=Count("id"),
        corrigidas=Count("id", filter=Q(status=AplicacaoAvaliacao.Status.CORRIGIDA)),
        media=Avg("nota"),
    )

    token_form = TokenLookupForm()
    versoes = versoes_da_avaliacao(avaliacao)

    actions = [
        {
            "label": "Nova questão",
            "url": reverse("avaliacoes:questao_create", args=[avaliacao.pk]) + f"?municipio={avaliacao.municipio_id}",
            "icon": "fa-solid fa-circle-plus",
            "variant": "btn--ghost",
        },
        {
            "label": "Resultados",
            "url": reverse("avaliacoes:resultados", args=[avaliacao.pk]) + f"?municipio={avaliacao.municipio_id}",
            "icon": "fa-solid fa-chart-column",
            "variant": "btn--ghost",
        },
        {
            "label": "PDF provas",
            "url": reverse("avaliacoes:prova_pdf", args=[avaliacao.pk]) + f"?municipio={avaliacao.municipio_id}",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn-primary",
        },
        {
            "label": "CSV notas",
            "url": reverse("avaliacoes:resultados_csv", args=[avaliacao.pk]) + f"?municipio={avaliacao.municipio_id}",
            "icon": "fa-solid fa-file-csv",
            "variant": "btn--ghost",
        },
    ]

    for versao in versoes:
        actions.append(
            {
                "label": f"Gabarito {versao}",
                "url": reverse("avaliacoes:gabarito_update", args=[avaliacao.pk, versao]) + f"?municipio={avaliacao.municipio_id}",
                "icon": "fa-solid fa-list-check",
                "variant": "btn--ghost",
            }
        )

    return render(
        request,
        "avaliacoes/detail.html",
        {
            "title": f"Avaliação • {avaliacao.titulo}",
            "subtitle": f"{avaliacao.municipio.nome}/{avaliacao.municipio.uf}",
            "avaliacao": avaliacao,
            "aplicacoes": aplicacoes,
            "questoes": avaliacao.questoes.order_by("numero"),
            "gabaritos": {g.versao: g for g in avaliacao.gabaritos.order_by("versao")},
            "stats": stats,
            "token_form": token_form,
            "actions": actions,
        },
    )


@login_required
@require_perm("avaliacoes.manage")
def avaliacao_sync(request, pk: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=pk)
    info = ensure_aplicacoes_da_avaliacao(avaliacao, actor=request.user)

    messages.success(
        request,
        f"Aplicações sincronizadas: {info['total']} (novas: {info['criadas']}, atualizadas: {info['atualizadas']}).",
    )
    return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)


@login_required
@require_perm("avaliacoes.manage")
def questao_create(request, avaliacao_pk: int):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao_pk)
    form = QuestaoProvaForm(request.POST or None, avaliacao=avaliacao)

    if request.method == "POST" and form.is_valid():
        questao = form.save()
        registrar_auditoria(
            municipio=avaliacao.municipio,
            modulo="AVALIACOES",
            evento="QUESTAO_CRIADA",
            entidade="QuestaoProva",
            entidade_id=questao.pk,
            usuario=request.user,
            depois={"avaliacao": avaliacao.pk, "numero": questao.numero},
        )
        messages.success(request, "Questão cadastrada.")
        return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Nova questão • {avaliacao.titulo}",
            "subtitle": f"Turma {avaliacao.turma.nome}",
            "form": form,
            "cancel_url": reverse("avaliacoes:avaliacao_detail", args=[avaliacao.pk]),
            "submit_label": "Salvar questão",
        },
    )


@login_required
@require_perm("avaliacoes.manage")
def questao_update(request, avaliacao_pk: int, questao_pk: int):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao_pk)
    questao = get_object_or_404(avaliacao.questoes.all(), pk=questao_pk)

    form = QuestaoProvaForm(request.POST or None, instance=questao, avaliacao=avaliacao)

    if request.method == "POST" and form.is_valid():
        questao = form.save()
        registrar_auditoria(
            municipio=avaliacao.municipio,
            modulo="AVALIACOES",
            evento="QUESTAO_ATUALIZADA",
            entidade="QuestaoProva",
            entidade_id=questao.pk,
            usuario=request.user,
            depois={"avaliacao": avaliacao.pk, "numero": questao.numero},
        )
        messages.success(request, "Questão atualizada.")
        return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar questão Q{questao.numero}",
            "subtitle": avaliacao.titulo,
            "form": form,
            "cancel_url": reverse("avaliacoes:avaliacao_detail", args=[avaliacao.pk]),
            "submit_label": "Atualizar questão",
        },
    )


@login_required
@require_perm("avaliacoes.manage")
def gabarito_update(request, avaliacao_pk: int, versao: str):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao_pk)
    versao = (versao or "A").upper()

    if versao not in versoes_da_avaliacao(avaliacao):
        messages.error(request, "Versão de gabarito inválida para esta avaliação.")
        return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)

    gabarito, _ = GabaritoProva.objects.get_or_create(
        avaliacao=avaliacao,
        versao=versao,
        defaults={"respostas": {}, "atualizado_por": request.user},
    )

    initial = normalize_respostas(
        gabarito.respostas,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
    )
    form = RespostasObjetivasForm(
        request.POST or None,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
        initial_respostas=initial,
    )

    if request.method == "POST" and form.is_valid():
        gabarito.respostas = form.respostas_dict()
        gabarito.atualizado_por = request.user
        gabarito.save()

        registrar_auditoria(
            municipio=avaliacao.municipio,
            modulo="AVALIACOES",
            evento="GABARITO_ATUALIZADO",
            entidade="GabaritoProva",
            entidade_id=gabarito.pk,
            usuario=request.user,
            depois={"versao": versao, "qtd_respostas": len(gabarito.respostas or {})},
        )

        messages.success(request, f"Gabarito {versao} atualizado.")
        return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)

    return render(
        request,
        "avaliacoes/gabarito_form.html",
        {
            "title": f"Gabarito {versao}",
            "subtitle": avaliacao.titulo,
            "avaliacao": avaliacao,
            "versao": versao,
            "form": form,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("avaliacoes:avaliacao_detail", args=[avaliacao.pk]),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("avaliacoes.manage")
def folha_token_lookup(request):
    form = TokenLookupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        token = form.cleaned_data["token"]
        return redirect("avaliacoes:folha_corrigir", token=token)

    messages.error(request, "Token inválido.")
    return redirect("avaliacoes:avaliacao_list")


@login_required
@require_perm("avaliacoes.manage")
def folha_corrigir(request, token):
    folha = get_object_or_404(
        FolhaResposta.objects.select_related(
            "aplicacao",
            "aplicacao__avaliacao",
            "aplicacao__aluno",
            "aplicacao__avaliacao__turma",
            "aplicacao__avaliacao__municipio",
        ),
        token=token,
    )
    avaliacao = folha.aplicacao.avaliacao

    # Respeita escopo do usuário
    get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao.pk)

    gabarito = gabarito_para_versao(avaliacao, folha.versao)
    if gabarito is None:
        messages.error(request, "Defina o gabarito antes de corrigir a folha.")
        return redirect("avaliacoes:gabarito_update", avaliacao_pk=avaliacao.pk, versao=folha.versao)

    initial = normalize_respostas(
        folha.respostas_marcadas,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
    )
    form = CorrecaoFolhaForm(
        request.POST or None,
        request.FILES or None,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
        initial_respostas=initial,
    )

    resultado = None
    omr_resultado = None
    if request.method == "POST" and form.is_valid():
        action = (request.POST.get("action") or "save").strip().lower()
        imagem_upload = form.cleaned_data.get("imagem_original")

        if action == "omr":
            if imagem_upload is not None:
                folha.imagem_original = imagem_upload
                folha.save(update_fields=["imagem_original", "hash_assinado", "atualizado_em"])

            imagem_ref = folha.imagem_original or imagem_upload
            if imagem_ref is None:
                messages.error(request, "Envie uma imagem da folha para executar OMR.")
            else:
                try:
                    omr_resultado = suggest_answers_from_omr_image(
                        imagem_ref,
                        qtd_questoes=avaliacao.qtd_questoes,
                        opcoes=avaliacao.opcoes,
                    )
                except OMRDetectionError as exc:
                    messages.error(request, str(exc))
                else:
                    manuais = form.respostas_dict()
                    sugeridas = dict(omr_resultado.get("respostas") or {})
                    merged = dict(sugeridas)
                    merged.update(manuais)

                    form = CorrecaoFolhaForm(
                        qtd_questoes=avaliacao.qtd_questoes,
                        opcoes=avaliacao.opcoes,
                        initial_respostas=merged,
                    )

                    detectadas = int(omr_resultado.get("questoes_detectadas") or 0)
                    confianca_media = omr_resultado.get("confianca_media") or 0
                    if detectadas == 0:
                        messages.warning(
                            request,
                            "Nenhuma marcação foi detectada automaticamente. Revise e preencha manualmente.",
                        )
                    else:
                        messages.info(
                            request,
                            f"OMR sugeriu {detectadas} respostas (confiança média {confianca_media}%). Revise antes de salvar.",
                        )
        else:
            try:
                resultado = corrigir_folha_manual(
                    folha,
                    respostas_marcadas=form.respostas_dict(),
                    actor=request.user,
                    anexar_imagem=imagem_upload,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Correção salva. Nota {resultado['nota']} ({resultado['percentual']}%).",
                )
                return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)

    gabarito_norm = normalize_respostas(
        gabarito.respostas,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
    )
    marcadas = normalize_respostas(
        folha.respostas_marcadas,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
    )
    gabarito_rows = []
    for idx in range(1, int(avaliacao.qtd_questoes or 0) + 1):
        key = str(idx)
        gabarito_rows.append(
            {
                "numero": idx,
                "oficial": gabarito_norm.get(key, "-"),
                "marcada": marcadas.get(key, "-"),
            }
        )

    return render(
        request,
        "avaliacoes/correcao.html",
        {
            "title": f"Correção • {folha.aplicacao.aluno.nome}",
            "subtitle": avaliacao.titulo,
            "avaliacao": avaliacao,
            "folha": folha,
            "aplicacao": folha.aplicacao,
            "gabarito": gabarito,
            "gabarito_rows": gabarito_rows,
            "form": form,
            "resultado": resultado,
            "omr_resultado": omr_resultado,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("avaliacoes:avaliacao_detail", args=[avaliacao.pk]),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("avaliacoes.view")
def resultados(request, avaliacao_pk: int):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao_pk)
    aplicacoes = (
        avaliacao.aplicacoes.select_related("aluno")
        .order_by("-nota", "aluno__nome")
    )

    ranking = [app for app in aplicacoes if app.nota is not None]
    questoes = resultados_por_questao(avaliacao)

    distribuicao = defaultdict(int)
    for app in ranking:
        nota = Decimal(app.nota or 0)
        if nota >= Decimal("8"):
            distribuicao["8-10"] += 1
        elif nota >= Decimal("6"):
            distribuicao["6-7.99"] += 1
        elif nota >= Decimal("4"):
            distribuicao["4-5.99"] += 1
        else:
            distribuicao["0-3.99"] += 1

    faixas_distribuicao = [
        {"label": "8-10", "total": distribuicao.get("8-10", 0)},
        {"label": "6-7.99", "total": distribuicao.get("6-7.99", 0)},
        {"label": "4-5.99", "total": distribuicao.get("4-5.99", 0)},
        {"label": "0-3.99", "total": distribuicao.get("0-3.99", 0)},
    ]

    return render(
        request,
        "avaliacoes/resultados.html",
        {
            "title": f"Resultados • {avaliacao.titulo}",
            "subtitle": f"Turma {avaliacao.turma.nome}",
            "avaliacao": avaliacao,
            "ranking": ranking,
            "questoes": questoes,
            "faixas_distribuicao": faixas_distribuicao,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("avaliacoes:avaliacao_detail", args=[avaliacao.pk]),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Exportar CSV",
                    "url": reverse("avaliacoes:resultados_csv", args=[avaliacao.pk]),
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn-primary",
                },
            ],
        },
    )


@login_required
@require_perm("avaliacoes.view")
def resultados_csv(request, avaliacao_pk: int):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao_pk)
    aplicacoes = avaliacao.aplicacoes.select_related("aluno").order_by("aluno__nome")

    headers = ["Aluno", "Status", "Versão", "Nota", "Percentual", "Corrigido em", "Token"]
    rows: list[list[str]] = []
    for app in aplicacoes:
        token = getattr(getattr(app, "folha", None), "token", "")
        rows.append(
            [
                app.aluno.nome,
                app.get_status_display(),
                app.versao,
                f"{app.nota}" if app.nota is not None else "",
                f"{app.percentual}" if app.percentual is not None else "",
                app.corrigido_em.strftime("%d/%m/%Y %H:%M") if app.corrigido_em else "",
                str(token or ""),
            ]
        )

    filename = f"resultados_{slugify(avaliacao.titulo) or avaliacao.pk}.csv"
    return export_csv(filename, headers, rows)


@login_required
@require_perm("avaliacoes.view")
def prova_pdf(request, avaliacao_pk: int):
    avaliacao = get_object_or_404(_avaliacoes_queryset(request), pk=avaliacao_pk)
    ensure_aplicacoes_da_avaliacao(avaliacao, actor=request.user)

    aplicacoes = (
        avaliacao.aplicacoes.select_related("aluno", "matricula", "folha")
        .order_by("aluno__nome")
    )
    if not aplicacoes.exists():
        messages.error(request, "Nenhum aluno ativo na turma para gerar prova.")
        return redirect("avaliacoes:avaliacao_detail", pk=avaliacao.pk)

    letras = [chr(ord("A") + idx) for idx in range(avaliacao.opcoes)]
    itens = []
    for app in aplicacoes:
        folha = getattr(app, "folha", None)
        if folha is None:
            continue

        validation_url = build_validation_url(request, folha)
        itens.append(
            {
                "aplicacao": app,
                "aluno": app.aluno,
                "folha": folha,
                "validation_url": validation_url,
                "qr_data_uri": _try_make_qr_data_uri(validation_url),
            }
        )

    response = export_pdf_template(
        request,
        filename=f"provas_{slugify(avaliacao.titulo) or avaliacao.pk}.pdf",
        title=f"Provas • {avaliacao.titulo}",
        template_name="avaliacoes/pdf/prova_lote.html",
        subtitle=f"Turma {avaliacao.turma.nome}",
        hash_payload=f"avaliacao|{avaliacao.pk}|{len(itens)}",
        context={
            "avaliacao": avaliacao,
            "itens": itens,
            "letras": letras,
            "questoes_range": range(1, int(avaliacao.qtd_questoes or 0) + 1),
        },
    )

    registrar_auditoria(
        municipio=avaliacao.municipio,
        modulo="AVALIACOES",
        evento="PDF_PROVAS_GERADO",
        entidade="AvaliacaoProva",
        entidade_id=avaliacao.pk,
        usuario=request.user,
        depois={"aplicacoes": len(itens)},
    )
    return response


def folha_validar(request, token):
    folha = get_object_or_404(
        FolhaResposta.objects.select_related(
            "aplicacao",
            "aplicacao__avaliacao",
            "aplicacao__avaliacao__turma",
            "aplicacao__aluno",
        ),
        token=token,
    )

    context = public_validation_payload(folha)
    context.update(
        {
            "title": "Validação de folha de prova",
            "busca_token": str(token),
        }
    )
    return render(request, "avaliacoes/validacao_publica.html", context)
