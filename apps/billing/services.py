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
    PlanoComercialConfig,
    PlanoMunicipal,
    SolicitacaoUpgrade,
    UsoMunicipio,
)


class PlanoApp:
    GESTAO = "GESTAO"
    PORTAL = "PORTAL"
    TRANSPARENCIA = "TRANSPARENCIA"
    CAMARA = "CAMARA"


PLANO_APP_ORDER: list[str] = [
    PlanoApp.GESTAO,
    PlanoApp.PORTAL,
    PlanoApp.TRANSPARENCIA,
    PlanoApp.CAMARA,
]

PLANO_APP_LABELS: dict[str, str] = {
    PlanoApp.GESTAO: "Gestão Interna (Secretarias)",
    PlanoApp.PORTAL: "Portal da Prefeitura",
    PlanoApp.TRANSPARENCIA: "Portal da Transparência",
    PlanoApp.CAMARA: "Portal da Câmara",
}

APP_FEATURE_FLAGS: dict[str, set[str]] = {
    PlanoApp.GESTAO: {
        "GESTAO_ORGAO_ESTRUTURA",
        "GESTAO_USUARIOS_RBAC",
        "GESTAO_PROTOCOLO",
        "GESTAO_DOCUMENTOS_MODELOS",
        "GESTAO_RELATORIOS_BASICO",
        "GESTAO_AUDITORIA_LOGS",
    },
    PlanoApp.PORTAL: {
        "PORTAL_CMS",
        "PORTAL_PAGINAS",
        "PORTAL_NOTICIAS",
        "PORTAL_BANNERS",
        "PORTAL_DOWNLOADS",
        "PORTAL_SEO_CONFIG",
    },
    PlanoApp.TRANSPARENCIA: {
        "TRANS_DADOS_RECEITAS",
        "TRANS_DADOS_DESPESAS",
        "TRANS_LICITACOES_CONTRATOS",
        "TRANS_PUBLICACOES_OFICIAIS",
        "TRANS_EXPORT_PDF_EXCEL",
        "TRANS_ESIC",
        "TRANS_AUDITORIA_PUBLICA",
    },
    PlanoApp.CAMARA: {
        "CAMARA_CMS",
        "CAMARA_VEREADORES_COMISSOES",
        "CAMARA_SESSOES_PAUTAS_ATAS",
        "CAMARA_PROPOSICOES",
        "CAMARA_TRANSPARENCIA",
        "CAMARA_YOUTUBE_LIVE",
    },
}

PLANO_APPS_BY_CODE: dict[str, set[str]] = {
    PlanoMunicipal.Codigo.STARTER: {
        PlanoApp.GESTAO,
    },
    PlanoMunicipal.Codigo.MUNICIPAL: {
        PlanoApp.GESTAO,
        PlanoApp.PORTAL,
    },
    PlanoMunicipal.Codigo.GESTAO_TOTAL: {
        PlanoApp.GESTAO,
        PlanoApp.PORTAL,
        PlanoApp.TRANSPARENCIA,
    },
    PlanoMunicipal.Codigo.CONSORCIO: {
        PlanoApp.GESTAO,
        PlanoApp.PORTAL,
        PlanoApp.TRANSPARENCIA,
        PlanoApp.CAMARA,
    },
}

