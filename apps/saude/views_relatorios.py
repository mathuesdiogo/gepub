from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade
from .models import (
    AgendamentoSaude,
    AtendimentoSaude,
    AuditoriaAcessoProntuarioSaude,
    DocumentoClinicoSaude,
    ExamePedidoSaude,
    FilaEsperaSaude,
)



def _clean_param(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.lower() in {"none", "null", "undefined"} else v


@login_required
@require_perm("saude.view")
def relatorio_mensal(request):
    inicio = _clean_param(request.GET.get("inicio"))
    fim = _clean_param(request.GET.get("fim"))
    unidade_id = _clean_param(request.GET.get("unidade"))
    export = _clean_param(request.GET.get("export")).lower()

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome")
    )

    atendimentos = AtendimentoSaude.objects.select_related("unidade").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    if inicio:
        atendimentos = atendimentos.filter(data__gte=inicio)
    if fim:
        atendimentos = atendimentos.filter(data__lte=fim)
    if unidade_id and unidade_id.isdigit():
        atendimentos = atendimentos.filter(unidade_id=int(unidade_id))

    resumo = (
        atendimentos.values("unidade__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    total_atendimentos = atendimentos.count()
    total_unidades = resumo.count()
    total_agendamentos = AgendamentoSaude.objects.filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if inicio:
        total_agendamentos = total_agendamentos.filter(inicio__date__gte=inicio)
    if fim:
        total_agendamentos = total_agendamentos.filter(inicio__date__lte=fim)
    if unidade_id and unidade_id.isdigit():
        total_agendamentos = total_agendamentos.filter(unidade_id=int(unidade_id))

    total_agendamentos_count = total_agendamentos.count()
    total_faltas = total_agendamentos.filter(status=AgendamentoSaude.Status.FALTA).count()
    taxa_absenteismo = (
        round((total_faltas / total_agendamentos_count) * 100, 2) if total_agendamentos_count else 0
    )

    fila = FilaEsperaSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    if inicio:
        fila = fila.filter(criado_em__date__gte=inicio)
    if fim:
        fila = fila.filter(criado_em__date__lte=fim)
    if unidade_id and unidade_id.isdigit():
        fila = fila.filter(unidade_id=int(unidade_id))
    total_fila_aguardando = fila.filter(status=FilaEsperaSaude.Status.AGUARDANDO).count()
    total_fila_convertido = fila.filter(status=FilaEsperaSaude.Status.CONVERTIDO).count()

    top_cids = (
        atendimentos.exclude(cid__isnull=True)
        .exclude(cid__exact="")
        .values("cid")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    exames = ExamePedidoSaude.objects.filter(
        atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if inicio:
        exames = exames.filter(criado_em__date__gte=inicio)
    if fim:
        exames = exames.filter(criado_em__date__lte=fim)
    if unidade_id and unidade_id.isdigit():
        exames = exames.filter(atendimento__unidade_id=int(unidade_id))
    total_exames = exames.count()
    total_exames_com_resultado = exames.filter(
        Q(status=ExamePedidoSaude.Status.RESULTADO) | Q(resultado__isnull=False)
    ).count()
    total_encaixes = total_agendamentos.filter(tipo=AgendamentoSaude.Tipo.ENCAIXE).count()
    taxa_encaixe = round((total_encaixes / total_agendamentos_count) * 100, 2) if total_agendamentos_count else 0

    producao_profissionais = (
        atendimentos.values("profissional__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "profissional__nome")[:10]
    )

    producao_especialidades = (
        atendimentos.values("profissional__especialidade__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "profissional__especialidade__nome")[:10]
    )

    tempo_medio_espera_delta = (
        fila.exclude(chamado_em__isnull=True)
        .annotate(
            espera=ExpressionWrapper(F("chamado_em") - F("criado_em"), output_field=DurationField())
        )
        .aggregate(media=Avg("espera"))
        .get("media")
    )
    tempo_medio_espera_min = (
        round(tempo_medio_espera_delta.total_seconds() / 60, 1) if tempo_medio_espera_delta else 0
    )

    documentos = DocumentoClinicoSaude.objects.filter(
        atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if inicio:
        documentos = documentos.filter(criado_em__date__gte=inicio)
    if fim:
        documentos = documentos.filter(criado_em__date__lte=fim)
    if unidade_id and unidade_id.isdigit():
        documentos = documentos.filter(atendimento__unidade_id=int(unidade_id))
    total_documentos = documentos.count()
    total_documentos_validaveis = documentos.filter(documento_emitido__isnull=False).count()

    auditoria = AuditoriaAcessoProntuarioSaude.objects.filter(
        atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if inicio:
        auditoria = auditoria.filter(criado_em__date__gte=inicio)
    if fim:
        auditoria = auditoria.filter(criado_em__date__lte=fim)
    if unidade_id and unidade_id.isdigit():
        auditoria = auditoria.filter(atendimento__unidade_id=int(unidade_id))
    total_acessos_prontuario = auditoria.count()
    top_acoes_auditoria = auditoria.values("acao").annotate(total=Count("id")).order_by("-total")[:10]

    # =========================
    # EXPORT PDF
    # =========================
    if export == "pdf":
        headers = ["Unidade", "Total de Atendimentos"]
        rows = [[r["unidade__nome"], r["total"]] for r in resumo]

        filtros_txt = f"Início={inicio or '-'} | Fim={fim or '-'}"

        return export_pdf_table(
            request,
            filename="relatorio_mensal_saude.pdf",
            title="Relatório Mensal de Atendimentos — Saúde",
            headers=headers,
            rows=rows,
            filtros=filtros_txt,
        )

    # mantém filtros na query do export
    base_q = []
    if inicio:
        base_q.append(f"inicio={inicio}")
    if fim:
        base_q.append(f"fim={fim}")
    if unidade_id:
        base_q.append(f"unidade={unidade_id}")

    base_query = "&".join(base_q)

    def qjoin(extra: str) -> str:
        return f"?{base_query + ('&' if base_query else '')}{extra}"

    actions = [
        {
            "label": "Exportar PDF",
            "url": qjoin("export=pdf"),
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        }
    ]

    # filtro extra no padrão do sistema
    extra_filters = f"""
    <div class="filter-bar__field">
        <label>Data início</label>
        <input type="date" name="inicio" value="{inicio}">
    </div>
    <div class="filter-bar__field">
        <label>Data fim</label>
        <input type="date" name="fim" value="{fim}">
    </div>
    <div class="filter-bar__field">
        <label>Unidade</label>
        <select name="unidade">
            <option value="">Todas</option>
            {''.join([f'<option value="{u.id}" {"selected" if str(u.id)==str(unidade_id) else ""}>{u.nome}</option>' for u in unidades_qs])}
        </select>
    </div>
    """

    return render(request, "saude/relatorio_mensal.html", {
        "resumo": resumo,
        "total_atendimentos": total_atendimentos,
        "total_unidades": total_unidades,
        "total_agendamentos": total_agendamentos_count,
        "total_faltas": total_faltas,
        "taxa_absenteismo": taxa_absenteismo,
        "total_fila_aguardando": total_fila_aguardando,
        "total_fila_convertido": total_fila_convertido,
        "total_exames": total_exames,
        "total_exames_com_resultado": total_exames_com_resultado,
        "total_encaixes": total_encaixes,
        "taxa_encaixe": taxa_encaixe,
        "producao_profissionais": producao_profissionais,
        "producao_especialidades": producao_especialidades,
        "tempo_medio_espera_min": tempo_medio_espera_min,
        "total_documentos": total_documentos,
        "total_documentos_validaveis": total_documentos_validaveis,
        "total_acessos_prontuario": total_acessos_prontuario,
        "top_acoes_auditoria": top_acoes_auditoria,
        "top_cids": top_cids,
        "inicio": inicio,
        "fim": fim,
        "unidade_id": unidade_id,
        "actions": actions,
        "action_url": reverse("saude:relatorio_mensal"),
        "clear_url": reverse("saude:relatorio_mensal"),
        "has_filters": bool(inicio or fim or unidade_id),
        "extra_filters": extra_filters,
    })
