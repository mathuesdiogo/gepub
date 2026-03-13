from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import OperationalError, ProgrammingError
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import calendar
import json

from apps.accounts.models import Profile
from apps.core.rbac import can, get_profile, is_admin, is_professor_profile_role, role_scope_base

from apps.org.models import (
    Municipio,
    Secretaria,
    Unidade,
    Setor,
    OnboardingStep,
    MunicipioOnboardingWizard,
    MunicipioModuloAtivo,
    SecretariaProvisionamento,
)
from apps.educacao.models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    CarteiraEstudantil,
    Curso,
    Matricula,
    Turma,
)
from apps.educacao.models_calendario import CalendarioEducacionalEvento
from apps.educacao.models_assistencia import (
    CardapioEscolar,
    RegistroRefeicaoEscolar,
    RotaTransporteEscolar,
    RegistroTransporteEscolar,
)
from apps.educacao.models_beneficios import BeneficioCampanha, BeneficioEntrega, BeneficioTipo
from apps.educacao.models_diario import (
    Aula,
    DiarioTurma,
    Frequencia,
    JustificativaFaltaPedido,
    Nota,
)
from apps.educacao.models_informatica import (
    InformaticaAlertaFrequencia,
    InformaticaAulaDiario,
    InformaticaCurso,
    InformaticaFrequencia,
    InformaticaLaboratorio,
    InformaticaListaEspera,
    InformaticaMatricula,
    InformaticaSolicitacaoVaga,
    InformaticaTurma,
)
try:
    from apps.nee.models import AlunoNecessidade, AcompanhamentoNEE, LaudoNEE
except Exception:
    AlunoNecessidade = None
    AcompanhamentoNEE = None
    LaudoNEE = None
from apps.compras.models import RequisicaoCompra
from apps.contratos.models import ContratoAdministrativo, MedicaoContrato
from apps.ouvidoria.models import OuvidoriaCadastro
from apps.paineis.models import Dataset
from apps.processos.models import ProcessoAdministrativo
from apps.comunicacao.models import NotificationJob

from apps.core.rbac import (
    scope_filter_secretarias,
    scope_filter_unidades,
    scope_filter_turmas,
    scope_filter_alunos,
    scope_filter_matriculas,
)

from .forms import AlunoAvisoForm, AlunoArquivoForm
from .models import AlunoAviso, AlunoArquivo


def _resolve_profile_municipio_id(profile) -> int | None:
    if not profile:
        return None
    if getattr(profile, "municipio_id", None):
        return int(profile.municipio_id)
    if getattr(profile, "secretaria_id", None):
        return (
            Secretaria.objects.filter(pk=profile.secretaria_id)
            .values_list("municipio_id", flat=True)
            .first()
        )
    if getattr(profile, "unidade_id", None):
        return (
            Unidade.objects.filter(pk=profile.unidade_id)
            .values_list("secretaria__municipio_id", flat=True)
            .first()
        )
    return None


