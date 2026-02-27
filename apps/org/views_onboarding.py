from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse

from apps.billing.forms import OnboardingPlanoForm
from apps.billing.models import AssinaturaMunicipio, PlanoMunicipal, SolicitacaoUpgrade
from apps.billing.services import (
    MetricaLimite,
    calcular_valor_upgrade,
    get_assinatura_ativa,
    verificar_limite_municipio,
)
from apps.core.decorators import require_perm
from apps.core.rbac import get_profile, is_admin
from apps.core.services_portal_seed import ensure_portal_seed_for_municipio
from apps.org.forms import OnboardingMunicipioForm, OnboardingTemplateActivationForm
from apps.org.models import (
    Municipio,
    MunicipioModuloAtivo,
    OnboardingStep,
    Secretaria,
    SecretariaProvisionamento,
    SecretariaTemplate,
)
from apps.org.services.provisioning import (
    provision_secretaria_from_template,
    refresh_onboarding_progress,
    seed_secretaria_templates,
)


TEMPLATE_VISUALS = {
    SecretariaTemplate.Modulo.ADMINISTRACAO: {"icon": "fa-solid fa-building-shield", "tone": "indigo"},
    SecretariaTemplate.Modulo.FINANCAS: {"icon": "fa-solid fa-coins", "tone": "emerald"},
    SecretariaTemplate.Modulo.PLANEJAMENTO: {"icon": "fa-solid fa-compass-drafting", "tone": "cyan"},
    SecretariaTemplate.Modulo.EDUCACAO: {"icon": "fa-solid fa-school", "tone": "blue"},
    SecretariaTemplate.Modulo.SAUDE: {"icon": "fa-solid fa-notes-medical", "tone": "rose"},
    SecretariaTemplate.Modulo.OBRAS: {"icon": "fa-solid fa-helmet-safety", "tone": "amber"},
    SecretariaTemplate.Modulo.AGRICULTURA: {"icon": "fa-solid fa-tractor", "tone": "lime"},
    SecretariaTemplate.Modulo.TECNOLOGIA: {"icon": "fa-solid fa-microchip", "tone": "violet"},
    SecretariaTemplate.Modulo.ASSISTENCIA: {"icon": "fa-solid fa-hands-holding-circle", "tone": "teal"},
    SecretariaTemplate.Modulo.MEIO_AMBIENTE: {"icon": "fa-solid fa-leaf", "tone": "green"},
    SecretariaTemplate.Modulo.TRANSPORTE: {"icon": "fa-solid fa-bus", "tone": "orange"},
    SecretariaTemplate.Modulo.CULTURA: {"icon": "fa-solid fa-masks-theater", "tone": "pink"},
    SecretariaTemplate.Modulo.DESENVOLVIMENTO: {"icon": "fa-solid fa-chart-line", "tone": "slate"},
    SecretariaTemplate.Modulo.HABITACAO: {"icon": "fa-solid fa-house-chimney", "tone": "sky"},
    SecretariaTemplate.Modulo.SERVICOS_PUBLICOS: {"icon": "fa-solid fa-road", "tone": "steel"},
    SecretariaTemplate.Modulo.OUTRO: {"icon": "fa-solid fa-layer-group", "tone": "indigo"},
}


TONE_TO_KPI_VARIANT = {
    "indigo": "kpi-card--indigo",
    "emerald": "kpi-card--green",
    "cyan": "kpi-card--teal",
    "blue": "kpi-card--blue",
    "rose": "kpi-card--amber",
    "amber": "kpi-card--amber",
    "lime": "kpi-card--green",
    "violet": "kpi-card--indigo",
    "teal": "kpi-card--teal",
    "green": "kpi-card--green",
    "orange": "kpi-card--amber",
    "pink": "kpi-card--indigo",
    "slate": "kpi-card--slate",
    "sky": "kpi-card--teal",
    "steel": "kpi-card--slate",
}

MANDATORY_TEMPLATE_SLUGS = {
    "administracao",
    "educacao",
    "saude",
}


