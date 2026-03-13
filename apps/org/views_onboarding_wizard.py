from __future__ import annotations

import secrets
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Profile
from apps.billing.services import MetricaLimite, get_assinatura_ativa, verificar_limite_municipio
from apps.core.decorators import require_perm
from apps.core.rbac import get_profile, is_admin
from apps.org.forms_onboarding_wizard import (
    WizardAdminStepForm,
    WizardEnderecoStepForm,
    WizardModulosStepForm,
    WizardMunicipioStepForm,
    WizardPasswordStepForm,
    WizardRevisaoStepForm,
    WizardSecretariasStepForm,
    WizardUnidadesStepForm,
    WizardUsuariosStepForm,
)
from apps.org.models import (
    Municipio,
    MunicipioModuloAtivo,
    MunicipioOnboardingWizard,
    Secretaria,
    Setor,
    Unidade,
)

TOTAL_STEPS = 9

STEP_META: dict[int, dict[str, str]] = {
    1: {
        "title": "Troca obrigatória de senha",
        "description": "Defina uma nova senha para continuar a implantação.",
    },
    2: {
        "title": "Administrador da Prefeitura",
        "description": "Identifique o responsável pela implantação e defina o código de acesso final.",
    },
    3: {
        "title": "Cadastro institucional",
        "description": "Configure os dados institucionais da Prefeitura.",
    },
    4: {
        "title": "Endereço e localização",
        "description": "Defina o endereço principal e coordenadas da sede.",
    },
    5: {
        "title": "Secretarias iniciais",
        "description": "Ative Gestão, Educação e Saúde e selecione secretarias adicionais.",
    },
    6: {
        "title": "Estruturas iniciais",
        "description": "Cadastre escolas, unidades de saúde e setores de gestão. Não é necessário cadastrar unidades por secretaria.",
    },
    7: {
        "title": "Usuários iniciais",
        "description": "Crie os usuários mínimos para operar cada secretaria (Gestão, Educação e Saúde).",
    },
    8: {
        "title": "Módulos e checklist",
        "description": "Ative módulos essenciais e parâmetros iniciais.",
    },
    9: {
        "title": "Revisão final",
        "description": "Revise o resumo e conclua a implantação da prefeitura.",
    },
}


def _wizard_can_access(user) -> bool:
    if is_admin(user):
        return True
    profile = get_profile(user)
    if not profile or not getattr(profile, "ativo", True):
        return False
    return (profile.role or "").upper() == "MUNICIPAL"


def _wizard_for_user(user) -> MunicipioOnboardingWizard:
    profile = get_profile(user)
    defaults = {
        "municipio": getattr(profile, "municipio", None),
        "current_step": 1,
        "total_steps": TOTAL_STEPS,
        "draft_data": {},
    }
    wizard, _ = MunicipioOnboardingWizard.objects.get_or_create(user=user, defaults=defaults)

    if profile and profile.municipio_id and wizard.municipio_id != profile.municipio_id:
        wizard.municipio = profile.municipio
        wizard.save(update_fields=["municipio", "updated_at"])

    if wizard.total_steps != TOTAL_STEPS:
        wizard.total_steps = TOTAL_STEPS
        wizard.save(update_fields=["total_steps", "updated_at"])

    return wizard


def _completed_steps(wizard: MunicipioOnboardingWizard) -> set[int]:
    data = wizard.draft_data or {}
    raw = data.get("completed_steps") or []
    result: set[int] = set()
    for item in raw:
        try:
            step = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= step <= TOTAL_STEPS:
            result.add(step)
    return result


def _set_completed_steps(wizard: MunicipioOnboardingWizard, values: set[int]) -> None:
    data = dict(wizard.draft_data or {})
    data["completed_steps"] = sorted(values)
    wizard.draft_data = data


def _set_step_payload(wizard: MunicipioOnboardingWizard, step: int, payload: dict[str, Any]) -> None:
    data = dict(wizard.draft_data or {})
    by_step = dict(data.get("step_payloads") or {})
    by_step[str(step)] = payload
    data["step_payloads"] = by_step
    wizard.draft_data = data