def _build_informatica_scope_data(profile):
    today = timezone.localdate()
    unidade_id = getattr(profile, "unidade_id", None) if profile else None
    secretaria_id = getattr(profile, "secretaria_id", None) if profile else None
    municipio_id = _resolve_profile_municipio_id(profile)

    turmas_qs = InformaticaTurma.objects.select_related(
        "curso",
        "laboratorio",
        "laboratorio__unidade",
        "instrutor",
    ).all()
    if unidade_id:
        turmas_qs = turmas_qs.filter(laboratorio__unidade_id=unidade_id)
    elif secretaria_id:
        turmas_qs = turmas_qs.filter(laboratorio__unidade__secretaria_id=secretaria_id)
    elif municipio_id:
        turmas_qs = turmas_qs.filter(curso__municipio_id=municipio_id)

    turmas_ativas_qs = turmas_qs.filter(
        status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA]
    )
    turma_ids = list(turmas_ativas_qs.values_list("id", flat=True))

    cursos_qs = InformaticaCurso.objects.all()
    labs_qs = InformaticaLaboratorio.objects.all()
    if unidade_id:
        labs_qs = labs_qs.filter(unidade_id=unidade_id)
        cursos_qs = cursos_qs.filter(id__in=turmas_qs.values_list("curso_id", flat=True))
    elif secretaria_id:
        labs_qs = labs_qs.filter(unidade__secretaria_id=secretaria_id)
        cursos_qs = cursos_qs.filter(municipio_id=municipio_id) if municipio_id else cursos_qs.none()
    elif municipio_id:
        labs_qs = labs_qs.filter(unidade__secretaria__municipio_id=municipio_id)
        cursos_qs = cursos_qs.filter(municipio_id=municipio_id)
    else:
        cursos_qs = cursos_qs.none()
        labs_qs = labs_qs.none()

    matriculas_ativas_qs = InformaticaMatricula.objects.filter(
        status=InformaticaMatricula.Status.MATRICULADO,
        turma_id__in=turma_ids,
    )
    matriculados_total = matriculas_ativas_qs.count()
    alunos_externos_total = matriculas_ativas_qs.filter(externo_laboratorio=True).count()
    vagas_total = sum(int(v) for v in turmas_ativas_qs.values_list("max_vagas", flat=True))
    vagas_livres_total = max(0, int(vagas_total) - int(matriculados_total))

    aulas_qs = InformaticaAulaDiario.objects.select_related(
        "turma",
        "turma__laboratorio",
        "encontro",
    ).filter(turma_id__in=turma_ids)
    aulas_previstas_total = aulas_qs.exclude(status=InformaticaAulaDiario.Status.CANCELADA).count()
    aulas_realizadas_total = aulas_qs.filter(
        status__in=[InformaticaAulaDiario.Status.REALIZADA, InformaticaAulaDiario.Status.REPOSTA]
    ).count()
    aulas_pendentes_total = aulas_qs.filter(
        status=InformaticaAulaDiario.Status.PREVISTA,
        data_aula__lte=today,
    ).count()
    proximas_aulas = list(
        aulas_qs.exclude(status=InformaticaAulaDiario.Status.CANCELADA)
        .filter(data_aula__gte=today)
        .order_by("data_aula", "encontro__hora_inicio", "id")[:8]
    )

    frequencias_qs = InformaticaFrequencia.objects.filter(aula__turma_id__in=turma_ids)
    freq_total = frequencias_qs.count()
    freq_presentes = frequencias_qs.filter(presente=True).count()
    taxa_frequencia_media = round((freq_presentes / freq_total) * 100, 1) if freq_total else None

    alertas_ativos_total = InformaticaAlertaFrequencia.objects.filter(
        ativo=True,
        matricula__turma_id__in=turma_ids,
        matricula__status=InformaticaMatricula.Status.MATRICULADO,
    ).count()

    solicitacoes_pendentes_qs = InformaticaSolicitacaoVaga.objects.filter(
        status=InformaticaSolicitacaoVaga.Status.PENDENTE
    )
    lista_espera_qs = InformaticaListaEspera.objects.filter(status=InformaticaListaEspera.Status.ATIVA)
    if unidade_id:
        solicitacoes_pendentes_qs = solicitacoes_pendentes_qs.filter(escola_origem_id=unidade_id)
        lista_espera_qs = lista_espera_qs.filter(escola_origem_id=unidade_id)
    elif secretaria_id:
        solicitacoes_pendentes_qs = solicitacoes_pendentes_qs.filter(escola_origem__secretaria_id=secretaria_id)
        lista_espera_qs = lista_espera_qs.filter(escola_origem__secretaria_id=secretaria_id)
    elif municipio_id:
        solicitacoes_pendentes_qs = solicitacoes_pendentes_qs.filter(curso__municipio_id=municipio_id)
        lista_espera_qs = lista_espera_qs.filter(curso__municipio_id=municipio_id)
    else:
        solicitacoes_pendentes_qs = solicitacoes_pendentes_qs.none()
        lista_espera_qs = lista_espera_qs.none()

    turmas_ocupacao = list(
        turmas_ativas_qs.annotate(
            matriculados=Count(
                "matriculas",
                filter=Q(matriculas__status=InformaticaMatricula.Status.MATRICULADO),
            )
        )
        .order_by("-matriculados", "codigo")[:10]
    )
    turmas_ocupacao_rows = []
    for turma in turmas_ocupacao:
        ocupacao_pct = round((int(turma.matriculados) / int(turma.max_vagas)) * 100, 1) if turma.max_vagas else 0
        turmas_ocupacao_rows.append(
            {
                "id": turma.id,
                "codigo": turma.codigo,
                "curso": turma.curso.nome,
                "laboratorio": turma.laboratorio.nome,
                "matriculados": int(turma.matriculados),
                "vagas": int(turma.max_vagas),
                "ocupacao_pct": ocupacao_pct,
            }
        )

    censo_por_escola = list(
        matriculas_ativas_qs.values("escola_origem__nome")
        .annotate(
            total=Count("id"),
            externos=Count("id", filter=Q(externo_laboratorio=True)),
        )
        .order_by("-total", "escola_origem__nome")[:10]
    )
    censo_por_laboratorio = list(
        matriculas_ativas_qs.values("turma__laboratorio__nome", "turma__laboratorio__unidade__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "turma__laboratorio__nome")[:10]
    )

    taxa_ocupacao_media = round((matriculados_total / vagas_total) * 100, 1) if vagas_total else None

    return {
        "cursos_total": cursos_qs.distinct().count(),
        "laboratorios_total": labs_qs.distinct().count(),
        "turmas_total": turmas_qs.count(),
        "turmas_ativas_total": turmas_ativas_qs.count(),
        "matriculados_total": matriculados_total,
        "vagas_total": int(vagas_total),
        "vagas_livres_total": int(vagas_livres_total),
        "alunos_externos_total": alunos_externos_total,
        "lista_espera_total": lista_espera_qs.count(),
        "solicitacoes_pendentes_total": solicitacoes_pendentes_qs.count(),
        "aulas_previstas_total": aulas_previstas_total,
        "aulas_realizadas_total": aulas_realizadas_total,
        "aulas_pendentes_total": aulas_pendentes_total,
        "alertas_ativos_total": alertas_ativos_total,
        "taxa_frequencia_media": taxa_frequencia_media,
        "taxa_ocupacao_media": taxa_ocupacao_media,
        "proximas_aulas": proximas_aulas,
        "turmas_ocupacao_rows": turmas_ocupacao_rows,
        "censo_por_escola": censo_por_escola,
        "censo_por_laboratorio": censo_por_laboratorio,
    }


def _build_secretaria_educacao_scope_data(user, profile):
    today = timezone.localdate()
    ano_ref = today.year
    secretaria_id = getattr(profile, "secretaria_id", None) if profile else None
    municipio_id = _resolve_profile_municipio_id(profile)

    unidades_qs = scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    )
    turmas_qs = scope_filter_turmas(
        user,
        Turma.objects.filter(unidade__tipo=Unidade.Tipo.EDUCACAO),
    )
    alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
    matriculas_qs = scope_filter_matriculas(
        user,
        Matricula.objects.filter(turma__unidade__tipo=Unidade.Tipo.EDUCACAO),
    )

    matriculas_ativas_qs = matriculas_qs.filter(situacao=Matricula.Situacao.ATIVA)
    aluno_ids_matriculados = matriculas_qs.values_list("aluno_id", flat=True).distinct()

    turmas_infantil_filter = Q(modalidade=Turma.Modalidade.EDUCACAO_INFANTIL) | Q(
        etapa__in=[Turma.Etapa.CRECHE, Turma.Etapa.PRE_ESCOLA]
    )
    turmas_fundamental_filter = Q(
        etapa__in=[Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS, Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS]
    )
    turmas_regular_filter = Q(modalidade=Turma.Modalidade.REGULAR)
    turmas_complementar_filter = Q(modalidade=Turma.Modalidade.ATIVIDADE_COMPLEMENTAR)

    def _alunos_distintos_por_turma(turma_filter):
        return (
            matriculas_ativas_qs.filter(turma__in=turmas_qs.filter(turma_filter))
            .values("aluno_id")
            .distinct()
            .count()
        )

    eventos_qs = CalendarioEducacionalEvento.objects.filter(ativo=True, ano_letivo=ano_ref)
    if secretaria_id:
        eventos_qs = eventos_qs.filter(secretaria_id=secretaria_id)
    elif municipio_id:
        eventos_qs = eventos_qs.filter(secretaria__municipio_id=municipio_id)
    else:
        eventos_qs = eventos_qs.none()

    unidade_ids = list(unidades_qs.values_list("id", flat=True))
    unidades_destaque = list(
        matriculas_ativas_qs.values("turma__unidade_id", "turma__unidade__nome")
        .annotate(total=Count("aluno", distinct=True))
        .order_by("-total", "turma__unidade__nome")[:8]
    )
    modalidades_destaque_raw = list(
        matriculas_ativas_qs.values("turma__modalidade")
        .annotate(total=Count("aluno", distinct=True))
        .order_by("-total", "turma__modalidade")
    )
    modalidade_label_map = dict(Turma.Modalidade.choices)
    modalidades_destaque = [
        {
            "codigo": row.get("turma__modalidade") or "",
            "nome": modalidade_label_map.get(row.get("turma__modalidade"), row.get("turma__modalidade") or "—"),
            "total": int(row.get("total") or 0),
        }
        for row in modalidades_destaque_raw
    ]

    cursos_catalogo_total = (
        turmas_qs.exclude(curso_id__isnull=True).values("curso_id").distinct().count()
    )
    cursos_complementares_total = (
        turmas_qs.filter(turmas_complementar_filter).exclude(curso_id__isnull=True).values("curso_id").distinct().count()
    )
    turmas_complementares_total = turmas_qs.filter(turmas_complementar_filter).count()
    cursos_ativos_total = Curso.objects.filter(turmas__in=turmas_qs, ativo=True).distinct().count()
    cursos_inativos_total = Curso.objects.filter(turmas__in=turmas_qs, ativo=False).distinct().count()

    unidades_total = unidades_qs.count()
    escolas_ativas_total = unidades_qs.filter(ativo=True).count()
    escolas_inativas_total = max(0, unidades_total - escolas_ativas_total)
    escolas_por_tipo_educacional = list(
        unidades_qs.values("tipo_educacional")
        .annotate(total=Count("id"))
        .order_by("-total", "tipo_educacional")
    )

    turmas_por_turno_raw = list(
        turmas_qs.values("turno")
        .annotate(total=Count("id"))
        .order_by("turno")
    )
    turno_label_map = dict(Turma.Turno.choices)
    turmas_por_turno = [
        {
            "codigo": row.get("turno") or "",
            "nome": turno_label_map.get(row.get("turno"), row.get("turno") or "—"),
            "total": int(row.get("total") or 0),
        }
        for row in turmas_por_turno_raw
    ]

    matricula_indicadores = {
        "transferidos_total": matriculas_qs.filter(situacao=Matricula.Situacao.TRANSFERIDO).count(),
        "evadidos_total": matriculas_qs.filter(situacao=Matricula.Situacao.EVADIDO).count(),
        "cancelados_total": matriculas_qs.filter(situacao=Matricula.Situacao.CANCELADO).count(),
        "concluidos_total": matriculas_qs.filter(situacao=Matricula.Situacao.CONCLUIDO).count(),
        "aprovados_total": matriculas_qs.filter(resultado_final__istartswith="APROV").count(),
        "reprovados_total": matriculas_qs.filter(resultado_final__istartswith="REPROV").count(),
        "abandono_total": matriculas_qs.filter(
            Q(situacao=Matricula.Situacao.EVADIDO) | Q(resultado_final__istartswith="ABAND")
        ).count(),
    }

    turma_ids = list(turmas_qs.values_list("id", flat=True))
    frequencias_qs = Frequencia.objects.filter(aula__diario__turma_id__in=turma_ids)
    freq_total = frequencias_qs.count()
    freq_presentes = frequencias_qs.filter(status=Frequencia.Status.PRESENTE).count()
    freq_justificadas = frequencias_qs.filter(status=Frequencia.Status.JUSTIFICADA).count()
    freq_faltas = frequencias_qs.filter(status=Frequencia.Status.FALTA).count()
    frequencia = {
        "registros_total": freq_total,
        "presentes_total": freq_presentes,
        "justificadas_total": freq_justificadas,
        "faltas_total": freq_faltas,
        "taxa_presenca": round((freq_presentes / freq_total) * 100, 1) if freq_total else None,
        "taxa_presenca_com_justificativa": round(
            ((freq_presentes + freq_justificadas) / freq_total) * 100,
            1,
        )
        if freq_total
        else None,
    }

    notas_qs = Nota.objects.filter(avaliacao__diario__turma_id__in=turma_ids)
    media_notas = notas_qs.aggregate(media=Avg("valor")).get("media")
    pedagogico = {
        "diarios_total": DiarioTurma.objects.filter(turma_id__in=turma_ids).count(),
        "aulas_total": Aula.objects.filter(diario__turma_id__in=turma_ids).count(),
        "avaliacoes_total": notas_qs.values("avaliacao_id").distinct().count(),
        "notas_lancadas_total": notas_qs.count(),
        "media_notas_geral": round(float(media_notas), 2) if media_notas is not None else None,
    }

    documentos = {
        "documentos_total": AlunoDocumento.objects.filter(
            aluno_id__in=aluno_ids_matriculados,
            ativo=True,
        ).count(),
        "certificados_total": AlunoCertificado.objects.filter(
            aluno_id__in=aluno_ids_matriculados,
            ativo=True,
        ).count(),
        "carteiras_ativas_total": CarteiraEstudantil.objects.filter(
            aluno_id__in=aluno_ids_matriculados,
            ativa=True,
        ).count(),
    }

    profiles_qs = Profile.objects.filter(ativo=True, bloqueado=False, user__is_active=True)
    if secretaria_id:
        profiles_qs = profiles_qs.filter(
            Q(secretaria_id=secretaria_id) | Q(unidade__secretaria_id=secretaria_id)
        )
    elif municipio_id:
        profiles_qs = profiles_qs.filter(
            Q(municipio_id=municipio_id)
            | Q(secretaria__municipio_id=municipio_id)
            | Q(unidade__secretaria__municipio_id=municipio_id)
        )
    else:
        profiles_qs = profiles_qs.none()

    roles_educacao = {
        "EDU_SECRETARIO",
        "EDU_DIRETOR",
        "EDU_COORD",
        "EDU_PROF",
        "EDU_SECRETARIA",
        "EDU_TRANSPORTE",
        "NEE",
        "NEE_COORD_MUN",
        "NEE_COORD_ESC",
        "NEE_MEDIADOR",
        "NEE_TECNICO",
        "PROFESSOR",
    }
    profissionais_qs = profiles_qs.filter(role__in=roles_educacao)
    profissionais = {
        "total": profissionais_qs.count(),
        "professores_total": profissionais_qs.filter(role__in=["EDU_PROF", "PROFESSOR"]).count(),
        "coordenadores_total": profissionais_qs.filter(role__in=["EDU_COORD", "NEE_COORD_ESC", "NEE_COORD_MUN"]).count(),
        "gestores_total": profissionais_qs.filter(role__in=["EDU_SECRETARIO", "EDU_DIRETOR"]).count(),
        "secretaria_escolar_total": profissionais_qs.filter(role="EDU_SECRETARIA").count(),
        "nee_total": profissionais_qs.filter(role__in=["NEE", "NEE_COORD_MUN", "NEE_COORD_ESC", "NEE_MEDIADOR", "NEE_TECNICO"]).count(),
        "transporte_total": profissionais_qs.filter(role="EDU_TRANSPORTE").count(),
    }

    assistencia = {
        "cardapios_total": 0,
        "refeicoes_registradas_total": 0,
        "rotas_total": 0,
        "transporte_registros_total": 0,
    }
    if unidade_ids:
        assistencia["cardapios_total"] = CardapioEscolar.objects.filter(
            unidade_id__in=unidade_ids,
            data__year=ano_ref,
        ).count()
        assistencia["refeicoes_registradas_total"] = int(
            RegistroRefeicaoEscolar.objects.filter(
                unidade_id__in=unidade_ids,
                data__year=ano_ref,
            ).aggregate(total=Sum("total_servidas"))["total"]
            or 0
        )
        assistencia["rotas_total"] = RotaTransporteEscolar.objects.filter(
            unidade_id__in=unidade_ids,
            ativo=True,
        ).count()
        assistencia["transporte_registros_total"] = RegistroTransporteEscolar.objects.filter(
            rota__unidade_id__in=unidade_ids,
            data__year=ano_ref,
        ).count()

    beneficios_tipo_qs = BeneficioTipo.objects.filter(area=BeneficioTipo.Area.EDUCACAO)
    beneficios_campanha_qs = BeneficioCampanha.objects.filter(area=BeneficioTipo.Area.EDUCACAO)
    beneficios_entrega_qs = BeneficioEntrega.objects.filter(area=BeneficioTipo.Area.EDUCACAO)
    if secretaria_id:
        beneficios_tipo_qs = beneficios_tipo_qs.filter(
            Q(secretaria_id=secretaria_id)
            | Q(secretaria__isnull=True, municipio_id=municipio_id)
        )
        beneficios_campanha_qs = beneficios_campanha_qs.filter(
            Q(secretaria_id=secretaria_id)
            | Q(secretaria__isnull=True, municipio_id=municipio_id)
        )
        beneficios_entrega_qs = beneficios_entrega_qs.filter(
            Q(secretaria_id=secretaria_id)
            | Q(secretaria__isnull=True, municipio_id=municipio_id)
        )
    elif municipio_id:
        beneficios_tipo_qs = beneficios_tipo_qs.filter(municipio_id=municipio_id)
        beneficios_campanha_qs = beneficios_campanha_qs.filter(municipio_id=municipio_id)
        beneficios_entrega_qs = beneficios_entrega_qs.filter(municipio_id=municipio_id)
    else:
        beneficios_tipo_qs = beneficios_tipo_qs.none()
        beneficios_campanha_qs = beneficios_campanha_qs.none()
        beneficios_entrega_qs = beneficios_entrega_qs.none()

    beneficios = {
        "tipos_total": beneficios_tipo_qs.count(),
        "campanhas_ativas_total": beneficios_campanha_qs.filter(
            status__in=[BeneficioCampanha.Status.RASCUNHO, BeneficioCampanha.Status.EM_EXECUCAO]
        ).count(),
        "campanhas_doacao_total": beneficios_campanha_qs.filter(
            origem=BeneficioCampanha.Origem.DOACAO
        ).count(),
        "entregas_ano_total": beneficios_entrega_qs.filter(data_hora__year=ano_ref).count(),
        "entregas_pendentes_total": beneficios_entrega_qs.filter(
            status=BeneficioEntrega.Status.PENDENTE
        ).count(),
    }

    nee = {
        "alunos_nee_total": 0,
        "necessidades_ativas_total": 0,
        "laudos_vigentes_total": 0,
        "acompanhamentos_mes_total": 0,
    }
    if AlunoNecessidade and LaudoNEE and AcompanhamentoNEE:
        try:
            necessidades_qs = AlunoNecessidade.objects.filter(
                aluno_id__in=aluno_ids_matriculados,
                ativo=True,
            )
            nee["necessidades_ativas_total"] = necessidades_qs.count()
            nee["alunos_nee_total"] = necessidades_qs.values("aluno_id").distinct().count()
            nee["laudos_vigentes_total"] = LaudoNEE.objects.filter(
                aluno_id__in=aluno_ids_matriculados
            ).filter(Q(validade__isnull=True) | Q(validade__gte=today)).count()
            nee["acompanhamentos_mes_total"] = AcompanhamentoNEE.objects.filter(
                aluno_id__in=aluno_ids_matriculados,
                data__year=today.year,
                data__month=today.month,
            ).count()
        except (ProgrammingError, OperationalError):
            pass

    return {
        "ano_ref": ano_ref,
        "unidades_total": unidades_total,
        "escolas_total": unidades_total,
        "escolas_ativas_total": escolas_ativas_total,
        "escolas_inativas_total": escolas_inativas_total,
        "escolas_por_tipo_educacional": escolas_por_tipo_educacional,
        "turmas_total": turmas_qs.count(),
        "turmas_ativas_total": turmas_qs.filter(ativo=True).count(),
        "turmas_por_turno": turmas_por_turno,
        "alunos_total": alunos_qs.count(),
        "alunos_ativos_total": matriculas_ativas_qs.values("aluno_id").distinct().count(),
        "matriculas_total": matriculas_qs.count(),
        "matriculas_ativas_total": matriculas_ativas_qs.count(),
        "matricula_indicadores": matricula_indicadores,
        "segmentos": {
            "infantil_turmas_total": turmas_qs.filter(turmas_infantil_filter).count(),
            "infantil_alunos_total": _alunos_distintos_por_turma(turmas_infantil_filter),
            "regular_turmas_total": turmas_qs.filter(turmas_regular_filter).count(),
            "regular_alunos_total": _alunos_distintos_por_turma(turmas_regular_filter),
            "fundamental_turmas_total": turmas_qs.filter(turmas_fundamental_filter).count(),
            "fundamental_alunos_total": _alunos_distintos_por_turma(turmas_fundamental_filter),
            "complementar_turmas_total": turmas_complementares_total,
            "complementar_alunos_total": _alunos_distintos_por_turma(turmas_complementar_filter),
        },
        "cursos_catalogo_total": cursos_catalogo_total,
        "cursos_complementares_total": cursos_complementares_total,
        "cursos_ativos_total": cursos_ativos_total,
        "cursos_inativos_total": cursos_inativos_total,
        "modalidades_total": turmas_qs.values("modalidade").distinct().count(),
        "profissionais": profissionais,
        "frequencia": frequencia,
        "pedagogico": pedagogico,
        "documentos": documentos,
        "eventos_total": eventos_qs.count(),
        "eventos_letivos_total": eventos_qs.filter(dia_letivo=True).count(),
        "feriados_total": eventos_qs.filter(tipo=CalendarioEducacionalEvento.Tipo.FERIADO).count(),
        "recessos_total": eventos_qs.filter(tipo=CalendarioEducacionalEvento.Tipo.RECESSO).count(),
        "proximos_eventos": list(
            eventos_qs.filter(data_inicio__gte=today).order_by("data_inicio", "titulo")[:8]
        ),
        "unidades_destaque": unidades_destaque,
        "modalidades_destaque": modalidades_destaque,
        "assistencia": assistencia,
        "beneficios": beneficios,
        "nee": nee,
    }