PLANO_COMERCIAL_SPECS: dict[str, dict] = {
    PlanoMunicipal.Codigo.STARTER: {
        "nome_comercial": "GEPUB Essencial",
        "categoria": "Etapa 1",
        "descricao_comercial": "Gestão interna da prefeitura com foco em organização operacional por secretarias.",
        "beneficios": [
            "Gestão interna completa por secretarias e unidades",
            "Protocolo interno, documentos e trilha de operação",
            "Controle de usuários e perfis com RBAC",
        ],
        "especiais": [
            "Ideal para iniciar a digitalização municipal com governança",
        ],
        "limitacoes": [
            "Não inclui Portal da Prefeitura",
            "Não inclui Portal da Transparência",
            "Não inclui Portal da Câmara",
        ],
        "dependencias": [
            "Evolução recomendada: Gestão Integrada para ativar o Portal da Prefeitura.",
        ],
    },
    PlanoMunicipal.Codigo.MUNICIPAL: {
        "nome_comercial": "GEPUB Gestão Integrada",
        "categoria": "Etapa 2",
        "descricao_comercial": "Gestão interna + portal institucional da prefeitura para comunicação oficial com o cidadão.",
        "beneficios": [
            "Tudo do Essencial",
            "CMS do Portal da Prefeitura com páginas, notícias e banners",
            "Biblioteca pública de documentos e comunicados oficiais",
        ],
        "especiais": [
            "Ideal para estruturar presença institucional digital",
        ],
        "limitacoes": [
            "Não inclui Portal da Transparência completo",
            "Não inclui Portal da Câmara",
        ],
        "dependencias": [
            "Evolução recomendada: Transformação Digital para e-SIC e transparência completa.",
        ],
    },
    PlanoMunicipal.Codigo.GESTAO_TOTAL: {
        "nome_comercial": "GEPUB Transformação Digital",
        "categoria": "Etapa 3",
        "descricao_comercial": "Gestão + Portal + Transparência completa com e-SIC, exportações e trilha de auditoria pública.",
        "beneficios": [
            "Tudo do Gestão Integrada",
            "Portal da Transparência com receitas, despesas, licitações e contratos",
            "e-SIC com gestão de prazos, respostas e histórico",
            "Exportações e relatórios para governança e auditoria",
        ],
        "especiais": [
            "Ideal para fortalecer conformidade legal e reputação institucional",
        ],
        "limitacoes": [
            "Não inclui Portal da Câmara completo",
        ],
        "dependencias": [
            "Evolução recomendada: Governo Completo para integrar Executivo e Legislativo.",
        ],
    },
    PlanoMunicipal.Codigo.CONSORCIO: {
        "nome_comercial": "GEPUB Governo Completo",
        "categoria": "Etapa 4",
        "descricao_comercial": "Executivo + Legislativo em plataforma única, com portais e transparência integrados.",
        "beneficios": [
            "Tudo do Transformação Digital",
            "Portal da Câmara com sessões, pautas, atas e proposições",
            "Transparência da Câmara (gastos, contratos, licitações e diárias)",
            "Integração com transmissões ao vivo via YouTube",
        ],
        "especiais": [
            "Ideal para municípios que buscam referência em transformação digital pública",
        ],
        "limitacoes": [
            "Serviços presenciais e escopos especiais dependem de proposta específica",
        ],
        "dependencias": [
            "Fluxos legislativos avançados podem ser ativados por demanda.",
        ],
    },
}

PLANO_DOC_LINKS: dict[str, dict[str, str]] = {
    PlanoMunicipal.Codigo.STARTER: {
        "contratacao": "/docs/contratacao/gepub-essencial.pdf",
        "servicos": "/docs/prestacao-servicos/gepub-essencial.pdf",
    },
    PlanoMunicipal.Codigo.MUNICIPAL: {
        "contratacao": "/docs/contratacao/gepub-gestao-integrada.pdf",
        "servicos": "/docs/prestacao-servicos/gepub-gestao-integrada.pdf",
    },
    PlanoMunicipal.Codigo.GESTAO_TOTAL: {
        "contratacao": "/docs/contratacao/gepub-transformacao-digital.pdf",
        "servicos": "/docs/prestacao-servicos/gepub-transformacao-digital.pdf",
    },
    PlanoMunicipal.Codigo.CONSORCIO: {
        "contratacao": "/docs/contratacao/gepub-governo-completo.pdf",
        "servicos": "/docs/prestacao-servicos/gepub-governo-completo.pdf",
    },
}

LEGACY_PLAN_FEATURES: list[str] = [
    "feature_bi_light",
    "feature_bi_municipal",
    "feature_bi_avancado",
    "feature_importacao_assistida",
    "feature_sla_prioritario",
    "feature_migracao_assistida",
    "feature_treinamento_continuo",
]


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


def _limit_text(value: int | None) -> str:
    if value is None:
        return "Ilimitado (fair use)"
    return str(int(value))


def plan_apps_for_code(plan_code: str | None) -> set[str]:
    return set(PLANO_APPS_BY_CODE.get(str(plan_code or "").strip(), {PlanoApp.GESTAO}))


def plan_feature_flags_for_code(plan_code: str | None) -> set[str]:
    apps = plan_apps_for_code(plan_code)
    features: set[str] = set()
    for app in apps:
        features.update(APP_FEATURE_FLAGS.get(app, set()))
    return features


def plan_app_labels_for_code(plan_code: str | None) -> list[str]:
    apps = plan_apps_for_code(plan_code)
    return [PLANO_APP_LABELS[item] for item in PLANO_APP_ORDER if item in apps]