def _get_step_payload(wizard: MunicipioOnboardingWizard, step: int) -> dict[str, Any]:
    data = wizard.draft_data or {}
    by_step = data.get("step_payloads") or {}
    payload = by_step.get(str(step))
    return payload if isinstance(payload, dict) else {}


def _mark_step_completed(wizard: MunicipioOnboardingWizard, step: int) -> None:
    done = _completed_steps(wizard)
    done.add(step)
    _set_completed_steps(wizard, done)

    if step < TOTAL_STEPS:
        wizard.current_step = max(1, min(TOTAL_STEPS, step + 1))
    else:
        wizard.current_step = TOTAL_STEPS


def _first_pending_step(wizard: MunicipioOnboardingWizard, profile: Profile | None) -> int:
    done = _completed_steps(wizard)

    must_change_password = bool(profile and profile.must_change_password)
    if must_change_password:
        return 1

    if 1 not in done:
        done.add(1)
        _set_completed_steps(wizard, done)
        wizard.save(update_fields=["draft_data", "updated_at"])

    for step in range(1, TOTAL_STEPS + 1):
        if step not in done:
            return step

    return TOTAL_STEPS


def _step_progress_percent(wizard: MunicipioOnboardingWizard) -> int:
    done_count = len(_completed_steps(wizard))
    return int((done_count / TOTAL_STEPS) * 100) if TOTAL_STEPS else 0


def _split_full_name(value: str) -> tuple[str, str]:
    tokens = [p for p in (value or "").strip().split() if p]
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], ""
    return tokens[0], " ".join(tokens[1:])


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _secretaria_sigla(nome: str) -> str:
    tokens = [t for t in (nome or "").replace("/", " ").split() if len(t) > 2]
    if not tokens:
        return "SEC"
    return "".join(token[0].upper() for token in tokens[:4])[:8] or "SEC"


def _get_or_create_secretaria(municipio: Municipio, nome: str, tipo_modelo: str) -> Secretaria:
    nome = (nome or "").strip()
    secretaria, created = Secretaria.objects.get_or_create(
        municipio=municipio,
        nome=nome,
        defaults={
            "sigla": _secretaria_sigla(nome),
            "tipo_modelo": tipo_modelo,
            "ativo": True,
        },
    )
    if not created:
        changed = False
        if not secretaria.sigla:
            secretaria.sigla = _secretaria_sigla(nome)
            changed = True
        if not secretaria.tipo_modelo:
            secretaria.tipo_modelo = tipo_modelo
            changed = True
        if not secretaria.ativo:
            secretaria.ativo = True
            changed = True
        if changed:
            secretaria.save(update_fields=["sigla", "tipo_modelo", "ativo"])
    return secretaria