def _build_student_calendar_context(eventos, ref_date):
    meses_pt = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ]
    semana_labels = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    month_start = ref_date.replace(day=1)
    last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
    month_end = ref_date.replace(day=last_day)

    tipo_prioridade = {
        "FERIADO": 100,
        "RECESSO": 90,
        "FACULTATIVO": 80,
        "PEDAGOGICO": 70,
        "PLANEJAMENTO": 60,
        "COMEMORATIVA": 50,
        "BIMESTRE_INICIO": 40,
        "BIMESTRE_FIM": 35,
        "LETIVO": 20,
        "OUTRO": 10,
    }
    event_type_by_day: dict[int, str] = {}
    for ev in eventos:
        ev_start = ev.data_inicio
        ev_end = ev.data_fim or ev.data_inicio
        start = max(ev_start, month_start)
        end = min(ev_end, month_end)
        cursor = start
        while cursor <= end:
            day = cursor.day
            tipo = (getattr(ev, "tipo", "") or "OUTRO").upper()
            current_tipo = event_type_by_day.get(day)
            if current_tipo is None:
                event_type_by_day[day] = tipo
            else:
                if tipo_prioridade.get(tipo, 0) > tipo_prioridade.get(current_tipo, 0):
                    event_type_by_day[day] = tipo
            cursor += timedelta(days=1)

    cal = calendar.Calendar(firstweekday=6)
    weeks = []
    for week in cal.monthdayscalendar(ref_date.year, ref_date.month):
        row = []
        for day in week:
            in_month = day > 0
            day_tipo = event_type_by_day.get(day) if in_month else None
            row.append(
                {
                    "day": day if in_month else "",
                    "is_today": in_month and day == ref_date.day,
                    "has_event": bool(in_month and day_tipo),
                    "event_type": (day_tipo or "").lower(),
                }
            )
        weeks.append(row)

    return {
        "mes_label": f"{meses_pt[ref_date.month - 1]} de {ref_date.year}",
        "semana_labels": semana_labels,
        "weeks": weeks,
    }