def _template_visual_data(template: SecretariaTemplate) -> dict:
    base = TEMPLATE_VISUALS.get(template.modulo) or TEMPLATE_VISUALS[SecretariaTemplate.Modulo.OUTRO]
    return {
        "icon": base["icon"],
        "tone": base["tone"],
    }


def _can_access_onboarding(user) -> bool:
    if is_admin(user):
        return True
    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return False
    return (p.role or "").upper() == "MUNICIPAL"


def _get_municipio_for_user(user):
    p = get_profile(user)
    if p and getattr(p, "municipio_id", None):
        return p.municipio
    if is_admin(user):
        return Municipio.objects.order_by("nome").first()
    return None


def _build_template_rows(
    form: OnboardingTemplateActivationForm,
    templates: list[SecretariaTemplate],
    activation_counts: dict[str, int] | None = None,
) -> list[dict]:
    def _field_is_checked(field_name: str) -> bool:
        value = form[field_name].value()
        return str(value).lower() in {"true", "1", "on", "yes"}

    activation_counts = activation_counts or {}
    rows: list[dict] = []
    for tpl in templates:
        modulos = [tpl.modulo, *(tpl.modulos_ativos_padrao or [])]
        modulos_preview: list[str] = []
        for mod in modulos:
            value = (mod or "").strip().lower()
            if value and value not in modulos_preview:
                modulos_preview.append(value)
        itens_ativos = tpl.itens.filter(ativo=True)
        qtd_unidades = itens_ativos.filter(tipo="UNIDADE").count() + (1 if tpl.criar_unidade_base else 0)
        qtd_setores = itens_ativos.filter(tipo="SETOR").count()
        visual = _template_visual_data(tpl)
        is_selected = _field_is_checked(f"ativar_{tpl.slug}")
        installed_total = sum(
            int(activation_counts.get(key) or 0)
            for key in {tpl.slug, tpl.modulo}
            if key
        )

        rows.append(
            {
                "template": tpl,
                "ativar_field": form[f"ativar_{tpl.slug}"],
                "qtd_field": form[f"qtd_{tpl.slug}"],
                "nome_field": form[f"nome_{tpl.slug}"],
                "sigla_field": form[f"sigla_{tpl.slug}"],
                "modulos_preview": modulos_preview,
                "qtd_unidades": qtd_unidades,
                "qtd_setores": qtd_setores,
                "qtd_cadastros_base": len(tpl.cadastros_base_padrao or []),
                "qtd_steps": len(tpl.onboarding_padrao or []),
                "icon": visual["icon"],
                "tone": visual["tone"],
                "kpi_variant": TONE_TO_KPI_VARIANT.get(visual["tone"], "kpi-card--blue"),
                "module_key": tpl.modulo,
                "module_label": tpl.get_modulo_display(),
                "is_selected": is_selected,
                "is_installed": installed_total > 0,
                "installed_total": installed_total,
                "is_required": tpl.slug in MANDATORY_TEMPLATE_SLUGS,
                "search_text": " ".join(
                    [
                        tpl.nome,
                        tpl.descricao or "",
                        tpl.get_modulo_display(),
                        " ".join(modulos_preview),
                    ]
                ).strip(),
            }
        )
    rows.sort(key=lambda item: (item["module_label"], item["template"].nome))
    return rows


