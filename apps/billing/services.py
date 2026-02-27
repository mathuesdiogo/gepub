from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Profile
from apps.educacao.models import Matricula
from apps.org.models import Municipio, Secretaria
from apps.saude.models import AtendimentoSaude

from .models import (
    AddonCatalogo,
    AssinaturaAddon,
    AssinaturaMunicipio,
    AssinaturaQuotaExtra,
    FaturaMunicipio,
    PlanoMunicipal,
    SolicitacaoUpgrade,
    UsoMunicipio,
)


class MetricaLimite:
    SECRETARIAS = "SECRETARIAS"
    USUARIOS = "USUARIOS"
    ALUNOS = "ALUNOS"
    ATENDIMENTOS = "ATENDIMENTOS"


METRICA_LABEL = {
    MetricaLimite.SECRETARIAS: "secretarias",
    MetricaLimite.USUARIOS: "usuários",
    MetricaLimite.ALUNOS: "alunos",
    MetricaLimite.ATENDIMENTOS: "atendimentos",
}

METRICA_TO_QUOTA = {
    MetricaLimite.SECRETARIAS: AssinaturaQuotaExtra.Tipo.SECRETARIAS,
    MetricaLimite.USUARIOS: AssinaturaQuotaExtra.Tipo.USUARIOS,
    MetricaLimite.ALUNOS: AssinaturaQuotaExtra.Tipo.ALUNOS,
    MetricaLimite.ATENDIMENTOS: AssinaturaQuotaExtra.Tipo.ATENDIMENTOS,
}


@dataclass
class ResultadoLimite:
    permitido: bool
    metrica: str
    atual: int
    limite: int | None
    projetado: int
    excedente: int
    valor_sugerido_mensal: Decimal
    valor_unitario: Decimal
    assinatura: AssinaturaMunicipio | None
    motivo: str = ""


@dataclass
class ResultadoSimulador:
    plano: PlanoMunicipal
    preco_base: Decimal
    adicionais: list[dict]
    total_adicionais: Decimal
    total_mensal: Decimal
    justificativa: str


def _hoje() -> timezone.datetime.date:
    return timezone.localdate()


def _mes_competencia(data_ref=None):
    data_ref = data_ref or _hoje()
    return data_ref.replace(day=1)


def resolver_municipio_usuario(user) -> Municipio | None:
    p = getattr(user, "profile", None)
    if not p or not getattr(p, "municipio_id", None):
        return None
    return getattr(p, "municipio", None)


def _plano_starter() -> PlanoMunicipal | None:
    return PlanoMunicipal.objects.filter(codigo=PlanoMunicipal.Codigo.STARTER, ativo=True).first()


def get_assinatura_ativa(municipio: Municipio, *, criar_default: bool = True) -> AssinaturaMunicipio | None:
    assinatura = (
        AssinaturaMunicipio.objects.select_related("plano")
        .filter(
            municipio=municipio,
            status__in=[
                AssinaturaMunicipio.Status.ATIVO,
                AssinaturaMunicipio.Status.TRIAL,
                AssinaturaMunicipio.Status.SUSPENSO,
            ],
        )
        .order_by("-inicio_vigencia", "-id")
        .first()
    )
    if assinatura or not criar_default:
        return assinatura

    starter = _plano_starter()
    if not starter:
        return None

    return AssinaturaMunicipio.objects.create(
        municipio=municipio,
        plano=starter,
        status=AssinaturaMunicipio.Status.ATIVO,
        inicio_vigencia=_hoje(),
        contrato_meses=12,
        preco_base_congelado=starter.preco_base_mensal,
    )