def _parse_multiline(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def _parse_unidade_line(raw: str, default_tipo: str) -> tuple[str, str, str]:
    parts = [p.strip() for p in (raw or "").split("|")]
    nome = parts[0] if parts else ""
    tipo_choices = {choice[0] for choice in Unidade.Tipo.choices}

    tipo = default_tipo
    endereco = ""
    if len(parts) == 2:
        candidate = (parts[1] or "").strip().upper()
        if candidate in tipo_choices:
            tipo = candidate
        else:
            endereco = parts[1]
    elif len(parts) >= 3:
        candidate = (parts[1] or "").strip().upper()
        if candidate in tipo_choices:
            tipo = candidate
            endereco = parts[2]
        else:
            endereco = " | ".join(parts[1:])
    return nome, tipo, endereco


def _find_secretaria_by_modelo(municipio: Municipio, tipo_modelo: str, fallback_nome: str) -> Secretaria | None:
    sec = (
        Secretaria.objects.filter(municipio=municipio, tipo_modelo=tipo_modelo, ativo=True)
        .order_by("id")
        .first()
    )
    if sec:
        return sec
    return (
        Secretaria.objects.filter(municipio=municipio, nome__iexact=fallback_nome, ativo=True)
        .order_by("id")
        .first()
    )


def _username_candidate(base: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "." for ch in (base or "").strip())
    cleaned = ".".join(part for part in cleaned.split(".") if part)
    return cleaned[:120] or f"user{secrets.randbelow(10_000)}"


def _build_unique_username(seed: str) -> str:
    User = get_user_model()
    base = _username_candidate(seed)
    candidate = base
    idx = 2
    while User.objects.filter(username__iexact=candidate).exists():
        suffix = f".{idx}"
        candidate = f"{base[: max(1, 150 - len(suffix))]}{suffix}"
        idx += 1
    return candidate


def _upsert_initial_user(
    *,
    municipio: Municipio,
    secretaria: Secretaria,
    role: str,
    nome: str,
    cpf: str,
    email: str,
) -> dict[str, str]:
    User = get_user_model()
    email_norm = (email or "").strip().lower()
    user = User.objects.filter(email__iexact=email_norm).order_by("id").first() if email_norm else None
    created = False

    if not user:
        first_name, last_name = _split_full_name(nome)
        username = _build_unique_username(email_norm.split("@")[0] if email_norm else nome)
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email_norm,
            is_active=True,
        )
        created = True

    first_name, last_name = _split_full_name(nome)
    user.first_name = first_name
    user.last_name = last_name
    user.email = email_norm
    user.is_active = True

    temp_password = ""
    if created:
        temp_password = secrets.token_urlsafe(8)
        user.set_password(temp_password)
    user.save()

    profile, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})
    profile.role = role
    profile.municipio = municipio
    profile.secretaria = secretaria
    profile.ativo = True
    profile.bloqueado = False
    profile.cpf = cpf
    if created:
        profile.must_change_password = True
    profile.save()

    return {
        "nome": nome,
        "username": user.username,
        "codigo_acesso": profile.codigo_acesso,
        "email": email_norm,
        "senha_temporaria": temp_password,
        "status": "criado" if created else "existente",
    }


def _will_increment_user_limit(*, municipio: Municipio, email: str) -> bool:
    email_norm = (email or "").strip().lower()
    if not email_norm:
        return True

    User = get_user_model()
    user = User.objects.filter(email__iexact=email_norm).order_by("id").first()
    if not user:
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return True

    if profile.municipio_id == municipio.id and profile.ativo and not profile.bloqueado:
        return False
    return True


def _ensure_base_secretarias(municipio: Municipio) -> dict[str, Secretaria]:
    return {
        "gestao": _get_or_create_secretaria(municipio, "Secretaria de Gestão Municipal", "administracao"),
        "educacao": _get_or_create_secretaria(municipio, "Secretaria de Educação", "educacao"),
        "saude": _get_or_create_secretaria(municipio, "Secretaria de Saúde", "saude"),
    }


def _render_step(request, wizard: MunicipioOnboardingWizard, step: int, form, extra: dict | None = None):
    extra = extra or {}
    done = _completed_steps(wizard)
    first_pending = _first_pending_step(wizard, get_profile(request.user))

    steps = []
    for idx in range(1, TOTAL_STEPS + 1):
        meta = STEP_META[idx]
        if idx in done:
            status = "done"
        elif idx == first_pending and not wizard.is_completed:
            status = "current"
        else:
            status = "pending"
        steps.append(
            {
                "index": idx,
                "title": meta["title"],
                "status": status,
            }
        )

    context = {
        "wizard": wizard,
        "wizard_step": step,
        "wizard_total_steps": TOTAL_STEPS,
        "wizard_progress_pct": _step_progress_percent(wizard),
        "wizard_steps": steps,
        "step_title": STEP_META[step]["title"],
        "step_description": STEP_META[step]["description"],
        "form": form,
        "can_go_back": step > 1,
        "back_step": max(1, step - 1),
    }
    context.update(extra)
    return render(request, "org/onboarding/wizard.html", context)


