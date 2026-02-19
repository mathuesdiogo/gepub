from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade
from .models import AtendimentoSaude



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
        "inicio": inicio,
        "fim": fim,
        "unidade_id": unidade_id,
        "actions": actions,
        "action_url": reverse("saude:relatorio_mensal"),
        "clear_url": reverse("saude:relatorio_mensal"),
        "has_filters": bool(inicio or fim or unidade_id),
        "extra_filters": extra_filters,
    })