def recalc_uso_municipio(municipio: Municipio, *, ano: int | None = None) -> UsoMunicipio:
    ano = ano or _hoje().year

    secretarias = Secretaria.objects.filter(municipio=municipio, ativo=True).count()
    usuarios = Profile.objects.filter(municipio=municipio, ativo=True, bloqueado=False).count()
    alunos = (
        Matricula.objects.filter(
            turma__unidade__secretaria__municipio=municipio,
            situacao=Matricula.Situacao.ATIVA,
        )
        .values("aluno_id")
        .distinct()
        .count()
    )
    atendimentos = AtendimentoSaude.objects.filter(
        unidade__secretaria__municipio=municipio,
        data__year=ano,
    ).count()

    uso, _ = UsoMunicipio.objects.get_or_create(municipio=municipio)
    uso.secretarias_ativas = secretarias
    uso.usuarios_ativos = usuarios
    uso.alunos_ativos = alunos
    uso.atendimentos_ano = atendimentos
    uso.ano_referencia = ano
    uso.save(
        update_fields=[
            "secretarias_ativas",
            "usuarios_ativos",
            "alunos_ativos",
            "atendimentos_ano",
            "ano_referencia",
            "atualizado_em",
        ]
    )
    return uso


def _valor_unitario_por_metrica(plano: PlanoMunicipal, metrica: str) -> Decimal:
    if metrica == MetricaLimite.SECRETARIAS:
        return plano.valor_secretaria_extra
    if metrica == MetricaLimite.USUARIOS:
        return plano.valor_usuario_extra
    if metrica == MetricaLimite.ALUNOS:
        return plano.valor_aluno_extra
    if metrica == MetricaLimite.ATENDIMENTOS:
        return plano.valor_atendimento_extra
    return Decimal("0.00")


def _limite_base_por_metrica(plano: PlanoMunicipal, metrica: str) -> int | None:
    if metrica == MetricaLimite.SECRETARIAS:
        return plano.limite_secretarias
    if metrica == MetricaLimite.USUARIOS:
        return plano.limite_usuarios
    if metrica == MetricaLimite.ALUNOS:
        return plano.limite_alunos
    if metrica == MetricaLimite.ATENDIMENTOS:
        return plano.limite_atendimentos_ano
    return None


def _uso_por_metrica(uso: UsoMunicipio, metrica: str) -> int:
    if metrica == MetricaLimite.SECRETARIAS:
        return int(uso.secretarias_ativas)
    if metrica == MetricaLimite.USUARIOS:
        return int(uso.usuarios_ativos)
    if metrica == MetricaLimite.ALUNOS:
        return int(uso.alunos_ativos)
    if metrica == MetricaLimite.ATENDIMENTOS:
        return int(uso.atendimentos_ano)
    return 0


def limite_efetivo_assinatura(assinatura: AssinaturaMunicipio, metrica: str, data_ref=None) -> int | None:
    base = _limite_base_por_metrica(assinatura.plano, metrica)
    if base is None:
        return None

    data_ref = data_ref or _hoje()
    quota_tipo = METRICA_TO_QUOTA.get(metrica)
    extras = (
        assinatura.quotas_extras.filter(
            tipo=quota_tipo,
            ativo=True,
            inicio_vigencia__lte=data_ref,
        )
        .filter(fim_vigencia__isnull=True)
        .aggregate(total=Sum("quantidade"))
        .get("total")
    )

    extras_ate_data = (
        assinatura.quotas_extras.filter(
            tipo=quota_tipo,
            ativo=True,
            inicio_vigencia__lte=data_ref,
            fim_vigencia__isnull=False,
            fim_vigencia__gte=data_ref,
        )
        .aggregate(total=Sum("quantidade"))
        .get("total")
    )

    total_extra = int(extras or 0) + int(extras_ate_data or 0)
    return int(base) + total_extra


