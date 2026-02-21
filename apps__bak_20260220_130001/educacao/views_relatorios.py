from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_unidades, scope_filter_matriculas, scope_filter_turmas
from apps.org.models import Unidade
from .models import Matricula, Turma


def _clean_param(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.lower() in {"none", "null", "undefined"} else v


@login_required
@require_perm("educacao.view")
def relatorio_mensal(request):
    inicio = _clean_param(request.GET.get("inicio"))
    fim = _clean_param(request.GET.get("fim"))
    unidade_id = _clean_param(request.GET.get("unidade"))
    export = _clean_param(request.GET.get("export")).lower()

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO).order_by("nome")
    )

    matriculas = Matricula.objects.select_related("turma", "turma__unidade").all()
    matriculas = scope_filter_matriculas(request.user, matriculas)

    # período pela data_matricula
    if inicio:
        matriculas = matriculas.filter(data_matricula__gte=inicio)
    if fim:
        matriculas = matriculas.filter(data_matricula__lte=fim)

    # filtra unidade via turma__unidade
    if unidade_id and unidade_id.isdigit():
        if unidades_qs.filter(pk=int(unidade_id)).exists():
            matriculas = matriculas.filter(turma__unidade_id=int(unidade_id))

    # KPIs
    total_matriculas = matriculas.count()
    alunos_unicos = matriculas.values("aluno_id").distinct().count()
    turmas_unicas = matriculas.values("turma_id").distinct().count()

    # resumo por unidade
    resumo = (
        matriculas.values("turma__unidade__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # =========================
    # EXPORT PDF
    # =========================
    if export == "pdf":
        headers = ["Unidade", "Total de Matrículas"]
        rows = [[r["turma__unidade__nome"], r["total"]] for r in resumo]
        filtros_txt = f"Início={inicio or '-'} | Fim={fim or '-'}"
        return export_pdf_table(
            request,
            filename="relatorio_mensal_educacao.pdf",
            title="Relatório Mensal — Educação (Matrículas)",
            headers=headers,
            rows=rows,
            filtros=filtros_txt,
        )

    # actions
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
        {"label": "Exportar PDF", "url": qjoin("export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    # extra_filters (filter_bar)
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

    return render(request, "educacao/relatorio_mensal.html", {
        "actions": actions,
        "action_url": reverse("educacao:relatorio_mensal"),
        "clear_url": reverse("educacao:relatorio_mensal"),
        "has_filters": bool(inicio or fim or unidade_id),
        "extra_filters": extra_filters,

        "inicio": inicio,
        "fim": fim,
        "unidade_id": unidade_id,

        "total_matriculas": total_matriculas,
        "alunos_unicos": alunos_unicos,
        "turmas_unicas": turmas_unicas,
        "resumo": resumo,
    })