def _scope_by_profile(qs, profile):
    if not profile:
        return qs
    if getattr(profile, "municipio_id", None):
        if "municipio_id" in [f.name for f in qs.model._meta.fields]:
            qs = qs.filter(municipio_id=profile.municipio_id)
    if getattr(profile, "secretaria_id", None):
        if "secretaria_id" in [f.name for f in qs.model._meta.fields]:
            qs = qs.filter(secretaria_id=profile.secretaria_id)
    if getattr(profile, "unidade_id", None):
        if "unidade_id" in [f.name for f in qs.model._meta.fields]:
            qs = qs.filter(unidade_id=profile.unidade_id)
    return qs


def _build_central_pendencias(user, profile):
    pendencias = []
    hoje = timezone.localdate()
    em_30 = hoje + timezone.timedelta(days=30)

    try:
        processos_qs = _scope_by_profile(ProcessoAdministrativo.objects.all(), profile)
        atrasados = processos_qs.exclude(
            status__in=[ProcessoAdministrativo.Status.CONCLUIDO, ProcessoAdministrativo.Status.ARQUIVADO]
        ).filter(prazo_final__lt=hoje).count()
        if atrasados:
            pendencias.append(
                {
                    "titulo": "Processos em atraso",
                    "valor": atrasados,
                    "url": "/processos/",
                    "nivel": "alto",
                    "descricao": "Processos com prazo final vencido.",
                }
            )
    except Exception:
        pass

    try:
        req_qs = _scope_by_profile(RequisicaoCompra.objects.all(), profile)
        em_aprovacao = req_qs.filter(status=RequisicaoCompra.Status.EM_APROVACAO).count()
        if em_aprovacao:
            pendencias.append(
                {
                    "titulo": "Requisições em aprovação",
                    "valor": em_aprovacao,
                    "url": "/compras/requisicoes/",
                    "nivel": "medio",
                    "descricao": "Requisições aguardando decisão.",
                }
            )
    except Exception:
        pass

    try:
        if profile and getattr(profile, "municipio_id", None):
            contrato_qs = ContratoAdministrativo.objects.filter(municipio_id=profile.municipio_id)
        else:
            contrato_qs = ContratoAdministrativo.objects.all()

        vencendo = contrato_qs.filter(
            status=ContratoAdministrativo.Status.ATIVO,
            vigencia_fim__gte=hoje,
            vigencia_fim__lte=em_30,
        ).count()
        vencidos = contrato_qs.filter(
            status=ContratoAdministrativo.Status.ATIVO,
            vigencia_fim__lt=hoje,
        ).count()

        if vencidos:
            pendencias.append(
                {
                    "titulo": "Contratos vencidos",
                    "valor": vencidos,
                    "url": "/contratos/",
                    "nivel": "alto",
                    "descricao": "Contratos ativos com vigência já encerrada.",
                }
            )
        if vencendo:
            pendencias.append(
                {
                    "titulo": "Contratos vencendo em 30 dias",
                    "valor": vencendo,
                    "url": "/contratos/",
                    "nivel": "medio",
                    "descricao": "Planejar aditivos/renovações.",
                }
            )
    except Exception:
        pass

    try:
        med_qs = MedicaoContrato.objects.select_related("contrato")
        if profile and getattr(profile, "municipio_id", None):
            med_qs = med_qs.filter(contrato__municipio_id=profile.municipio_id)
        pendentes = med_qs.filter(status=MedicaoContrato.Status.PENDENTE).count()
        if pendentes:
            pendencias.append(
                {
                    "titulo": "Medições pendentes de atesto",
                    "valor": pendentes,
                    "url": "/contratos/",
                    "nivel": "medio",
                    "descricao": "Medições aguardando atesto/liquidação.",
                }
            )
    except Exception:
        pass

    try:
        ouv_qs = _scope_by_profile(OuvidoriaCadastro.objects.all(), profile)
        ouv_atrasadas = ouv_qs.exclude(
            status__in=[
                OuvidoriaCadastro.Status.CONCLUIDO,
                OuvidoriaCadastro.Status.CANCELADO,
                OuvidoriaCadastro.Status.RESPONDIDO,
            ]
        ).filter(prazo_resposta__lt=hoje).count()
        if ouv_atrasadas:
            pendencias.append(
                {
                    "titulo": "Ouvidorias com SLA vencido",
                    "valor": ouv_atrasadas,
                    "url": "/ouvidoria/",
                    "nivel": "alto",
                    "descricao": "Chamados com prazo de resposta vencido.",
                }
            )
    except Exception:
        pass

    try:
        if profile and getattr(profile, "municipio_id", None):
            dataset_qs = Dataset.objects.filter(municipio_id=profile.municipio_id)
        else:
            dataset_qs = Dataset.objects.all()
        dataset_sensiveis = (
            dataset_qs.exclude(status=Dataset.Status.PUBLICADO)
            .filter(visibilidade=Dataset.Visibilidade.PUBLICO, versoes__colunas__sensivel=True)
            .distinct()
            .count()
        )
        if dataset_sensiveis:
            pendencias.append(
                {
                    "titulo": "Datasets públicos com coluna sensível",
                    "valor": dataset_sensiveis,
                    "url": "/paineis/",
                    "nivel": "medio",
                    "descricao": "Revisar checklist LGPD antes da publicação.",
                }
            )
    except Exception:
        pass

    try:
        if profile and getattr(profile, "municipio_id", None):
            jobs_qs = NotificationJob.objects.filter(municipio_id=profile.municipio_id)
        else:
            jobs_qs = NotificationJob.objects.all()
        jobs_falhos = jobs_qs.filter(
            status=NotificationJob.Status.FALHA,
            created_at__date=hoje,
        ).count()
        if jobs_falhos:
            pendencias.append(
                {
                    "titulo": "Falhas de comunicação hoje",
                    "valor": jobs_falhos,
                    "url": "/comunicacao/",
                    "nivel": "medio",
                    "descricao": "Jobs com erro no dia atual.",
                }
            )
    except Exception:
        pass

    pendencias.sort(key=lambda item: (0 if item["nivel"] == "alto" else 1, -int(item["valor"])))
    return pendencias