def verificar_limite_municipio(
    municipio: Municipio,
    metrica: str,
    *,
    incremento: int = 1,
    recalcular: bool = True,
) -> ResultadoLimite:
    assinatura = get_assinatura_ativa(municipio)
    if not assinatura:
        return ResultadoLimite(
            permitido=True,
            metrica=metrica,
            atual=0,
            limite=None,
            projetado=max(0, incremento),
            excedente=0,
            valor_sugerido_mensal=Decimal("0.00"),
            valor_unitario=Decimal("0.00"),
            assinatura=None,
            motivo="Município sem assinatura ativa.",
        )

    uso = recalc_uso_municipio(municipio) if recalcular else UsoMunicipio.objects.get_or_create(municipio=municipio)[0]
    atual = _uso_por_metrica(uso, metrica)
    projetado = atual + max(0, incremento)

    limite = limite_efetivo_assinatura(assinatura, metrica)
    valor_unitario = _valor_unitario_por_metrica(assinatura.plano, metrica)

    if limite is None or projetado <= limite:
        return ResultadoLimite(
            permitido=True,
            metrica=metrica,
            atual=atual,
            limite=limite,
            projetado=projetado,
            excedente=0,
            valor_sugerido_mensal=Decimal("0.00"),
            valor_unitario=valor_unitario,
            assinatura=assinatura,
            motivo="Dentro do limite.",
        )

    excedente = projetado - limite
    valor_sugerido = (Decimal(excedente) * valor_unitario).quantize(Decimal("0.01"))
    return ResultadoLimite(
        permitido=False,
        metrica=metrica,
        atual=atual,
        limite=limite,
        projetado=projetado,
        excedente=excedente,
        valor_sugerido_mensal=valor_sugerido,
        valor_unitario=valor_unitario,
        assinatura=assinatura,
        motivo=(
            f"Limite de {METRICA_LABEL.get(metrica, metrica)} excedido "
            f"({atual}/{limite}; projeção: {projetado})."
        ),
    )


def calcular_valor_upgrade(
    assinatura: AssinaturaMunicipio,
    *,
    tipo: str,
    quantidade: int,
    addon: AddonCatalogo | None = None,
    plano_destino: PlanoMunicipal | None = None,
) -> Decimal:
    qtd = max(1, int(quantidade or 1))

    if tipo in {
        SolicitacaoUpgrade.Tipo.SECRETARIAS,
        SolicitacaoUpgrade.Tipo.USUARIOS,
        SolicitacaoUpgrade.Tipo.ALUNOS,
        SolicitacaoUpgrade.Tipo.ATENDIMENTOS,
    }:
        unit = _valor_unitario_por_metrica(assinatura.plano, tipo)
        return (Decimal(qtd) * unit).quantize(Decimal("0.01"))

    if tipo == SolicitacaoUpgrade.Tipo.ADDON and addon:
        return (Decimal(qtd) * addon.valor_mensal).quantize(Decimal("0.01"))

    if tipo == SolicitacaoUpgrade.Tipo.TROCA_PLANO and plano_destino:
        atual = assinatura.valor_base_mensal()
        proposto = plano_destino.preco_base_mensal
        diff = (proposto - atual).quantize(Decimal("0.01"))
        return diff if diff > 0 else Decimal("0.00")

    return Decimal("0.00")


