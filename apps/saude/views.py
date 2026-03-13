from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import render

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade
from .models import ProfissionalSaude
from .models import AtendimentoSaude
from .models import (
    AgendamentoSaude,
    AuditoriaAcessoProntuarioSaude,
    EspecialidadeSaude,
    FilaEsperaSaude,
)


@login_required
@require_perm("saude.view")
def index(request):
    # =========================
    # UNIDADES (somente tipo SAÚDE)
    # =========================
    unidades_qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE)

    # aplica escopo do usuário (municipal / secretaria etc.)
    unidades_qs = scope_filter_unidades(request.user, unidades_qs)

    unidades_total = unidades_qs.count()
    unidades_ativas = unidades_qs.filter(ativo=True).count()
    unidades_inativas = unidades_qs.filter(ativo=False).count()

    # =========================
    # PROFISSIONAIS
    # =========================
    profissionais_qs = ProfissionalSaude.objects.filter(
        unidade__tipo=Unidade.Tipo.SAUDE
    ).select_related("unidade")

    # aplica escopo também baseado nas unidades visíveis
    profissionais_qs = profissionais_qs.filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    profissionais_total = profissionais_qs.filter(ativo=True).count()
    profissionais_inativos = profissionais_qs.filter(ativo=False).count()

    # =========================
    # ATENDIMENTOS (placeholder)
        # =========================
    atendimentos_total = AtendimentoSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True)).count()
    agendamentos_qs = AgendamentoSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    agendamentos_total = agendamentos_qs.count()
    agendamentos_pendentes = agendamentos_qs.filter(
        status__in=[AgendamentoSaude.Status.MARCADO, AgendamentoSaude.Status.CONFIRMADO]
    ).count()
    periodo_abs = timezone.now() - timezone.timedelta(days=30)
    agendamentos_30d = agendamentos_qs.filter(inicio__gte=periodo_abs)
    faltas_30d = agendamentos_30d.filter(status=AgendamentoSaude.Status.FALTA).count()
    total_30d = agendamentos_30d.count()
    taxa_absenteismo_30d = round((faltas_30d / total_30d) * 100, 2) if total_30d else 0

    fila_qs = FilaEsperaSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    fila_aguardando = fila_qs.filter(status=FilaEsperaSaude.Status.AGUARDANDO).count()
    sla_days = int(getattr(settings, "SAUDE_FILA_SLA_DIAS", 15) or 15)
    fila_sla_data = timezone.now() - timezone.timedelta(days=sla_days)
    fila_aguardando_sla = fila_qs.filter(
        status=FilaEsperaSaude.Status.AGUARDANDO,
        criado_em__lt=fila_sla_data,
    ).count()

    acessos_prontuario_7d = AuditoriaAcessoProntuarioSaude.objects.filter(
        atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True),
        criado_em__gte=timezone.now() - timezone.timedelta(days=7),
    ).count()
    especialidades_total = EspecialidadeSaude.objects.filter(ativo=True).count()

    context = {
        # Unidades
        "unidades_total": unidades_total,
        "unidades_ativas": unidades_ativas,
        "unidades_inativas": unidades_inativas,

        # Profissionais
        "profissionais_total": profissionais_total,
        "profissionais_inativos": profissionais_inativos,

        # Atendimentos
        "atendimentos_total": atendimentos_total,
        "agendamentos_total": agendamentos_total,
        "agendamentos_pendentes": agendamentos_pendentes,
        "faltas_30d": faltas_30d,
        "taxa_absenteismo_30d": taxa_absenteismo_30d,
        "fila_aguardando": fila_aguardando,
        "fila_aguardando_sla": fila_aguardando_sla,
        "fila_sla_dias": sla_days,
        "acessos_prontuario_7d": acessos_prontuario_7d,
        "especialidades_total": especialidades_total,
    }

    return render(request, "saude/index.html", context)
