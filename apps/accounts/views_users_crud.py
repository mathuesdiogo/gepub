from __future__ import annotations

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.billing.services import MetricaLimite, verificar_limite_municipio
from apps.core.decorators import require_perm
from apps.core.rbac import get_profile, is_admin

from .forms import UsuarioCreateForm, UsuarioUpdateForm
from .models import Profile, UserManagementAudit
from .views_users_common import (
    User,
    can_manage_users,
    log_user_action,
    scope_users_queryset,
)

_ROLE_ALLOWED_BY_MANAGER = {
    "MUNICIPAL": {"SECRETARIA", "UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
    "SECRETARIA": {"UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
    "UNIDADE": {"PROFESSOR", "ALUNO", "NEE", "LEITURA"},
}


def _sync_user_active(user, profile: Profile):
    user.is_active = bool(profile.ativo and not profile.bloqueado)
    user.save(update_fields=["is_active"])


def _assign_scope_by_actor_or_form(*, actor, profile: Profile, form_cleaned: dict):
    p_me = get_profile(actor)
    if not is_admin(actor) and p_me:
        profile.municipio_id = getattr(p_me, "municipio_id", None)
        profile.secretaria_id = getattr(p_me, "secretaria_id", None)
        profile.unidade_id = getattr(p_me, "unidade_id", None)
        profile.setor_id = getattr(p_me, "setor_id", None)
        return

    profile.municipio = form_cleaned.get("municipio")
    profile.secretaria = form_cleaned.get("secretaria")
    profile.unidade = form_cleaned.get("unidade")
    profile.setor = form_cleaned.get("setor")


@login_required
@require_perm("accounts.manage_users")
@require_http_methods(["GET", "POST"])
def usuario_create(request):
    if not can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para criar usuários.")
        return redirect("core:dashboard")

    form = UsuarioCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        role_new = form.cleaned_data["role"]
        p_me = get_profile(request.user)
        role_me = (getattr(p_me, "role", None) or "").upper()

        if not is_admin(request.user) and role_new not in _ROLE_ALLOWED_BY_MANAGER.get(role_me, set()):
            messages.error(request, "Você não pode criar esse tipo de usuário.")
            return redirect("accounts:usuarios_list")

        municipio_alvo = form.cleaned_data.get("municipio")
        if (not is_admin(request.user)) and p_me and getattr(p_me, "municipio", None):
            municipio_alvo = p_me.municipio

        if municipio_alvo and bool(form.cleaned_data.get("ativo", True)):
            limite = verificar_limite_municipio(
                municipio_alvo,
                MetricaLimite.USUARIOS,
                incremento=1,
            )
            if not limite.permitido:
                upgrade_url = reverse("billing:solicitar_upgrade")
                upgrade_url += f"?municipio={municipio_alvo.pk}&tipo=USUARIOS&qtd={limite.excedente}"
                messages.error(
                    request,
                    (
                        f"Limite de usuários excedido ({limite.atual}/{limite.limite}). "
                        f"Solicite upgrade em: {upgrade_url}"
                    ),
                )
                return redirect("accounts:usuarios_list")

        username = f"u{secrets.token_hex(10)}"
        user = User(
            username=username,
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            email=form.cleaned_data["email"] or "",
        )

        cpf_digits = "".join(ch for ch in (form.cleaned_data["cpf"] or "") if ch.isdigit())
        user.set_password(cpf_digits)
        user.is_active = True
        user.save()

        prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})
        prof.cpf = form.cleaned_data["cpf"]
        prof.role = role_new
        prof.ativo = bool(form.cleaned_data.get("ativo", True))
        prof.bloqueado = False
        _assign_scope_by_actor_or_form(actor=request.user, profile=prof, form_cleaned=form.cleaned_data)
        prof.must_change_password = True
        prof.save()
        _sync_user_active(user, prof)

        if prof.role == "PROFESSOR":
            user.turmas_ministradas.set(form.cleaned_data.get("turmas") or [])
        else:
            user.turmas_ministradas.clear()

        log_user_action(
            actor=request.user,
            target=user,
            action=UserManagementAudit.Action.CREATE,
            details=f"role={prof.role}; municipio={prof.municipio_id}; secretaria={prof.secretaria_id}; unidade={prof.unidade_id}; setor={prof.setor_id}",
        )

        messages.success(
            request,
            f"Usuário criado. Código de acesso: {prof.codigo_acesso}. Senha inicial: CPF. (Troca obrigatória no 1º acesso)",
        )
        return redirect("accounts:usuarios_list")

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "mode": "create",
            "title": "Novo usuário",
            "subtitle": "Cadastro de conta e lotação organizacional",
            "actions": [
                {"label": "Voltar", "url": reverse("accounts:usuarios_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            ],
        },
    )


@login_required
@require_perm("accounts.manage_users")
@require_http_methods(["GET", "POST"])
def usuario_update(request, pk: int):
    if not can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para editar usuários.")
        return redirect("core:dashboard")

    user = get_object_or_404(scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    initial = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "cpf": prof.cpf_digits,
        "role": prof.role,
        "municipio": prof.municipio_id,
        "secretaria": prof.secretaria_id,
        "unidade": prof.unidade_id,
        "setor": prof.setor_id,
        "ativo": prof.ativo,
        "turmas": user.turmas_ministradas.all(),
    }

    form = UsuarioUpdateForm(
        request.POST or None,
        user=request.user,
        edited_user=user,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        municipio_anterior_id = prof.municipio_id
        estava_contabilizado = bool(prof.ativo and not prof.bloqueado)

        role_new = form.cleaned_data["role"]
        p_me = get_profile(request.user)
        role_me = (getattr(p_me, "role", None) or "").upper()
        if not is_admin(request.user) and role_new not in _ROLE_ALLOWED_BY_MANAGER.get(role_me, set()):
            messages.error(request, "Você não pode alterar para esse tipo de função.")
            return redirect("accounts:usuarios_list")

        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"] or ""
        user.save(update_fields=["first_name", "last_name", "email"])

        prof.cpf = form.cleaned_data.get("cpf") or prof.cpf_digits
        prof.role = role_new
        prof.ativo = bool(form.cleaned_data.get("ativo", True))
        _assign_scope_by_actor_or_form(actor=request.user, profile=prof, form_cleaned=form.cleaned_data)

        ficara_contabilizado = bool(prof.ativo and not prof.bloqueado)
        mudou_municipio = municipio_anterior_id != prof.municipio_id
        precisa_incremento = ficara_contabilizado and (not estava_contabilizado or mudou_municipio)
        if precisa_incremento and prof.municipio_id:
            limite = verificar_limite_municipio(
                prof.municipio,
                MetricaLimite.USUARIOS,
                incremento=1,
            )
            if not limite.permitido:
                upgrade_url = reverse("billing:solicitar_upgrade")
                upgrade_url += f"?municipio={prof.municipio_id}&tipo=USUARIOS&qtd={limite.excedente}"
                messages.error(
                    request,
                    (
                        f"Limite de usuários excedido ({limite.atual}/{limite.limite}). "
                        f"Solicite upgrade em: {upgrade_url}"
                    ),
                )
                return redirect("accounts:usuarios_list")

        prof.save()
        _sync_user_active(user, prof)

        if prof.role == "PROFESSOR":
            user.turmas_ministradas.set(form.cleaned_data.get("turmas") or [])
        else:
            user.turmas_ministradas.clear()

        log_user_action(
            actor=request.user,
            target=user,
            action=UserManagementAudit.Action.UPDATE,
            details=f"role={prof.role}; ativo={prof.ativo}; bloqueado={prof.bloqueado}; municipio={prof.municipio_id}; secretaria={prof.secretaria_id}; unidade={prof.unidade_id}; setor={prof.setor_id}",
        )

        messages.success(request, "Usuário atualizado.")
        return redirect("accounts:usuario_detail", pk=user.pk)

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "mode": "update",
            "u": user,
            "title": "Editar usuário",
            "subtitle": "Ajuste de função, lotação e status",
            "actions": [
                {"label": "Detalhes", "url": reverse("accounts:usuario_detail", args=[user.pk]), "icon": "fa-solid fa-id-card", "variant": "btn--ghost"},
                {"label": "Voltar", "url": reverse("accounts:usuarios_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            ],
        },
    )


@login_required
@require_perm("accounts.manage_users")
def usuario_detail(request, pk: int):
    user = get_object_or_404(scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})
    logs = list(
        UserManagementAudit.objects.select_related("actor")
        .filter(target=user)
        .order_by("-created_at")[:20]
    )

    status = "BLOQUEADO" if prof.bloqueado else ("ATIVO" if prof.ativo else "INATIVO")
    fields = [
        {"label": "Nome", "value": user.get_full_name() or user.username},
        {"label": "Username técnico", "value": user.username},
        {"label": "E-mail", "value": user.email or "—"},
        {"label": "Código de acesso", "value": prof.codigo_acesso or "—"},
        {"label": "Função", "value": prof.get_role_display() if prof.role else "—"},
        {"label": "Status", "value": status},
        {"label": "Município", "value": str(prof.municipio) if prof.municipio else "—"},
        {"label": "Secretaria", "value": str(prof.secretaria) if prof.secretaria else "—"},
        {"label": "Unidade", "value": str(prof.unidade) if prof.unidade else "—"},
        {"label": "Setor", "value": str(prof.setor) if prof.setor else "—"},
        {"label": "Último login", "value": user.last_login.strftime("%d/%m/%Y %H:%M") if user.last_login else "Nunca"},
    ]
    pills = [
        {"label": "Ativo", "value": "Sim" if prof.ativo else "Não"},
        {"label": "Bloqueado", "value": "Sim" if prof.bloqueado else "Não"},
        {"label": "Troca de senha pendente", "value": "Sim" if prof.must_change_password else "Não"},
    ]

    return render(
        request,
        "accounts/user_detail.html",
        {
            "title": user.get_full_name() or user.username,
            "subtitle": "Detalhes e auditoria da conta",
            "actions": [
                {"label": "Editar", "url": reverse("accounts:usuario_update", args=[user.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
                {"label": "Voltar", "url": reverse("accounts:usuarios_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            ],
            "fields": fields,
            "pills": pills,
            "u": user,
            "profile_obj": prof,
            "logs": logs,
        },
    )


@login_required
@require_perm("accounts.manage_users")
@require_http_methods(["POST"])
def usuario_toggle_ativo(request, pk: int):
    user = get_object_or_404(scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    vai_ativar = (not prof.ativo) and (not prof.bloqueado)
    if vai_ativar and prof.municipio_id:
        limite = verificar_limite_municipio(
            prof.municipio,
            MetricaLimite.USUARIOS,
            incremento=1,
        )
        if not limite.permitido:
            upgrade_url = reverse("billing:solicitar_upgrade")
            upgrade_url += f"?municipio={prof.municipio_id}&tipo=USUARIOS&qtd={limite.excedente}"
            messages.error(
                request,
                (
                    f"Limite de usuários excedido ({limite.atual}/{limite.limite}). "
                    f"Solicite upgrade em: {upgrade_url}"
                ),
            )
            return redirect(request.POST.get("next") or reverse("accounts:usuarios_list"))

    prof.ativo = not prof.ativo
    prof.save(update_fields=["ativo"])
    _sync_user_active(user, prof)

    action = UserManagementAudit.Action.ACTIVATE if prof.ativo else UserManagementAudit.Action.DEACTIVATE
    log_user_action(actor=request.user, target=user, action=action, details=f"ativo={prof.ativo}")

    messages.success(request, "Status de ativação atualizado.")
    return redirect(request.POST.get("next") or reverse("accounts:usuarios_list"))


@login_required
@require_perm("accounts.manage_users")
@require_http_methods(["POST"])
def usuario_toggle_bloqueio(request, pk: int):
    user = get_object_or_404(scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    vai_desbloquear = prof.bloqueado and prof.ativo
    if vai_desbloquear and prof.municipio_id:
        limite = verificar_limite_municipio(
            prof.municipio,
            MetricaLimite.USUARIOS,
            incremento=1,
        )
        if not limite.permitido:
            upgrade_url = reverse("billing:solicitar_upgrade")
            upgrade_url += f"?municipio={prof.municipio_id}&tipo=USUARIOS&qtd={limite.excedente}"
            messages.error(
                request,
                (
                    f"Limite de usuários excedido ({limite.atual}/{limite.limite}). "
                    f"Solicite upgrade em: {upgrade_url}"
                ),
            )
            return redirect(request.POST.get("next") or reverse("accounts:usuarios_list"))

    prof.bloqueado = not prof.bloqueado
    prof.save(update_fields=["bloqueado"])
    _sync_user_active(user, prof)

    action = UserManagementAudit.Action.BLOCK if prof.bloqueado else UserManagementAudit.Action.UNBLOCK
    log_user_action(actor=request.user, target=user, action=action, details=f"bloqueado={prof.bloqueado}")

    messages.success(request, "Status de bloqueio atualizado.")
    return redirect(request.POST.get("next") or reverse("accounts:usuarios_list"))


@login_required
@require_perm("accounts.manage_users")
@require_http_methods(["POST"])
def usuario_reset_codigo(request, pk: int):
    user = get_object_or_404(scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    prof.codigo_acesso = ""
    prof.save()

    log_user_action(
        actor=request.user,
        target=user,
        action=UserManagementAudit.Action.RESET_CODE,
        details=f"novo_codigo={prof.codigo_acesso}",
    )

    messages.success(request, f"Código de acesso redefinido para: {prof.codigo_acesso}")
    return redirect(request.POST.get("next") or reverse("accounts:usuarios_list"))


@login_required
@require_perm("accounts.manage_users")
@require_http_methods(["POST"])
def usuario_reset_senha(request, pk: int):
    if not can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para redefinir senha.")
        return redirect("core:dashboard")

    user = get_object_or_404(scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    cpf_digits = prof.cpf_digits
    if not cpf_digits:
        messages.error(request, "Este usuário não tem CPF no perfil. Preencha o CPF antes de redefinir a senha.")
        return redirect("accounts:usuario_update", pk=user.pk)

    user.set_password(cpf_digits)
    user.save(update_fields=["password"])

    prof.must_change_password = True
    prof.save(update_fields=["must_change_password"])

    if user.email:
        try:
            send_mail(
                subject="GEPUB — Senha redefinida",
                message=(
                    "Sua senha foi redefinida para o CPF (apenas números).\n\n"
                    f"Código de acesso: {prof.codigo_acesso}\n"
                    "No primeiro login, você será obrigado a criar uma nova senha."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )
            messages.success(request, "Senha redefinida. E-mail enviado (se o servidor de e-mail estiver configurado).")
        except Exception:
            messages.success(request, "Senha redefinida. (Não foi possível enviar e-mail agora.)")
    else:
        messages.success(request, "Senha redefinida para o CPF. (Usuário não tem e-mail cadastrado.)")

    log_user_action(
        actor=request.user,
        target=user,
        action=UserManagementAudit.Action.RESET_PASSWORD,
        details="reset senha para CPF",
    )
    return redirect(request.POST.get("next") or reverse("accounts:usuarios_list"))