def aprovar_upgrade(solicitacao: SolicitacaoUpgrade, *, aprovado_por, observacao: str = "") -> SolicitacaoUpgrade:
    if solicitacao.status not in {SolicitacaoUpgrade.Status.SOLICITADO, SolicitacaoUpgrade.Status.RASCUNHO}:
        return solicitacao

    with transaction.atomic():
        solicitacao.status = SolicitacaoUpgrade.Status.APROVADO
        solicitacao.aprovado_por = aprovado_por
        solicitacao.aprovado_em = timezone.now()
        if observacao:
            solicitacao.observacao = (solicitacao.observacao or "") + f"\n[Aprovação] {observacao}".strip()
        solicitacao.save(update_fields=["status", "aprovado_por", "aprovado_em", "observacao"])

        if solicitacao.tipo in {
            SolicitacaoUpgrade.Tipo.SECRETARIAS,
            SolicitacaoUpgrade.Tipo.USUARIOS,
            SolicitacaoUpgrade.Tipo.ALUNOS,
            SolicitacaoUpgrade.Tipo.ATENDIMENTOS,
        }:
            AssinaturaQuotaExtra.objects.create(
                assinatura=solicitacao.assinatura,
                tipo=solicitacao.tipo,
                quantidade=solicitacao.quantidade,
                origem=AssinaturaQuotaExtra.Origem.UPGRADE,
                descricao=f"Upgrade aprovado #{solicitacao.pk}",
                criado_por=aprovado_por,
            )

        elif solicitacao.tipo == SolicitacaoUpgrade.Tipo.ADDON and solicitacao.addon_id:
            addon_assinatura, created = AssinaturaAddon.objects.get_or_create(
                assinatura=solicitacao.assinatura,
                addon=solicitacao.addon,
                defaults={
                    "quantidade": solicitacao.quantidade,
                    "valor_unitario_congelado": solicitacao.addon.valor_mensal,
                    "ativo": True,
                },
            )
            if not created:
                addon_assinatura.quantidade += solicitacao.quantidade
                addon_assinatura.ativo = True
                addon_assinatura.save(update_fields=["quantidade", "ativo"])

        elif solicitacao.tipo == SolicitacaoUpgrade.Tipo.TROCA_PLANO and solicitacao.plano_destino_id:
            solicitacao.assinatura.plano = solicitacao.plano_destino
            solicitacao.assinatura.preco_base_congelado = solicitacao.plano_destino.preco_base_mensal
            solicitacao.assinatura.save(update_fields=["plano", "preco_base_congelado", "atualizado_em"])

    return solicitacao


def recusar_upgrade(solicitacao: SolicitacaoUpgrade, *, aprovado_por, observacao: str = "") -> SolicitacaoUpgrade:
    if solicitacao.status not in {SolicitacaoUpgrade.Status.SOLICITADO, SolicitacaoUpgrade.Status.RASCUNHO}:
        return solicitacao

    solicitacao.status = SolicitacaoUpgrade.Status.RECUSADO
    solicitacao.aprovado_por = aprovado_por
    solicitacao.aprovado_em = timezone.now()
    if observacao:
        solicitacao.observacao = (solicitacao.observacao or "") + f"\n[Recusa] {observacao}".strip()
    solicitacao.save(update_fields=["status", "aprovado_por", "aprovado_em", "observacao"])
    return solicitacao


def calcular_total_adicionais(assinatura: AssinaturaMunicipio, data_ref=None) -> Decimal:
    data_ref = data_ref or _hoje()

    adicionais = Decimal("0.00")
    for metrica in [
        MetricaLimite.SECRETARIAS,
        MetricaLimite.USUARIOS,
        MetricaLimite.ALUNOS,
        MetricaLimite.ATENDIMENTOS,
    ]:
        tipo = METRICA_TO_QUOTA[metrica]
        qtd = (
            assinatura.quotas_extras.filter(tipo=tipo, ativo=True, inicio_vigencia__lte=data_ref)
            .filter(fim_vigencia__isnull=True)
            .aggregate(total=Sum("quantidade"))
            .get("total")
            or 0
        )
        qtd += (
            assinatura.quotas_extras.filter(
                tipo=tipo,
                ativo=True,
                inicio_vigencia__lte=data_ref,
                fim_vigencia__isnull=False,
                fim_vigencia__gte=data_ref,
            )
            .aggregate(total=Sum("quantidade"))
            .get("total")
            or 0
        )
        adicionais += Decimal(qtd) * _valor_unitario_por_metrica(assinatura.plano, metrica)

    addons_total = Decimal("0.00")
    addons_qs = assinatura.addons.filter(ativo=True, inicio_vigencia__lte=data_ref).filter(
        fim_vigencia__isnull=True
    ) | assinatura.addons.filter(
        ativo=True,
        inicio_vigencia__lte=data_ref,
        fim_vigencia__isnull=False,
        fim_vigencia__gte=data_ref,
    )

    for ad in addons_qs.distinct():
        unit = ad.valor_unitario_congelado or ad.addon.valor_mensal
        addons_total += Decimal(ad.quantidade) * unit

    return (adicionais + addons_total).quantize(Decimal("0.01"))