def plano_comercial_data(plano: PlanoMunicipal | None) -> dict:
    if not plano:
        return {
            "codigo": "",
            "nome": "",
            "nome_comercial": "Plano não definido",
            "categoria": "",
            "descricao_comercial": "Defina um plano para liberar limites e benefícios comerciais.",
            "beneficios": [],
            "especiais": [],
            "limitacoes": [],
            "dependencias": [],
            "features_habilitadas": [],
            "limites": {
                "secretarias": "Ilimitado",
                "usuarios": "Ilimitado",
                "alunos": "Ilimitado",
                "atendimentos_ano": "Ilimitado",
            },
            "links": {
                "contratacao": "#",
                "servicos": "#",
            },
        }

    spec = PLANO_COMERCIAL_SPECS.get(plano.codigo, {})
    links = PLANO_DOC_LINKS.get(plano.codigo, {})
    config: PlanoComercialConfig | None = getattr(plano, "comercial_config", None)
    apps_habilitados = plan_app_labels_for_code(plano.codigo)
    features_habilitadas = apps_habilitados
    beneficios = list((config.beneficios if config else None) or spec.get("beneficios", []))
    especiais = list((config.especiais if config else None) or spec.get("especiais", []))
    limitacoes = list((config.limitacoes if config else None) or spec.get("limitacoes", []))
    dependencias = list((config.dependencias if config else None) or spec.get("dependencias", []))
    for item in apps_habilitados:
        if item not in beneficios:
            beneficios.append(item)

    return {
        "codigo": plano.codigo,
        "nome": plano.nome,
        "nome_comercial": (config.nome_comercial if config else "") or spec.get("nome_comercial") or plano.nome,
        "categoria": (config.categoria if config else "") or spec.get("categoria", ""),
        "descricao_comercial": (config.descricao_comercial if config else "") or spec.get("descricao_comercial") or plano.descricao,
        "beneficios": beneficios,
        "especiais": especiais,
        "limitacoes": limitacoes,
        "dependencias": dependencias,
        "apps_habilitados": apps_habilitados,
        "features_habilitadas": features_habilitadas,
        "limites": {
            "secretarias": "Ilimitado",
            "usuarios": _limit_text(plano.limite_usuarios),
            "alunos": _limit_text(plano.limite_alunos),
            "atendimentos_ano": _limit_text(plano.limite_atendimentos_ano),
        },
        "links": {
            "contratacao": (config.link_documento_contratacao if config else "") or links.get("contratacao", "#"),
            "servicos": (config.link_documento_servicos if config else "") or links.get("servicos", "#"),
        },
    }


def catalogo_planos_comercial(planos: list[PlanoMunicipal] | None = None) -> list[dict]:
    if planos is None:
        planos = list(
            PlanoMunicipal.objects.filter(
                ativo=True,
                codigo__in=[
                    PlanoMunicipal.Codigo.STARTER,
                    PlanoMunicipal.Codigo.MUNICIPAL,
                    PlanoMunicipal.Codigo.GESTAO_TOTAL,
                    PlanoMunicipal.Codigo.CONSORCIO,
                ],
            )
            .select_related("comercial_config")
            .order_by("preco_base_mensal", "nome")
        )
    return [plano_comercial_data(plano) for plano in planos]


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


def municipio_plan_features(municipio: Municipio | None) -> set[str]:
    """
    Retorna as features habilitadas no plano ativo do município.
    """
    if not municipio:
        return set()
    assinatura = get_assinatura_ativa(municipio, criar_default=False)
    if not assinatura or not assinatura.plano_id:
        return set()

    plano = assinatura.plano
    features: set[str] = set(plan_feature_flags_for_code(plano.codigo))
    for attr in LEGACY_PLAN_FEATURES:
        if bool(getattr(plano, attr, False)):
            features.add(attr)
    return features


def municipio_plan_apps(municipio: Municipio | None) -> set[str]:
    if not municipio:
        return set()
    assinatura = get_assinatura_ativa(municipio, criar_default=False)
    if not assinatura or not assinatura.plano_id:
        return set()
    return plan_apps_for_code(assinatura.plano.codigo)


def municipio_has_plan_app(municipio: Municipio | None, app_key: str) -> bool:
    app = (app_key or "").strip().upper()
    if not app:
        return False
    return app in municipio_plan_apps(municipio)


def municipio_has_plan_feature(municipio: Municipio | None, feature_name: str) -> bool:
    feature = (feature_name or "").strip()
    if not feature:
        return False
    return feature in municipio_plan_features(municipio)


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
        # Política comercial atual: sem limitação de secretarias por plano.
        return None
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
    elif alunos <= 20000:
        codigo = PlanoMunicipal.Codigo.GESTAO_TOTAL
    else:
        codigo = PlanoMunicipal.Codigo.CONSORCIO
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

    # Política comercial atual: secretarias sem cobrança de excedente.

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
        justificativa = "Plano base para organizar a gestão interna por secretarias."
    elif plano.codigo == PlanoMunicipal.Codigo.MUNICIPAL:
        justificativa = "Gestão + Portal da Prefeitura para comunicação institucional."
    elif plano.codigo == PlanoMunicipal.Codigo.GESTAO_TOTAL:
        justificativa = "Gestão + Portal + Transparência para governança e conformidade."
    else:
        justificativa = "Executivo + Legislativo com portais completos e integração Câmara."

    return ResultadoSimulador(
        plano=plano,
        preco_base=plano.preco_base_mensal,
        adicionais=extras,
        total_adicionais=total_adicionais,
        total_mensal=total_mensal,
        justificativa=justificativa,
    )