def portal_manage_allowed(user) -> bool:
    p = get_profile(user)
    return bool(
        can(user, "educacao.manage")
        or can(user, "org.manage_unidade")
        or can(user, "org.manage_secretaria")
        or can(user, "org.manage_municipio")
        or (p and is_professor_profile_role(p.role))
        or is_admin(user)
    )


def _render_secretaria_educacao_painel(
    request,
    *,
    dash_template: str,
    page_subtitle: str,
    extra_context: dict | None = None,
):
    user = request.user
    profile = get_profile(user)
    role = (getattr(profile, "role", "") or "").upper()
    if role != "EDU_SECRETARIO":
        return HttpResponseForbidden("Acesso restrito ao perfil da Secretaria de Educação.")

    central_pendencias = _build_central_pendencias(user, profile)
    ctx = {
        "page_title": "Dashboard",
        "page_subtitle": page_subtitle,
        "show_page_head": False,
        "central_pendencias": central_pendencias,
        "central_pendencias_total": len(central_pendencias),
        "dash_template": dash_template,
        "secretaria_nome": getattr(getattr(profile, "secretaria", None), "nome", "—"),
        "secretaria_informatica": _build_informatica_scope_data(profile),
        "secretaria_educacao": _build_secretaria_educacao_scope_data(user, profile),
    }
    if extra_context:
        ctx.update(extra_context)
    return render(request, "core/dashboard.html", ctx)


def _secretaria_educacao_scope_querysets(user):
    unidades_qs = scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    ).select_related("secretaria", "secretaria__municipio")
    turmas_qs = scope_filter_turmas(
        user,
        Turma.objects.filter(unidade__tipo=Unidade.Tipo.EDUCACAO),
    ).select_related("unidade", "unidade__secretaria", "curso")
    matriculas_qs = scope_filter_matriculas(
        user,
        Matricula.objects.filter(turma__unidade__tipo=Unidade.Tipo.EDUCACAO),
    ).select_related("aluno", "turma", "turma__unidade")
    alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
    return {
        "unidades_qs": unidades_qs,
        "turmas_qs": turmas_qs,
        "matriculas_qs": matriculas_qs,
        "alunos_qs": alunos_qs,
    }


@login_required
def secretaria_educacao_visao_geral(request):
    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_visao_geral.html",
        page_subtitle="Secretaria de Educação • Visão Geral da Rede",
    )


@login_required
def secretaria_educacao_modalidades(request):
    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_modalidades.html",
        page_subtitle="Secretaria de Educação • Modalidades de Ensino",
    )


@login_required
def secretaria_educacao_frequencia(request):
    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_frequencia.html",
        page_subtitle="Secretaria de Educação • Frequência",
    )


@login_required
def secretaria_educacao_desempenho(request):
    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_desempenho.html",
        page_subtitle="Secretaria de Educação • Desempenho Pedagógico",
    )


@login_required
def secretaria_educacao_profissionais(request):
    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_profissionais.html",
        page_subtitle="Secretaria de Educação • Profissionais da Educação",
    )


@login_required
def secretaria_educacao_documentos(request):
    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_documentos.html",
        page_subtitle="Secretaria de Educação • Documentos Institucionais",
    )


@login_required
def secretaria_educacao_escolas(request):
    scope = _secretaria_educacao_scope_querysets(request.user)
    unidades_qs = scope["unidades_qs"]
    turmas_qs = scope["turmas_qs"]
    matriculas_qs = scope["matriculas_qs"]

    unidade_ids = list(unidades_qs.values_list("id", flat=True))
    turmas_por_unidade = {
        unidade_id: int(total)
        for unidade_id, total in turmas_qs.values_list("unidade_id").annotate(total=Count("id"))
    }
    alunos_ativos_por_unidade = {
        unidade_id: int(total)
        for unidade_id, total in (
            matriculas_qs.filter(situacao=Matricula.Situacao.ATIVA)
            .values_list("turma__unidade_id")
            .annotate(total=Count("aluno_id", distinct=True))
        )
    }

    unidades_rows = []
    for unidade in unidades_qs.order_by("nome")[:250]:
        unidades_rows.append(
            {
                "id": unidade.id,
                "nome": unidade.nome,
                "municipio": getattr(getattr(unidade.secretaria, "municipio", None), "nome", "—"),
                "tipo_educacional": unidade.get_tipo_educacional_display(),
                "ativo": unidade.ativo,
                "turmas_total": turmas_por_unidade.get(unidade.id, 0),
                "alunos_ativos_total": alunos_ativos_por_unidade.get(unidade.id, 0),
            }
        )
    unidades_rows.sort(key=lambda row: (-row["alunos_ativos_total"], -row["turmas_total"], row["nome"]))

    escolas_com_turmas = sum(1 for row in unidades_rows if row["turmas_total"] > 0)
    escolas_sem_turmas = max(0, len(unidades_rows) - escolas_com_turmas)
    escolas_ativas = sum(1 for row in unidades_rows if row["ativo"])
    escolas_inativas = max(0, len(unidades_rows) - escolas_ativas)

    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_escolas.html",
        page_subtitle="Secretaria de Educação • Escolas",
        extra_context={
            "escolas_rows": unidades_rows,
            "escolas_total": len(unidades_rows),
            "escolas_com_turmas": escolas_com_turmas,
            "escolas_sem_turmas": escolas_sem_turmas,
            "escolas_ativas": escolas_ativas,
            "escolas_inativas": escolas_inativas,
            "escolas_ids": unidade_ids,
        },
    )