def gerar_fatura_mensal(assinatura: AssinaturaMunicipio, *, competencia=None) -> FaturaMunicipio:
    competencia = _mes_competencia(competencia)

    fatura, _ = FaturaMunicipio.objects.get_or_create(
        assinatura=assinatura,
        competencia=competencia,
        defaults={
            "municipio": assinatura.municipio,
        },
    )

    desconto = assinatura.valor_desconto_mensal()
    base = assinatura.preco_base_congelado
    adicionais = calcular_total_adicionais(assinatura, competencia)
    total = (base - desconto + adicionais).quantize(Decimal("0.01"))

    fatura.municipio = assinatura.municipio
    fatura.valor_base = base
    fatura.valor_desconto = desconto
    fatura.valor_adicionais = adicionais
    fatura.valor_total = total
    fatura.vencimento = competencia.replace(day=20)
    fatura.save(
        update_fields=[
            "municipio",
            "valor_base",
            "valor_desconto",
            "valor_adicionais",
            "valor_total",
            "vencimento",
        ]
    )
    return fatura


def recomendar_plano_por_porte(*, alunos: int) -> PlanoMunicipal | None:
    if alunos <= 2000:
        codigo = PlanoMunicipal.Codigo.STARTER
    elif alunos <= 8000:
        codigo = PlanoMunicipal.Codigo.MUNICIPAL
    else:
        codigo = PlanoMunicipal.Codigo.GESTAO_TOTAL
    return PlanoMunicipal.objects.filter(codigo=codigo, ativo=True).first()


def simular_plano(
    *,
    secretarias: int,
    usuarios: int,
    alunos: int,
    atendimentos: int,
) -> ResultadoSimulador | None:
    plano = recomendar_plano_por_porte(alunos=alunos)
    if not plano:
        return None

    extras = []

    def _add_extra(nome: str, qtd: int, unit: Decimal):
        if qtd <= 0:
            return
        total = (Decimal(qtd) * unit).quantize(Decimal("0.01"))
        extras.append(
            {
                "nome": nome,
                "quantidade": qtd,
                "valor_unitario": unit,
                "valor_total": total,
            }
        )

    if plano.limite_secretarias is not None:
        _add_extra(
            "Secretarias extras",
            max(0, int(secretarias) - int(plano.limite_secretarias)),
            plano.valor_secretaria_extra,
        )

    if plano.limite_usuarios is not None:
        _add_extra(
            "Usuários extras",
            max(0, int(usuarios) - int(plano.limite_usuarios)),
            plano.valor_usuario_extra,
        )

    if plano.limite_alunos is not None:
        _add_extra(
            "Alunos extras",
            max(0, int(alunos) - int(plano.limite_alunos)),
            plano.valor_aluno_extra,
        )

    if plano.limite_atendimentos_ano is not None:
        _add_extra(
            "Atendimentos extras/ano",
            max(0, int(atendimentos) - int(plano.limite_atendimentos_ano)),
            plano.valor_atendimento_extra,
        )

    total_adicionais = sum((e["valor_total"] for e in extras), Decimal("0.00")).quantize(Decimal("0.01"))
    total_mensal = (plano.preco_base_mensal + total_adicionais).quantize(Decimal("0.01"))

    if plano.codigo == PlanoMunicipal.Codigo.STARTER:
        justificativa = "Porte municipal pequeno com melhor custo de entrada." 
    elif plano.codigo == PlanoMunicipal.Codigo.MUNICIPAL:
        justificativa = "Plano recomendado por equilíbrio entre cobertura e custo-benefício."
    else:
        justificativa = "Porte médio/grande, com necessidade de escala e BI executivo."

    return ResultadoSimulador(
        plano=plano,
        preco_base=plano.preco_base_mensal,
        adicionais=extras,
        total_adicionais=total_adicionais,
        total_mensal=total_mensal,
        justificativa=justificativa,
    )