def _build_market_categories(template_rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in template_rows:
        key = row["module_key"]
        current = grouped.get(key)
        if not current:
            grouped[key] = {
                "key": key,
                "label": row["module_label"],
                "icon": row["icon"],
                "count": 1,
            }
            continue
        current["count"] += 1

    return sorted(grouped.values(), key=lambda item: item["label"])


def _template_activation_counts(municipio: Municipio | None, templates: list[SecretariaTemplate]) -> dict[str, int]:
    if not municipio:
        return {}

    keys: set[str] = set()
    for tpl in templates:
        if tpl.slug:
            keys.add(tpl.slug)
        if tpl.modulo:
            keys.add(tpl.modulo)

    if not keys:
        return {}

    rows = (
        Secretaria.objects.filter(municipio=municipio, tipo_modelo__in=keys)
        .values("tipo_modelo")
        .annotate(total=Count("id"))
    )
    return {item["tipo_modelo"]: int(item["total"] or 0) for item in rows}


def _template_is_installed(template: SecretariaTemplate, activation_counts: dict[str, int] | None = None) -> bool:
    counts = activation_counts or {}
    keys = {template.slug, template.modulo}
    for key in keys:
        if key and int(counts.get(key) or 0) > 0:
            return True
    return False


def _get_assinatura_municipio(municipio: Municipio | None) -> AssinaturaMunicipio | None:
    if not municipio:
        return None
    return get_assinatura_ativa(municipio, criar_default=False)


def _planos_upgrade(assinatura: AssinaturaMunicipio | None) -> list[PlanoMunicipal]:
    qs = PlanoMunicipal.objects.filter(ativo=True).order_by("preco_base_mensal", "nome")
    if not assinatura:
        return list(qs)
    return list(qs.exclude(pk=assinatura.plano_id))


def _fmt_currency(value: Decimal) -> str:
    try:
        val = Decimal(value or 0).quantize(Decimal("0.01"))
    except Exception:
        val = Decimal("0.00")
    return f"{val:.2f}".replace(".", ",")


def _seed_portais_base(municipio: Municipio | None, request) -> None:
    if not municipio:
        return
    try:
        result = ensure_portal_seed_for_municipio(municipio, autor=request.user)
    except Exception:
        messages.warning(
            request,
            "Não foi possível concluir o seed inicial dos portais públicos neste momento.",
        )
        return
    if result.created_total > 0:
        messages.info(
            request,
            "Portais públicos iniciados automaticamente: "
            f"{'configuração' if result.config_created else 'configuração existente'}, "
            f"{result.banners_created} banner(s), {result.noticias_created} notícia(s), "
            f"{result.paginas_created} página(s), {result.menus_created} menu(s) e "
            f"{result.blocos_created} bloco(s) padrão.",
        )


@login_required
@require_perm("org.view")
def onboarding_primeiro_acesso(request):
    if not _can_access_onboarding(request.user):
        return HttpResponseForbidden("403 — Apenas gestor municipal pode executar o onboarding.")

    templates = list(SecretariaTemplate.objects.filter(ativo=True).order_by("nome"))
    if not templates:
        templates = seed_secretaria_templates()

    municipio = _get_municipio_for_user(request.user)
    p = get_profile(request.user)
    assinatura = _get_assinatura_municipio(municipio)
    limite_secretarias_alert = None
    planos_upgrade = _planos_upgrade(assinatura)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "save_municipio":
            form_municipio = OnboardingMunicipioForm(request.POST, instance=municipio)
            form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
            form_ativacao = OnboardingTemplateActivationForm(templates=templates)
            if form_municipio.is_valid():
                municipio = form_municipio.save()
                _seed_portais_base(municipio, request)
                if p and not p.municipio_id:
                    p.municipio = municipio
                    p.save(update_fields=["municipio"])
                assinatura = _get_assinatura_municipio(municipio)
                planos_upgrade = _planos_upgrade(assinatura)
                form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
                messages.success(request, "Dados do município salvos.")
                return redirect("org:onboarding_primeiro_acesso")
            messages.error(request, "Corrija os dados do município para continuar.")
        elif action == "save_plano":
            form_municipio = OnboardingMunicipioForm(instance=municipio)
            form_ativacao = OnboardingTemplateActivationForm(templates=templates)
            if not municipio:
                form_plano = OnboardingPlanoForm(prefix="plano")
                messages.error(request, "Cadastre o município antes de selecionar o plano.")
                return redirect("org:onboarding_primeiro_acesso")

            form_plano = OnboardingPlanoForm(request.POST, instance=assinatura, prefix="plano")
            if form_plano.is_valid():
                assinatura_obj = form_plano.save(commit=False)
                assinatura_obj.municipio = municipio
                assinatura_obj.status = AssinaturaMunicipio.Status.ATIVO
                if (not assinatura) or (assinatura.plano_id != assinatura_obj.plano_id):
                    assinatura_obj.preco_base_congelado = assinatura_obj.plano.preco_base_mensal
                elif not assinatura_obj.preco_base_congelado:
                    assinatura_obj.preco_base_congelado = assinatura_obj.plano.preco_base_mensal
                assinatura_obj.save()
                assinatura = assinatura_obj
                planos_upgrade = _planos_upgrade(assinatura)
                messages.success(request, "Plano municipal definido com sucesso.")
                return redirect("org:onboarding_primeiro_acesso")
            messages.error(request, "Corrija os dados do plano para continuar.")
        elif action == "solicitar_overage_secretarias":
            form_municipio = OnboardingMunicipioForm(instance=municipio)
            form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
            form_ativacao = OnboardingTemplateActivationForm(templates=templates)

            if not municipio:
                messages.error(request, "Cadastre o município antes de solicitar extras.")
                return redirect("org:onboarding_primeiro_acesso")

            assinatura = get_assinatura_ativa(municipio, criar_default=True)
            planos_upgrade = _planos_upgrade(assinatura)
            if not assinatura:
                messages.error(request, "Não foi possível identificar assinatura ativa para este município.")
                return redirect("org:onboarding_primeiro_acesso")

            qtd_raw = (request.POST.get("qtd_excedente") or "").strip()
            qtd = int(qtd_raw) if qtd_raw.isdigit() else 1
            qtd = max(1, qtd)
            valor = calcular_valor_upgrade(
                assinatura,
                tipo=SolicitacaoUpgrade.Tipo.SECRETARIAS,
                quantidade=qtd,
            )
            SolicitacaoUpgrade.objects.create(
                municipio=municipio,
                assinatura=assinatura,
                tipo=SolicitacaoUpgrade.Tipo.SECRETARIAS,
                quantidade=qtd,
                valor_mensal_calculado=valor,
                status=SolicitacaoUpgrade.Status.SOLICITADO,
                solicitado_por=request.user,
                observacao="Solicitação criada pelo carrinho de secretarias no onboarding.",
            )
            messages.success(
                request,
                f"Carrinho de extras enviado: +{qtd} secretaria(s) por R$ {_fmt_currency(valor)}/mês.",
            )
            return redirect("org:onboarding_primeiro_acesso")
        elif action == "solicitar_troca_plano":
            form_municipio = OnboardingMunicipioForm(instance=municipio)
            form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
            form_ativacao = OnboardingTemplateActivationForm(templates=templates)

            if not municipio:
                messages.error(request, "Cadastre o município antes de solicitar troca de plano.")
                return redirect("org:onboarding_primeiro_acesso")

            assinatura = get_assinatura_ativa(municipio, criar_default=True)
            planos_upgrade = _planos_upgrade(assinatura)
            if not assinatura:
                messages.error(request, "Não foi possível identificar assinatura ativa para este município.")
                return redirect("org:onboarding_primeiro_acesso")

            plano_destino_id = (request.POST.get("plano_destino_id") or "").strip()
            if not plano_destino_id.isdigit():
                messages.error(request, "Selecione um plano de destino para solicitar a troca.")
                return redirect("org:onboarding_primeiro_acesso")

            plano_destino = PlanoMunicipal.objects.filter(pk=int(plano_destino_id), ativo=True).first()
            if not plano_destino:
                messages.error(request, "Plano de destino inválido.")
                return redirect("org:onboarding_primeiro_acesso")
            if plano_destino.pk == assinatura.plano_id:
                messages.error(request, "O plano selecionado já é o plano atual do município.")
                return redirect("org:onboarding_primeiro_acesso")

            valor = calcular_valor_upgrade(
                assinatura,
                tipo=SolicitacaoUpgrade.Tipo.TROCA_PLANO,
                quantidade=1,
                plano_destino=plano_destino,
            )
            SolicitacaoUpgrade.objects.create(
                municipio=municipio,
                assinatura=assinatura,
                tipo=SolicitacaoUpgrade.Tipo.TROCA_PLANO,
                plano_destino=plano_destino,
                quantidade=1,
                valor_mensal_calculado=valor,
                status=SolicitacaoUpgrade.Status.SOLICITADO,
                solicitado_por=request.user,
                observacao="Solicitação de troca de plano criada durante onboarding.",
            )
            messages.success(
                request,
                f"Solicitação de troca enviada para {plano_destino.nome}. Diferença estimada: R$ {_fmt_currency(valor)}/mês.",
            )
            return redirect("org:onboarding_primeiro_acesso")
        elif action == "ativar_templates":
            form_municipio = OnboardingMunicipioForm(instance=municipio)
            form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
            form_ativacao = OnboardingTemplateActivationForm(request.POST, templates=templates)
            if not municipio:
                messages.error(request, "Cadastre o município antes de ativar secretarias.")
                return redirect("org:onboarding_primeiro_acesso")
            if not assinatura:
                assinatura = get_assinatura_ativa(municipio, criar_default=True)
                if assinatura:
                    messages.warning(
                        request,
                        "Plano não definido previamente. Foi aplicado Starter como base inicial.",
                    )
                planos_upgrade = _planos_upgrade(assinatura)

            if form_ativacao.is_valid():
                try:
                    ativacoes = form_ativacao.get_ativacoes()
                    activation_counts_post = _template_activation_counts(municipio, templates)

                    ativacoes_por_slug = {
                        (item["template"].slug or ""): item
                        for item in ativacoes
                        if item.get("template")
                    }
                    obrigatorias_auto: list[str] = []
                    for tpl in templates:
                        slug = (tpl.slug or "").strip().lower()
                        if slug not in MANDATORY_TEMPLATE_SLUGS:
                            continue
                        if _template_is_installed(tpl, activation_counts_post):
                            continue
                        if slug in ativacoes_por_slug:
                            continue
                        ativacoes.append(
                            {
                                "template": tpl,
                                "qtd": 1,
                                "nome": "",
                                "sigla": "",
                            }
                        )
                        obrigatorias_auto.append(tpl.nome)

                    if obrigatorias_auto:
                        messages.info(
                            request,
                            "Secretarias obrigatórias adicionadas automaticamente no onboarding: "
                            + ", ".join(sorted(set(obrigatorias_auto))),
                        )

                    ativacoes_bloqueadas: list[str] = []
                    ativacoes_disponiveis: list[dict] = []
                    for ativ in ativacoes:
                        tpl = ativ["template"]
                        if _template_is_installed(tpl, activation_counts_post):
                            ativacoes_bloqueadas.append(tpl.nome)
                            continue
                        ativacoes_disponiveis.append(ativ)

                    if ativacoes_bloqueadas:
                        messages.warning(
                            request,
                            "Alguns modelos já estão instalados e foram ignorados: "
                            + ", ".join(sorted(set(ativacoes_bloqueadas))[:5]),
                        )
                    ativacoes = ativacoes_disponiveis

                    if not ativacoes:
                        messages.error(
                            request,
                            "Selecione ao menos um modelo novo para ativação.",
                        )
                    else:
                        qtd_solicitada = sum(max(1, int(item["qtd"] or 1)) for item in ativacoes)
                        limite = None
                        try:
                            limite = verificar_limite_municipio(
                                municipio,
                                MetricaLimite.SECRETARIAS,
                                incremento=qtd_solicitada,
                            )
                        except Exception:
                            messages.warning(
                                request,
                                "Não foi possível validar limite de plano neste momento. "
                                "A instalação seguirá e será validada no faturamento.",
                            )

                        if limite is not None and not limite.permitido:
                            limite_secretarias_alert = {
                                "atual": limite.atual,
                                "limite": limite.limite,
                                "projetado": limite.projetado,
                                "excedente": limite.excedente,
                                "valor_unitario": _fmt_currency(limite.valor_unitario),
                                "valor_sugerido_mensal": _fmt_currency(limite.valor_sugerido_mensal),
                                "qtd_solicitada": qtd_solicitada,
                                "assinatura": limite.assinatura,
                            }
                            messages.error(
                                request,
                                "Essa instalação excede o limite de secretarias do plano atual. "
                                "Escolha troca de plano ou carrinho de extras.",
                            )
                        else:
                            credentials: list[dict] = []
                            install_errors: list[str] = []
                            for ativ in ativacoes:
                                tpl = ativ["template"]
                                qtd = max(1, int(ativ["qtd"]))
                                base_nome = ativ["nome"]
                                sigla = ativ["sigla"]
                                for i in range(qtd):
                                    if base_nome:
                                        nome_secretaria = base_nome if qtd == 1 else f"{base_nome} {i + 1}"
                                    else:
                                        nome_secretaria = tpl.nome if qtd == 1 else f"{tpl.nome} {i + 1}"
                                    try:
                                        result = provision_secretaria_from_template(
                                            municipio=municipio,
                                            template=tpl,
                                            solicitado_por=request.user,
                                            nome_secretaria=nome_secretaria,
                                            sigla=sigla,
                                        )
                                    except Exception:
                                        install_errors.append(nome_secretaria)
                                        continue
                                    credentials.append(
                                        {
                                            "secretaria": result.secretaria.nome if result.secretaria else "—",
                                            "username": result.gestor_username,
                                            "password": result.gestor_temp_password,
                                        }
                                    )

                            if install_errors:
                                messages.error(
                                    request,
                                    "Algumas secretarias não foram instaladas corretamente: "
                                    + ", ".join(install_errors[:5]),
                                )

                            if not credentials:
                                messages.error(
                                    request,
                                    "Nenhuma secretaria foi instalada. Revise nomes/siglas e tente novamente.",
                                )
                            else:
                                _seed_portais_base(municipio, request)
                                request.session["org_last_provision_credentials"] = credentials
                                messages.success(
                                    request,
                                    "Templates ativados com sucesso. Confira o painel de onboarding para os próximos passos.",
                                )
                                return redirect("org:onboarding_painel")
                except Exception as exc:
                    messages.error(
                        request,
                        f"Falha ao processar instalação de secretarias: {exc}",
                    )
            else:
                messages.error(request, "Corrija os campos de ativação dos templates.")
        else:
            form_municipio = OnboardingMunicipioForm(instance=municipio)
            form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
            form_ativacao = OnboardingTemplateActivationForm(templates=templates)
            messages.error(request, "Ação inválida.")
    else:
        form_municipio = OnboardingMunicipioForm(instance=municipio)
        form_plano = OnboardingPlanoForm(instance=assinatura, prefix="plano")
        form_ativacao = OnboardingTemplateActivationForm(templates=templates)

    activation_counts = _template_activation_counts(municipio, templates)
    template_rows = _build_template_rows(form_ativacao, templates, activation_counts=activation_counts)
    market_categories = _build_market_categories(template_rows)

    context = {
        "title": "Onboarding Inicial",
        "subtitle": "Configuração inicial da prefeitura e ativação de secretarias por modelo",
        "municipio": municipio,
        "assinatura": assinatura,
        "form_municipio": form_municipio,
        "form_plano": form_plano,
        "form_ativacao": form_ativacao,
        "template_rows": template_rows,
        "market_categories": market_categories,
        "market_installed_total": sum(1 for row in template_rows if row["is_installed"]),
        "limite_secretarias_alert": limite_secretarias_alert,
        "planos_upgrade": planos_upgrade,
        "template_choices": templates,
        "summary": {
            "templates_total": len(templates),
            "templates_ativos": sum(1 for t in templates if t.ativo),
            "modulos_ativos": (
                MunicipioModuloAtivo.objects.filter(municipio=municipio, ativo=True).count()
                if municipio
                else 0
            ),
            "plano_atual": assinatura.plano.nome if assinatura else "Não definido",
            "provisionamentos": (
                SecretariaProvisionamento.objects.filter(municipio=municipio).count()
                if municipio
                else 0
            ),
            "steps_total": OnboardingStep.objects.filter(municipio=municipio).count() if municipio else 0,
            "steps_concluidos": (
                OnboardingStep.objects.filter(municipio=municipio, status=OnboardingStep.Status.CONCLUIDO).count()
                if municipio
                else 0
            ),
        },
        "actions": [
            {
                "label": "Painel de Onboarding",
                "url": reverse("org:onboarding_painel"),
                "icon": "fa-solid fa-list-check",
                "variant": "btn--ghost",
            },
            {
                "label": "Voltar ao ORG",
                "url": reverse("org:index"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
        ],
    }
    return render(request, "org/onboarding_primeiro_acesso.html", context)


@login_required
@require_perm("org.view")
def onboarding_painel(request):
    if not _can_access_onboarding(request.user):
        return HttpResponseForbidden("403 — Apenas gestor municipal pode acessar o painel de onboarding.")

    municipio = _get_municipio_for_user(request.user)
    if not municipio:
        messages.error(request, "Cadastre um município para iniciar o onboarding.")
        return redirect("org:onboarding_primeiro_acesso")

    refresh_onboarding_progress(municipio)

    steps = list(
        OnboardingStep.objects.filter(municipio=municipio)
        .select_related("secretaria")
        .order_by("modulo", "ordem", "id")
    )
    provisionamentos = list(
        SecretariaProvisionamento.objects.filter(municipio=municipio)
        .select_related("template", "secretaria", "solicitado_por")
        .order_by("-criado_em")[:30]
    )
    modulos_ativos = list(
        MunicipioModuloAtivo.objects.filter(municipio=municipio, ativo=True).order_by("modulo")
    )

    grouped = defaultdict(list)
    for step in steps:
        grouped[(step.modulo, step.secretaria.nome if step.secretaria else "Escopo municipal")].append(step)

    modulo_cards = []
    for (modulo, secretaria_nome), items in grouped.items():
        total = len(items)
        concluidos = sum(1 for s in items if s.status == OnboardingStep.Status.CONCLUIDO)
        em_progresso = sum(1 for s in items if s.status == OnboardingStep.Status.EM_PROGRESSO)
        pendentes = total - concluidos - em_progresso
        progress = int((concluidos / total) * 100) if total else 0

        steps_render = []
        for s in items:
            url = ""
            if s.url_name:
                try:
                    url = reverse(s.url_name)
                except NoReverseMatch:
                    url = ""
            steps_render.append({"obj": s, "url": url})

        modulo_cards.append(
            {
                "modulo": modulo,
                "secretaria_nome": secretaria_nome,
                "total": total,
                "concluidos": concluidos,
                "em_progresso": em_progresso,
                "pendentes": pendentes,
                "progress": progress,
                "steps": steps_render,
            }
        )

    credentials = request.session.pop("org_last_provision_credentials", [])

    context = {
        "title": "Painel de Onboarding Municipal",
        "subtitle": f"Progresso de implantação de módulos e secretarias em {municipio.nome}",
        "municipio": municipio,
        "modulos_ativos": modulos_ativos,
        "modulo_cards": modulo_cards,
        "provisionamentos": provisionamentos,
        "credentials": credentials,
        "summary": {
            "modulos_ativos": len(modulos_ativos),
            "secretarias_em_implantacao": len({c["secretaria_nome"] for c in modulo_cards}),
            "steps_total": len(steps),
            "steps_concluidos": sum(1 for s in steps if s.status == OnboardingStep.Status.CONCLUIDO),
            "provisionamentos_total": len(provisionamentos),
            "provisionamentos_erro": sum(
                1 for p in provisionamentos if p.status == SecretariaProvisionamento.Status.ERRO
            ),
        },
        "actions": [
            {
                "label": "Executar Onboarding",
                "url": reverse("org:onboarding_primeiro_acesso"),
                "icon": "fa-solid fa-wand-magic-sparkles",
                "variant": "btn-primary",
            },
            {
                "label": "Voltar ao ORG",
                "url": reverse("org:index"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
        ],
    }
    return render(request, "org/onboarding_painel.html", context)