@login_required
def secretaria_educacao_alunos(request):
    scope = _secretaria_educacao_scope_querysets(request.user)
    alunos_qs = scope["alunos_qs"]
    matriculas_qs = scope["matriculas_qs"]

    matriculas_ativas = matriculas_qs.filter(situacao=Matricula.Situacao.ATIVA).order_by("aluno__nome", "-id")
    alunos_rows = []
    seen_aluno_ids: set[int] = set()
    for matricula in matriculas_ativas[:800]:
        if matricula.aluno_id in seen_aluno_ids:
            continue
        seen_aluno_ids.add(matricula.aluno_id)
        turma = getattr(matricula, "turma", None)
        unidade = getattr(turma, "unidade", None) if turma else None
        alunos_rows.append(
            {
                "aluno_id": matricula.aluno_id,
                "nome": getattr(matricula.aluno, "nome", "—"),
                "aluno_ativo": bool(getattr(matricula.aluno, "ativo", False)),
                "turma": getattr(turma, "nome", "—"),
                "turno": turma.get_turno_display() if turma else "—",
                "modalidade": turma.get_modalidade_display() if turma else "—",
                "unidade": getattr(unidade, "nome", "—"),
                "data_matricula": matricula.data_matricula,
                "situacao": matricula.get_situacao_display(),
            }
        )
        if len(alunos_rows) >= 250:
            break

    alunos_ids_com_matricula = set(matriculas_qs.values_list("aluno_id", flat=True).distinct())
    alunos_sem_matricula = alunos_qs.exclude(id__in=alunos_ids_com_matricula).count()

    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_alunos.html",
        page_subtitle="Secretaria de Educação • Alunos",
        extra_context={
            "alunos_rows": alunos_rows,
            "alunos_rows_total": len(alunos_rows),
            "alunos_sem_matricula_total": int(alunos_sem_matricula),
        },
    )


@login_required
def secretaria_educacao_turmas(request):
    scope = _secretaria_educacao_scope_querysets(request.user)
    turmas_qs = scope["turmas_qs"]
    matriculas_qs = scope["matriculas_qs"]

    matriculados_por_turma = {
        turma_id: int(total)
        for turma_id, total in (
            matriculas_qs.filter(situacao=Matricula.Situacao.ATIVA)
            .values_list("turma_id")
            .annotate(total=Count("aluno_id", distinct=True))
        )
    }

    turmas_rows = []
    for turma in turmas_qs.order_by("-ano_letivo", "nome")[:400]:
        turmas_rows.append(
            {
                "id": turma.id,
                "nome": turma.nome,
                "ano_letivo": turma.ano_letivo,
                "unidade": getattr(getattr(turma, "unidade", None), "nome", "—"),
                "turno": turma.get_turno_display(),
                "modalidade": turma.get_modalidade_display(),
                "etapa": turma.get_etapa_display(),
                "serie_ano": turma.get_serie_ano_display(),
                "ativo": turma.ativo,
                "curso": getattr(getattr(turma, "curso", None), "nome", "—"),
                "matriculados_ativos": matriculados_por_turma.get(turma.id, 0),
            }
        )

    turmas_ativas = sum(1 for row in turmas_rows if row["ativo"])
    turmas_inativas = max(0, len(turmas_rows) - turmas_ativas)

    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_turmas.html",
        page_subtitle="Secretaria de Educação • Turmas",
        extra_context={
            "turmas_rows": turmas_rows,
            "turmas_rows_total": len(turmas_rows),
            "turmas_ativas_total": turmas_ativas,
            "turmas_inativas_total": turmas_inativas,
        },
    )


@login_required
def secretaria_educacao_cursos(request):
    scope = _secretaria_educacao_scope_querysets(request.user)
    turmas_qs = scope["turmas_qs"]
    matriculas_qs = scope["matriculas_qs"]

    cursos_ids = list(turmas_qs.exclude(curso_id__isnull=True).values_list("curso_id", flat=True).distinct())
    cursos_qs = Curso.objects.filter(id__in=cursos_ids).order_by("nome")

    turmas_por_curso = {
        curso_id: int(total)
        for curso_id, total in (
            turmas_qs.filter(curso_id__in=cursos_ids).values_list("curso_id").annotate(total=Count("id"))
        )
    }
    turmas_ativas_por_curso = {
        curso_id: int(total)
        for curso_id, total in (
            turmas_qs.filter(curso_id__in=cursos_ids, ativo=True).values_list("curso_id").annotate(total=Count("id"))
        )
    }
    alunos_ativos_por_curso = {
        curso_id: int(total)
        for curso_id, total in (
            matriculas_qs.filter(
                situacao=Matricula.Situacao.ATIVA,
                turma__curso_id__in=cursos_ids,
            )
            .values_list("turma__curso_id")
            .annotate(total=Count("aluno_id", distinct=True))
        )
    }

    cursos_rows = []
    for curso in cursos_qs[:250]:
        cursos_rows.append(
            {
                "id": curso.id,
                "nome": curso.nome,
                "codigo": curso.codigo or "—",
                "modalidade_oferta": curso.get_modalidade_oferta_display(),
                "carga_horaria": curso.carga_horaria,
                "ativo": curso.ativo,
                "turmas_total": turmas_por_curso.get(curso.id, 0),
                "turmas_ativas_total": turmas_ativas_por_curso.get(curso.id, 0),
                "alunos_ativos_total": alunos_ativos_por_curso.get(curso.id, 0),
            }
        )

    cursos_ativos = sum(1 for row in cursos_rows if row["ativo"])
    cursos_inativos = max(0, len(cursos_rows) - cursos_ativos)

    return _render_secretaria_educacao_painel(
        request,
        dash_template="core/dashboards/partials/secretaria_educacao_cursos.html",
        page_subtitle="Secretaria de Educação • Cursos",
        extra_context={
            "cursos_rows": cursos_rows,
            "cursos_rows_total": len(cursos_rows),
            "cursos_ativos_total": cursos_ativos,
            "cursos_inativos_total": cursos_inativos,
        },
    )


