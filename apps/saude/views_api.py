from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_alunos, scope_filter_unidades
from apps.educacao.models import Aluno
from apps.org.models import Unidade

from .models import AgendamentoSaude, AtendimentoSaude, PacienteSaude, ProfissionalSaude


@login_required
@require_perm("saude.view")
@require_GET
def api_profissionais_por_unidade(request):
    unidade_id = (request.GET.get("unidade") or "").strip()
    if not unidade_id.isdigit():
        return JsonResponse({"results": []})

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE),
    )

    if not unidades_qs.filter(pk=int(unidade_id)).exists():
        return JsonResponse({"results": []})

    qs = (
        ProfissionalSaude.objects.filter(unidade_id=int(unidade_id), ativo=True)
        .select_related("unidade")
        .order_by("nome")[:200]
    )

    return JsonResponse({"results": [{"id": p.id, "text": p.nome} for p in qs]})


@login_required
@require_perm("saude.view")
@require_GET
def api_alunos_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = scope_filter_alunos(
        request.user,
        Aluno.objects.only("id", "nome", "cpf", "nis"),
    ).filter(
        Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(nis__icontains=q)
    ).order_by("nome")[:10]

    results = []
    for aluno in qs:
        meta_bits = []
        if aluno.cpf:
            meta_bits.append(f"CPF {aluno.cpf}")
        if aluno.nis:
            meta_bits.append(f"NIS {aluno.nis}")

        results.append(
            {
                "id": aluno.id,
                "nome": aluno.nome,
                "meta": " • ".join(meta_bits),
            }
        )
    return JsonResponse({"results": results})


def _scoped_saude_unidades(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE))


@login_required
@require_perm("saude.view")
@require_GET
def api_pacientes_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    unidades_qs = _scoped_saude_unidades(request.user)
    qs = (
        PacienteSaude.objects.select_related("unidade_referencia")
        .filter(unidade_referencia_id__in=unidades_qs.values_list("id", flat=True))
        .filter(Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(cartao_sus__icontains=q))
        .order_by("nome")[:12]
    )

    results = []
    for paciente in qs:
        meta_bits = [paciente.unidade_referencia.nome]
        if paciente.cpf:
            meta_bits.append(f"CPF {paciente.cpf}")
        elif paciente.cartao_sus:
            meta_bits.append(f"SUS {paciente.cartao_sus}")

        results.append(
            {
                "id": paciente.id,
                "nome": paciente.nome,
                "meta": " • ".join(meta_bits),
            }
        )
    return JsonResponse({"results": results})


@login_required
@require_perm("saude.view")
@require_GET
def api_atendimentos_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    unidades_qs = _scoped_saude_unidades(request.user)
    qs = AtendimentoSaude.objects.select_related("unidade").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    search_filter = (
        Q(paciente_nome__icontains=q)
        | Q(paciente_cpf__icontains=q)
        | Q(unidade__nome__icontains=q)
    )
    if q.isdigit():
        search_filter |= Q(pk=int(q))

    qs = qs.filter(search_filter).order_by("-data", "-id")[:12]

    results = []
    for atendimento in qs:
        data_txt = atendimento.data.strftime("%d/%m/%Y")
        results.append(
            {
                "id": atendimento.id,
                "nome": f"#{atendimento.id} • {atendimento.paciente_nome}",
                "meta": f"{data_txt} • {atendimento.unidade.nome}",
            }
        )
    return JsonResponse({"results": results})


@login_required
@require_perm("saude.view")
@require_GET
def api_agendamentos_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    unidades_qs = _scoped_saude_unidades(request.user)
    qs = AgendamentoSaude.objects.select_related("unidade", "profissional").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    search_filter = (
        Q(paciente_nome__icontains=q)
        | Q(paciente_cpf__icontains=q)
        | Q(unidade__nome__icontains=q)
        | Q(profissional__nome__icontains=q)
    )
    if q.isdigit():
        search_filter |= Q(pk=int(q))

    qs = qs.filter(search_filter).order_by("-inicio", "-id")[:12]

    results = []
    for agendamento in qs:
        inicio_txt = agendamento.inicio.strftime("%d/%m/%Y %H:%M")
        profissional = agendamento.profissional.nome if agendamento.profissional_id else "Sem profissional"
        results.append(
            {
                "id": agendamento.id,
                "nome": f"#{agendamento.id} • {agendamento.paciente_nome}",
                "meta": f"{inicio_txt} • {profissional}",
            }
        )
    return JsonResponse({"results": results})