@login_required
@require_perm("org.view")
def onboarding_wizard(request):
    if not _wizard_can_access(request.user):
        return HttpResponseForbidden("403 — Apenas gestor municipal pode executar este onboarding.")

    wizard = _wizard_for_user(request.user)
    profile = get_profile(request.user)
    if not profile:
        profile, _ = Profile.objects.get_or_create(user=request.user, defaults={"ativo": True})

    if wizard.is_completed:
        return redirect("core:dashboard")

    next_step = _first_pending_step(wizard, profile)
    return redirect("org:onboarding_wizard_step", step=next_step)


@login_required
@require_perm("org.view")
def onboarding_wizard_step(request, step: int):
    if not _wizard_can_access(request.user):
        return HttpResponseForbidden("403 — Apenas gestor municipal pode executar este onboarding.")

    if step < 1 or step > TOTAL_STEPS:
        return redirect("org:onboarding_wizard")

    wizard = _wizard_for_user(request.user)
    profile = get_profile(request.user)
    if not profile:
        profile, _ = Profile.objects.get_or_create(user=request.user, defaults={"ativo": True})
    if wizard.is_completed:
        return redirect("core:dashboard")

    first_pending = _first_pending_step(wizard, profile)
    if step > first_pending:
        return redirect("org:onboarding_wizard_step", step=first_pending)

    action = (request.POST.get("action") or "continue").strip().lower() if request.method == "POST" else ""
    if request.method == "POST" and action == "save_exit":
        raw_payload = {
            k: v
            for k, v in request.POST.items()
            if k not in {"csrfmiddlewaretoken", "action"}
        }
        _set_step_payload(wizard, step, raw_payload)
        wizard.save(update_fields=["draft_data", "updated_at"])
        messages.info(request, "Progresso salvo. Você pode continuar depois.")
        return redirect("accounts:logout")

    if step == 1:
        form = WizardPasswordStepForm(request.POST or None, user=request.user)
        if request.method == "POST" and action == "continue" and form.is_valid():
            new_password = form.cleaned_data.get("new_password1") or ""
            if profile and profile.cpf_digits and _digits(new_password) == profile.cpf_digits:
                form.add_error("new_password1", "A nova senha não pode ser igual ao CPF.")
            else:
                request.user.set_password(new_password)
                request.user.save(update_fields=["password"])

                if profile:
                    profile.must_change_password = False
                    profile.password_changed_at = timezone.now()
                    if not profile.password_expires_days:
                        profile.password_expires_days = 90
                    profile.save(update_fields=["must_change_password", "password_changed_at", "password_expires_days"])

                update_session_auth_hash(request, request.user)
                _set_step_payload(wizard, 1, {"changed_at": timezone.now().isoformat()})
                _mark_step_completed(wizard, 1)
                wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
                messages.success(request, "Senha atualizada. Continue o onboarding.")
                return redirect("org:onboarding_wizard_step", step=2)

        return _render_step(request, wizard, step, form)

    if step == 2:
        initial = _get_step_payload(wizard, 2)
        if not initial:
            initial = {
                "nome_completo": request.user.get_full_name() or request.user.username,
                "codigo_acesso": getattr(profile, "codigo_acesso", "") if profile else "",
                "cpf": getattr(profile, "cpf", "") if profile else "",
                "email": request.user.email or "",
            }
        form = WizardAdminStepForm(request.POST or None, initial=initial)

        if request.method == "POST" and action == "continue" and form.is_valid():
            cleaned = form.cleaned_data
            novo_codigo = (cleaned.get("codigo_acesso") or "").strip().lower()
            if Profile.objects.filter(codigo_acesso__iexact=novo_codigo).exclude(user=request.user).exists():
                form.add_error("codigo_acesso", "Este código de acesso já está em uso por outro usuário.")
                return _render_step(request, wizard, step, form)

            first_name, last_name = _split_full_name(cleaned["nome_completo"])
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = cleaned["email"]
            request.user.save(update_fields=["first_name", "last_name", "email"])

            if profile:
                profile.cpf = cleaned["cpf"]
                profile.codigo_acesso = novo_codigo
                profile.save(update_fields=["cpf", "codigo_acesso"])

            _set_step_payload(wizard, 2, cleaned)
            _mark_step_completed(wizard, 2)
            wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
            return redirect("org:onboarding_wizard_step", step=3)

        return _render_step(request, wizard, step, form)

    if step == 3:
        municipio = wizard.municipio or (profile.municipio if profile and profile.municipio_id else None)
        initial = _get_step_payload(wizard, 3)
        form = WizardMunicipioStepForm(request.POST or None, instance=municipio, initial=initial)

        if request.method == "POST" and action == "continue" and form.is_valid():
            cleaned = form.cleaned_data
            with transaction.atomic():
                if municipio is None:
                    municipio_nome = cleaned["municipio_nome"]
                    uf = cleaned["uf"]
                    municipio = Municipio.objects.filter(nome__iexact=municipio_nome).first()
                    if municipio is None:
                        municipio = Municipio.objects.create(nome=municipio_nome, uf=uf)
                    elif municipio.uf != uf:
                        municipio.uf = uf
                        municipio.save(update_fields=["uf"])

                municipio.nome = cleaned["municipio_nome"]
                municipio.uf = cleaned["uf"]
                municipio.razao_social_prefeitura = cleaned.get("razao_social_prefeitura") or ""
                municipio.nome_fantasia_prefeitura = cleaned.get("nome_fantasia_prefeitura") or ""
                municipio.cnpj_prefeitura = cleaned.get("cnpj_prefeitura") or ""
                municipio.email_prefeitura = cleaned.get("email_prefeitura") or ""
                municipio.telefone_prefeitura = cleaned.get("telefone_prefeitura") or ""
                municipio.site_prefeitura = cleaned.get("site_prefeitura") or ""
                municipio.save()
                # Garante assinatura base para aplicar políticas de plano desde o onboarding.
                get_assinatura_ativa(municipio, criar_default=True)

                wizard.municipio = municipio
                if profile and profile.municipio_id != municipio.id:
                    profile.municipio = municipio
                    profile.save(update_fields=["municipio"])

                payload = {
                    "municipio_nome": municipio.nome,
                    "uf": municipio.uf,
                    "razao_social_prefeitura": municipio.razao_social_prefeitura,
                    "nome_fantasia_prefeitura": municipio.nome_fantasia_prefeitura,
                    "cnpj_prefeitura": municipio.cnpj_prefeitura,
                    "email_prefeitura": municipio.email_prefeitura,
                    "telefone_prefeitura": municipio.telefone_prefeitura,
                    "site_prefeitura": municipio.site_prefeitura,
                }
                _set_step_payload(wizard, 3, payload)
                _mark_step_completed(wizard, 3)
                wizard.save(update_fields=["municipio", "draft_data", "current_step", "updated_at"])

            return redirect("org:onboarding_wizard_step", step=4)

        return _render_step(request, wizard, step, form)

    if step == 4:
        initial = _get_step_payload(wizard, 4)
        form = WizardEnderecoStepForm(request.POST or None, initial=initial)

        if request.method == "POST" and action == "continue" and form.is_valid():
            cleaned = form.cleaned_data
            if wizard.municipio_id:
                municipio = wizard.municipio
                municipio.endereco_prefeitura = (
                    f"{cleaned['logradouro']}, {cleaned['numero']}"
                    f" - {cleaned['bairro']} - {cleaned['cidade']}/{cleaned['uf']}"
                    f" - CEP {cleaned['cep']}"
                )
                municipio.save(update_fields=["endereco_prefeitura"])

            payload = {
                "cep": cleaned["cep"],
                "logradouro": cleaned["logradouro"],
                "numero": cleaned["numero"],
                "complemento": cleaned.get("complemento") or "",
                "bairro": cleaned["bairro"],
                "cidade": cleaned["cidade"],
                "uf": cleaned["uf"],
                "latitude": str(cleaned.get("latitude") or ""),
                "longitude": str(cleaned.get("longitude") or ""),
            }
            _set_step_payload(wizard, 4, payload)
            _mark_step_completed(wizard, 4)
            wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
            return redirect("org:onboarding_wizard_step", step=5)

        return _render_step(request, wizard, step, form)

    if step == 5:
        form = WizardSecretariasStepForm(request.POST or None, initial=_get_step_payload(wizard, 5))

        if request.method == "POST" and action == "continue" and form.is_valid():
            if not wizard.municipio_id:
                messages.error(request, "Configure os dados da prefeitura antes de ativar secretarias.")
                return redirect("org:onboarding_wizard_step", step=3)

            municipio = wizard.municipio
            _ensure_base_secretarias(municipio)

            optional_map = {
                "secretaria_assistencia_social": ("Secretaria de Assistência Social", "assistencia"),
                "secretaria_financas": ("Secretaria de Finanças", "financas"),
                "secretaria_obras": ("Secretaria de Obras", "obras"),
                "secretaria_agricultura": ("Secretaria de Agricultura", "agricultura"),
                "secretaria_cultura": ("Secretaria de Cultura", "cultura"),
                "secretaria_esporte": ("Secretaria de Esporte", "cultura"),
                "secretaria_meio_ambiente": ("Secretaria de Meio Ambiente", "meio_ambiente"),
                "secretaria_transporte": ("Secretaria de Transporte", "transporte"),
            }
            selected_names = [
                "Secretaria de Gestão Municipal",
                "Secretaria de Educação",
                "Secretaria de Saúde",
            ]
            for key, (nome, modelo) in optional_map.items():
                if form.cleaned_data.get(key):
                    _get_or_create_secretaria(municipio, nome, modelo)
                    selected_names.append(nome)

            for custom_name in _parse_multiline(form.cleaned_data.get("secretarias_personalizadas") or ""):
                _get_or_create_secretaria(municipio, custom_name, "outro")
                selected_names.append(custom_name)

            payload = dict(form.cleaned_data)
            payload["secretarias_ativas"] = selected_names
            _set_step_payload(wizard, 5, payload)
            _mark_step_completed(wizard, 5)
            wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
            return redirect("org:onboarding_wizard_step", step=6)

        return _render_step(request, wizard, step, form)

    if step == 6:
        form = WizardUnidadesStepForm(request.POST or None, initial=_get_step_payload(wizard, 6))

        if request.method == "POST" and action == "continue" and form.is_valid():
            if not wizard.municipio_id:
                messages.error(request, "Configure os dados da prefeitura antes de cadastrar unidades.")
                return redirect("org:onboarding_wizard_step", step=3)

            municipio = wizard.municipio
            base_secretarias = _ensure_base_secretarias(municipio)
            sec_edu = _find_secretaria_by_modelo(municipio, "educacao", "Secretaria de Educação") or base_secretarias["educacao"]
            sec_sau = _find_secretaria_by_modelo(municipio, "saude", "Secretaria de Saúde") or base_secretarias["saude"]
            sec_ges = _find_secretaria_by_modelo(municipio, "administracao", "Secretaria de Gestão Municipal") or base_secretarias["gestao"]

            escolas = _parse_multiline(form.cleaned_data["escolas"])
            unidades_saude = _parse_multiline(form.cleaned_data["unidades_saude"])
            setores_gestao = _parse_multiline(form.cleaned_data["setores_gestao"])

            escolas_count = 0
            saude_count = 0
            setor_count = 0

            for line in escolas:
                nome, tipo_valor, endereco = _parse_unidade_line(line, Unidade.Tipo.EDUCACAO)
                if not nome:
                    continue
                Unidade.objects.get_or_create(
                    secretaria=sec_edu,
                    nome=nome,
                    defaults={
                        "tipo": tipo_valor,
                        "endereco": endereco,
                        "ativo": True,
                    },
                )
                escolas_count += 1

            for line in unidades_saude:
                nome, tipo_valor, endereco = _parse_unidade_line(line, Unidade.Tipo.SAUDE)
                if not nome:
                    continue
                Unidade.objects.get_or_create(
                    secretaria=sec_sau,
                    nome=nome,
                    defaults={
                        "tipo": tipo_valor,
                        "endereco": endereco,
                        "ativo": True,
                    },
                )
                saude_count += 1

            unidade_gestao, _ = Unidade.objects.get_or_create(
                secretaria=sec_ges,
                nome="Sede Administrativa",
                defaults={"tipo": Unidade.Tipo.ADMINISTRACAO, "ativo": True},
            )

            for nome_setor in setores_gestao:
                Setor.objects.get_or_create(unidade=unidade_gestao, nome=nome_setor, defaults={"ativo": True})
                setor_count += 1

            payload = {
                "escolas": form.cleaned_data["escolas"],
                "unidades_saude": form.cleaned_data["unidades_saude"],
                "setores_gestao": form.cleaned_data["setores_gestao"],
                "resumo": {
                    "escolas": escolas_count,
                    "unidades_saude": saude_count,
                    "setores_gestao": setor_count,
                },
            }
            _set_step_payload(wizard, 6, payload)
            _mark_step_completed(wizard, 6)
            wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
            return redirect("org:onboarding_wizard_step", step=7)

        return _render_step(request, wizard, step, form)

    if step == 7:
        form = WizardUsuariosStepForm(request.POST or None, initial=_get_step_payload(wizard, 7))

        if request.method == "POST" and action == "continue" and form.is_valid():
            if not wizard.municipio_id:
                messages.error(request, "Configure os dados da prefeitura antes de criar usuários.")
                return redirect("org:onboarding_wizard_step", step=3)

            municipio = wizard.municipio
            base_secretarias = _ensure_base_secretarias(municipio)
            sec_edu = _find_secretaria_by_modelo(municipio, "educacao", "Secretaria de Educação") or base_secretarias["educacao"]
            sec_sau = _find_secretaria_by_modelo(municipio, "saude", "Secretaria de Saúde") or base_secretarias["saude"]
            sec_ges = _find_secretaria_by_modelo(municipio, "administracao", "Secretaria de Gestão Municipal") or base_secretarias["gestao"]

            incremento = 0
            for email in [
                form.cleaned_data["gestao_email"],
                form.cleaned_data["educacao_email"],
                form.cleaned_data["saude_email"],
            ]:
                if _will_increment_user_limit(municipio=municipio, email=email):
                    incremento += 1
            if incremento > 0:
                limite = verificar_limite_municipio(
                    municipio,
                    MetricaLimite.USUARIOS,
                    incremento=incremento,
                )
                if not limite.permitido:
                    form.add_error(
                        None,
                        (
                            f"Limite de usuários do plano excedido ({limite.atual}/{limite.limite}). "
                            f"Necessário ampliar {limite.excedente} usuário(s) para concluir esta etapa."
                        ),
                    )
                    return _render_step(request, wizard, step, form)

            creds = []
            creds.append(
                _upsert_initial_user(
                    municipio=municipio,
                    secretaria=sec_ges,
                    role=Profile.Role.PROTOCOLO,
                    nome=form.cleaned_data["gestao_nome"],
                    cpf=form.cleaned_data["gestao_cpf"],
                    email=form.cleaned_data["gestao_email"],
                )
            )
            creds.append(
                _upsert_initial_user(
                    municipio=municipio,
                    secretaria=sec_edu,
                    role=Profile.Role.EDU_SECRETARIO,
                    nome=form.cleaned_data["educacao_nome"],
                    cpf=form.cleaned_data["educacao_cpf"],
                    email=form.cleaned_data["educacao_email"],
                )
            )
            creds.append(
                _upsert_initial_user(
                    municipio=municipio,
                    secretaria=sec_sau,
                    role=Profile.Role.SAU_SECRETARIO,
                    nome=form.cleaned_data["saude_nome"],
                    cpf=form.cleaned_data["saude_cpf"],
                    email=form.cleaned_data["saude_email"],
                )
            )

            payload = dict(form.cleaned_data)
            payload["credenciais"] = creds
            _set_step_payload(wizard, 7, payload)
            _mark_step_completed(wizard, 7)
            wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
            return redirect("org:onboarding_wizard_step", step=8)

        return _render_step(request, wizard, step, form)

    if step == 8:
        initial = _get_step_payload(wizard, 8)
        if not initial:
            initial = {"ano_letivo_atual": timezone.localdate().year}
        form = WizardModulosStepForm(request.POST or None, initial=initial)

        if request.method == "POST" and action == "continue" and form.is_valid():
            if not wizard.municipio_id:
                messages.error(request, "Configure os dados da prefeitura antes de ativar módulos.")
                return redirect("org:onboarding_wizard_step", step=3)

            municipio = wizard.municipio
            module_flags = {
                "educacao": True,
                "saude": True,
                "nee": bool(form.cleaned_data.get("ativar_nee")),
                "comunicacao": bool(
                    form.cleaned_data.get("configurar_smtp")
                    or form.cleaned_data.get("configurar_whatsapp")
                    or form.cleaned_data.get("configurar_sms")
                ),
            }

            for module, active in module_flags.items():
                MunicipioModuloAtivo.objects.update_or_create(
                    municipio=municipio,
                    modulo=module,
                    defaults={"ativo": active},
                )

            payload = {
                "ativar_educacao": True,
                "ativar_saude": True,
                "ativar_nee": bool(form.cleaned_data.get("ativar_nee")),
                "ano_letivo_atual": form.cleaned_data["ano_letivo_atual"],
                "configurar_smtp": bool(form.cleaned_data.get("configurar_smtp")),
                "configurar_whatsapp": bool(form.cleaned_data.get("configurar_whatsapp")),
                "configurar_sms": bool(form.cleaned_data.get("configurar_sms")),
            }
            _set_step_payload(wizard, 8, payload)
            _mark_step_completed(wizard, 8)
            wizard.save(update_fields=["draft_data", "current_step", "updated_at"])
            return redirect("org:onboarding_wizard_step", step=9)

        return _render_step(request, wizard, step, form)

    if step == 9:
        form = WizardRevisaoStepForm(request.POST or None)
        step7_payload = _get_step_payload(wizard, 7)
        credenciais = step7_payload.get("credenciais") if isinstance(step7_payload, dict) else []
        context_extra = {
            "resumo_steps": {
                "admin": _get_step_payload(wizard, 2),
                "municipio": _get_step_payload(wizard, 3),
                "endereco": _get_step_payload(wizard, 4),
                "secretarias": _get_step_payload(wizard, 5),
                "unidades": _get_step_payload(wizard, 6),
                "modulos": _get_step_payload(wizard, 8),
            },
            "credenciais_iniciais": credenciais,
        }

        if request.method == "POST" and action == "continue" and form.is_valid():
            _set_step_payload(wizard, 9, {"confirmed_at": timezone.now().isoformat()})
            _mark_step_completed(wizard, 9)
            wizard.completed_at = timezone.now()
            wizard.current_step = TOTAL_STEPS
            wizard.save(update_fields=["draft_data", "current_step", "completed_at", "updated_at"])
            messages.success(request, "Implantação concluída com sucesso. Bem-vindo ao GEPUB.")
            return redirect("core:dashboard")

        return _render_step(request, wizard, step, form, extra=context_extra)

    return redirect("org:onboarding_wizard")


@login_required
@require_perm("org.view")
def onboarding_wizard_autosave(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método não permitido."}, status=405)

    if not _wizard_can_access(request.user):
        return JsonResponse({"ok": False, "error": "Sem permissão."}, status=403)

    wizard = _wizard_for_user(request.user)
    try:
        step = int((request.POST.get("step") or "0").strip())
    except (TypeError, ValueError):
        step = 0

    if step < 1 or step > TOTAL_STEPS:
        return JsonResponse({"ok": False, "error": "Etapa inválida."}, status=400)

    payload = {
        k: v
        for k, v in request.POST.items()
        if k not in {"csrfmiddlewaretoken", "step"}
    }

    data = dict(wizard.draft_data or {})
    autosave = dict(data.get("autosave") or {})
    autosave[str(step)] = payload
    data["autosave"] = autosave
    wizard.draft_data = data
    wizard.save(update_fields=["draft_data", "updated_at"])

    return JsonResponse({"ok": True, "saved_at": timezone.now().isoformat()})