@login_required
def dashboard_view(request):
    user = request.user
    p = get_profile(user)
    central_pendencias = _build_central_pendencias(user, p)

    base_ctx = {
        "page_title": "Dashboard",
        "page_subtitle": "Visão geral",
        "show_page_head": False,
        "central_pendencias": central_pendencias,
        "central_pendencias_total": len(central_pendencias),
    }

    if is_admin(user):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        kpis = {
            "municipios": Municipio.objects.count(),
            "usuarios": User.objects.count(),
            "secretarias": Secretaria.objects.count(),
            "unidades": Unidade.objects.count(),
            "setores": Setor.objects.count(),
            "turmas": Turma.objects.count(),
            "alunos": Aluno.objects.count(),
            "matriculas": Matricula.objects.count(),
        }

        roles_qs = Profile.objects.values("role").annotate(total=Count("id")).order_by("-total")
        role_labels = [r["role"] or "SEM_ROLE" for r in roles_qs]
        role_values = [r["total"] for r in roles_qs]
        chart_roles = {"labels": json.dumps(role_labels), "values": json.dumps(role_values)}

        unidades_por_municipio = list(
            Unidade.objects.values("secretaria__municipio_id", "secretaria__municipio__nome")
            .annotate(unidades=Count("id"))
            .order_by("-unidades")
        )

        secretarias_por_municipio = list(
            Secretaria.objects.values("municipio_id", "municipio__nome")
            .annotate(secretarias=Count("id"))
            .order_by("-secretarias")
        )

        resumo_por_municipio: dict[int, dict] = {}
        for row in secretarias_por_municipio:
            mid = int(row["municipio_id"])
            resumo_por_municipio[mid] = {
                "id": mid,
                "nome": row["municipio__nome"] or "—",
                "secretarias": int(row["secretarias"] or 0),
                "unidades": 0,
            }

        for row in unidades_por_municipio:
            mid = int(row["secretaria__municipio_id"])
            current = resumo_por_municipio.setdefault(
                mid,
                {
                    "id": mid,
                    "nome": row["secretaria__municipio__nome"] or "—",
                    "secretarias": 0,
                    "unidades": 0,
                },
            )
            current["nome"] = current["nome"] or row["secretaria__municipio__nome"] or "—"
            current["unidades"] = int(row["unidades"] or 0)

        resumo_values = list(resumo_por_municipio.values())
        max_secretarias = max((item["secretarias"] for item in resumo_values), default=0)
        max_unidades = max((item["unidades"] for item in resumo_values), default=0)

        for item in resumo_values:
            sec_component = (item["secretarias"] / max_secretarias) if max_secretarias else 0
            uni_component = (item["unidades"] / max_unidades) if max_unidades else 0
            item["volume_score"] = round(((sec_component * 0.45) + (uni_component * 0.55)) * 100, 1)

        top_municipios = sorted(
            resumo_values,
            key=lambda item: (item["volume_score"], item["unidades"], item["secretarias"]),
            reverse=True,
        )[:10]

        top_unidades_raw = list(
            Turma.objects.values("unidade_id", "unidade__nome")
            .annotate(turmas=Count("id"))
            .order_by("-turmas", "unidade__nome")[:10]
        )
        top_unidades = [{"id": r["unidade_id"], "nome": r["unidade__nome"] or "—", "turmas": r["turmas"]} for r in top_unidades_raw]

        chart_municipios = {
            "labels": json.dumps([m["nome"] for m in top_municipios]),
            "values": json.dumps([m["unidades"] for m in top_municipios]),
        }

        ctx = {
            **base_ctx,
            "page_subtitle": "Visão geral do sistema",
            "dash_template": "core/dashboards/partials/admin.html",
            "kpis": kpis,
            "chart_roles": chart_roles,
            "chart_municipios": chart_municipios,
            "top_municipios": top_municipios,
            "top_unidades": top_unidades,
            "can_nee": True,
            "can_users": True,
            "ultimos_municipios": Municipio.objects.order_by("-id")[:5],
        }
        return render(request, "core/dashboard.html", ctx)

    if not p or not getattr(p, "ativo", True):
        return render(request, "core/dashboard.html", {**base_ctx, "dash_template": "core/dashboards/partials/default.html"})

    role = (p.role or "").upper()
    role_base = role_scope_base(role)

    if role_base == "MUNICIPAL":
        try:
            wizard_done = MunicipioOnboardingWizard.objects.filter(
                user_id=user.id,
                completed_at__isnull=False,
            ).exists()
            has_steps = OnboardingStep.objects.filter(municipio_id=p.municipio_id).exists()
            has_provision = SecretariaProvisionamento.objects.filter(municipio_id=p.municipio_id).exists()
            if (not wizard_done) and (not has_steps and not has_provision):
                return redirect("org:onboarding_wizard")
        except (ProgrammingError, OperationalError):
            pass

    if role_base == "ALUNO":
        if not getattr(p, "aluno_id", None):
            return render(request, "core/dashboard.html", {
                **base_ctx,
                "page_subtitle": "Meu painel",
                "dash_template": "core/dashboards/partials/aluno.html",
                "sem_vinculo": True,
                "avisos": [],
                "arquivos": [],
                "eventos_calendario": [],
            })

        aluno_id = p.aluno_id

        matriculas = Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        ).filter(aluno_id=aluno_id)

        turma_ids = list(matriculas.values_list("turma_id", flat=True))
        unidade_ids = list(matriculas.values_list("turma__unidade_id", flat=True))
        secretaria_ids = list(matriculas.values_list("turma__unidade__secretaria_id", flat=True))
        municipio_ids = list(matriculas.values_list("turma__unidade__secretaria__municipio_id", flat=True))

        avisos = (
            AlunoAviso.objects.filter(ativo=True)
            .filter(
                Q(aluno_id=aluno_id)
                | Q(turma_id__in=turma_ids)
                | Q(unidade_id__in=unidade_ids)
                | Q(secretaria_id__in=secretaria_ids)
                | Q(municipio_id__in=municipio_ids)
            )
            .select_related("autor")
            .order_by("-criado_em")[:20]
        )

        arquivos = (
            AlunoArquivo.objects.filter(ativo=True)
            .filter(
                Q(aluno_id=aluno_id)
                | Q(turma_id__in=turma_ids)
                | Q(unidade_id__in=unidade_ids)
                | Q(secretaria_id__in=secretaria_ids)
                | Q(municipio_id__in=municipio_ids)
            )
            .select_related("autor")
            .order_by("-criado_em")[:20]
        )

        eventos_calendario = CalendarioEducacionalEvento.objects.none()
        if secretaria_ids:
            try:
                eventos_calendario = (
                    CalendarioEducacionalEvento.objects.filter(
                        ativo=True,
                        secretaria_id__in=secretaria_ids,
                        data_fim__gte=timezone.localdate(),
                    )
                    .filter(Q(unidade__isnull=True) | Q(unidade_id__in=unidade_ids))
                    .order_by("data_inicio", "titulo")
                )
            except (ProgrammingError, OperationalError):
                eventos_calendario = CalendarioEducacionalEvento.objects.none()

        eventos_lista = list(eventos_calendario[:8])
        calendario_ctx = _build_student_calendar_context(eventos_lista, timezone.localdate())
        aluno_code = (getattr(p, "codigo_acesso", "") or user.username) if p else user.username

        informatica_matriculas = list(
            InformaticaMatricula.objects.select_related(
                "turma",
                "turma__curso",
                "turma__laboratorio",
                "turma__laboratorio__unidade",
            )
            .filter(
                aluno_id=aluno_id,
                status=InformaticaMatricula.Status.MATRICULADO,
                turma__status__in=["PLANEJADA", "ATIVA"],
            )
            .order_by("-id")[:20]
        )
        informatica_turma_ids = [m.turma_id for m in informatica_matriculas if m.turma_id]
        informatica_proximas_aulas = []
        informatica_faltas_abertas = 0
        informatica_alertas = 0
        if informatica_turma_ids:
            informatica_proximas_aulas = list(
                InformaticaAulaDiario.objects.select_related("turma", "encontro")
                .filter(
                    turma_id__in=informatica_turma_ids,
                    data_aula__gte=timezone.localdate(),
                )
                .exclude(status=InformaticaAulaDiario.Status.CANCELADA)
                .order_by("data_aula", "encontro__hora_inicio", "id")[:12]
            )
            informatica_faltas_abertas = (
                InformaticaFrequencia.objects.filter(
                    aluno_id=aluno_id,
                    aula__turma_id__in=informatica_turma_ids,
                    presente=False,
                )
                .filter(Q(justificativa__isnull=True) | Q(justificativa=""))
                .count()
            )
            informatica_alertas = InformaticaAlertaFrequencia.objects.filter(
                ativo=True,
                matricula__aluno_id=aluno_id,
                matricula__status=InformaticaMatricula.Status.MATRICULADO,
                matricula__turma_id__in=informatica_turma_ids,
            ).count()

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Meu painel",
            "dash_template": "core/dashboards/partials/aluno.html",
            "sem_vinculo": False,
            "avisos": avisos,
            "arquivos": arquivos,
            "eventos_calendario": eventos_lista,
            "student_calendario": calendario_ctx,
            "aluno_code": aluno_code,
            "meus_dados_url": reverse("educacao:aluno_meus_dados", args=[aluno_code]),
            "aluno_documentos_processos_url": reverse("educacao:aluno_documentos_processos", args=[aluno_code]),
            "aluno_ensino_url": reverse("educacao:aluno_ensino", args=[aluno_code]),
            "aluno_ensino_horarios_url": reverse("educacao:aluno_ensino_horarios", args=[aluno_code]),
            "aluno_ensino_justificativa_url": reverse("educacao:aluno_ensino_justificativa", args=[aluno_code]),
            "aluno_ensino_mensagens_url": reverse("educacao:aluno_ensino_mensagens", args=[aluno_code]),
            "informatica_matriculas": informatica_matriculas,
            "informatica_proximas_aulas": informatica_proximas_aulas,
            "informatica_faltas_abertas": informatica_faltas_abertas,
            "informatica_alertas": informatica_alertas,
        })

    if role_base == "PROFESSOR":
        ano_atual = timezone.now().date().year
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade").order_by("-ano_letivo", "nome")
        alunos_total = Matricula.objects.filter(turma__in=turmas_qs).values("aluno_id").distinct().count()
        diarios_qs = DiarioTurma.objects.select_related("turma", "turma__unidade").filter(
            professor=user,
            turma__in=turmas_qs,
        ).order_by("-ano_letivo", "turma__nome")
        diarios_ids = list(diarios_qs.values_list("id", flat=True))
        aulas_total = Aula.objects.filter(diario_id__in=diarios_ids).count() if diarios_ids else 0
        pendencias_total = (
            JustificativaFaltaPedido.objects.filter(
                aula__diario_id__in=diarios_ids,
                status=JustificativaFaltaPedido.Status.PENDENTE,
            ).count()
            if diarios_ids
            else 0
        )
        secretaria_ids = list(turmas_qs.values_list("unidade__secretaria_id", flat=True).distinct())
        unidade_ids = list(turmas_qs.values_list("unidade_id", flat=True).distinct())

        eventos_calendario = CalendarioEducacionalEvento.objects.none()
        if secretaria_ids:
            try:
                eventos_calendario = (
                    CalendarioEducacionalEvento.objects.filter(
                        ativo=True,
                        secretaria_id__in=secretaria_ids,
                        data_fim__gte=timezone.localdate(),
                    )
                    .filter(Q(unidade__isnull=True) | Q(unidade_id__in=unidade_ids))
                    .order_by("data_inicio", "titulo")
                )
            except (ProgrammingError, OperationalError):
                eventos_calendario = CalendarioEducacionalEvento.objects.none()
        eventos_lista = list(eventos_calendario[:8])
        calendario_ctx = _build_student_calendar_context(eventos_lista, timezone.localdate())

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Minhas turmas e alunos",
            "dash_template": "core/dashboards/partials/professor.html",
            "turmas": turmas_qs.filter(ano_letivo=ano_atual)[:8],
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_total,
            "ano_atual": ano_atual,
            "diarios_total": len(diarios_ids),
            "aulas_total": aulas_total,
            "pendencias_total": pendencias_total,
            "professor_code": (getattr(p, "codigo_acesso", "") or user.username) if p else user.username,
            "eventos_calendario": eventos_lista,
            "student_calendario": calendario_ctx,
            "diarios_preview": list(diarios_qs[:6]),
        })

    if role_base == "MUNICIPAL":
        secretarias_qs = scope_filter_secretarias(user, Secretaria.objects.all()).select_related("municipio")
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria", "secretaria__municipio")

        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_unidades_por_secretaria = list(
            Unidade.objects.filter(secretaria__in=secretarias_qs)
            .values("secretaria__nome").annotate(total=Count("id")).order_by("-total")[:8]
        )
        graf_alunos_por_secretaria = list(
            Matricula.objects.filter(turma__unidade__secretaria__in=secretarias_qs)
            .values("turma__unidade__secretaria__nome")
            .annotate(total=Count("aluno", distinct=True))
            .order_by("-total")[:8]
        )

        onboarding_total_steps = 0
        onboarding_done_steps = 0
        onboarding_modules_active = 0
        try:
            onboarding_steps_qs = OnboardingStep.objects.filter(municipio_id=p.municipio_id)
            onboarding_total_steps = onboarding_steps_qs.count()
            onboarding_done_steps = onboarding_steps_qs.filter(status=OnboardingStep.Status.CONCLUIDO).count()
            onboarding_modules_active = MunicipioModuloAtivo.objects.filter(
                municipio_id=p.municipio_id,
                ativo=True,
            ).count()
        except (ProgrammingError, OperationalError):
            onboarding_total_steps = 0
            onboarding_done_steps = 0
            onboarding_modules_active = 0

        ctx = {
            **base_ctx,
            "page_subtitle": "Visão municipal",
            "dash_template": "core/dashboards/partials/municipal.html",
            "municipio_nome": getattr(p.municipio, "nome", "—") if getattr(p, "municipio_id", None) else "—",
            "secretarias_total": secretarias_qs.count(),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "ultimas_secretarias": secretarias_qs.order_by("-id")[:5],
            "ultimos_alunos": alunos_qs.prefetch_related("matriculas__turma__unidade").order_by("-id")[:5],
            "chart1_labels": [i["secretaria__nome"] for i in graf_unidades_por_secretaria],
            "chart1_values": [i["total"] for i in graf_unidades_por_secretaria],
            "chart2_labels": [i["turma__unidade__secretaria__nome"] for i in graf_alunos_por_secretaria],
            "chart2_values": [i["total"] for i in graf_alunos_por_secretaria],
            "onboarding_total_steps": onboarding_total_steps,
            "onboarding_done_steps": onboarding_done_steps,
            "onboarding_modules_active": onboarding_modules_active,
            "onboarding_url": "/org/onboarding/",
        }
        return render(request, "core/dashboard.html", ctx)

    if role_base == "SECRETARIA":
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria")
        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_turmas_por_unidade = list(
            turmas_qs.values("unidade__nome").annotate(total=Count("id")).order_by("-total")[:8]
        )

        if role == "EDU_SECRETARIO":
            secretaria_informatica = _build_informatica_scope_data(p)
            secretaria_educacao = _build_secretaria_educacao_scope_data(user, p)
            return render(
                request,
                "core/dashboard.html",
                {
                    **base_ctx,
                    "page_subtitle": "Secretaria de Educação • Painel Integrado (somente leitura)",
                    "dash_template": "core/dashboards/partials/secretaria_informatica.html",
                    "secretaria_nome": getattr(getattr(p, "secretaria", None), "nome", "—"),
                    "secretaria_informatica": secretaria_informatica,
                    "secretaria_educacao": secretaria_educacao,
                },
            )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Visão da secretaria",
            "dash_template": "core/dashboards/partials/secretaria.html",
            "secretaria_nome": getattr(getattr(p, "secretaria", None), "nome", "—"),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "unidades": unidades_qs.order_by("nome")[:10],
            "graf_turmas_por_unidade": graf_turmas_por_unidade,
        })

    if role_base == "UNIDADE":
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade")
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all()).select_related("turma")

        graf_matriculas_por_turma = list(
            matriculas_qs.values("turma__nome").annotate(total=Count("id")).order_by("-total")[:10]
        )

        if role == "EDU_COORD":
            coordenacao_informatica = _build_informatica_scope_data(p)
            return render(
                request,
                "core/dashboard.html",
                {
                    **base_ctx,
                    "page_subtitle": "Coordenação de Informática",
                    "dash_template": "core/dashboards/partials/coordenacao_informatica.html",
                    "unidade_nome": getattr(getattr(p, "unidade", None), "nome", "—"),
                    "coordenacao_informatica": coordenacao_informatica,
                },
            )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Visão da unidade",
            "dash_template": "core/dashboards/partials/unidade.html",
            "unidade_nome": getattr(getattr(p, "unidade", None), "nome", "—"),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "turmas": turmas_qs.order_by("-ano_letivo", "nome")[:10],
            "graf_matriculas_por_turma": graf_matriculas_por_turma,
        })

    return render(request, "core/dashboard.html", {**base_ctx, "dash_template": "core/dashboards/partials/default.html"})


@login_required
def dashboard_aluno(request):
    return redirect("core:dashboard")


@login_required
def aviso_create(request):
    if not portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoAvisoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        aviso = form.save(commit=False)
        aviso.autor = request.user
        aviso.save()
        messages.success(request, "Aviso publicado.")
        return redirect("core:dashboard")

    return render(request, "core/aviso_form.html", {"form": form})


@login_required
def arquivo_create(request):
    if not portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoArquivoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        arq = form.save(commit=False)
        arq.autor = request.user
        arq.save()
        messages.success(request, "Arquivo enviado.")
        return redirect("core:dashboard")

    return render(request, "core/arquivo_form.html", {"form": form})
