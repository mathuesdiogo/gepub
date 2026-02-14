from __future__ import annotations

import secrets
from django.urls import reverse  # garanta esse import
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.urls import reverse 
from django.contrib.auth.models import User
from apps.core.rbac import get_profile, is_admin



from django.shortcuts import render
from django.contrib.auth import get_user_model

from apps.core.decorators import require_perm
from apps.core.rbac import can, get_profile, is_admin


User = get_user_model()
from .forms import (
    AlterarSenhaPrimeiroAcessoForm,
    LoginCodigoForm,
    UsuarioCreateForm,
    UsuarioUpdateForm,
)
from .models import Profile
from .security import is_locked, register_failure, reset

User = get_user_model()


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _can_manage_users(user) -> bool:
    if is_admin(user):
        return True
    p = get_profile(user)
    return bool(p and p.ativo and p.role in {"MUNICIPAL", "SECRETARIA", "UNIDADE"})


def _scope_users_queryset(request):
    qs = User.objects.select_related("profile").all().order_by("id")
    if is_admin(request.user):
        return qs

    p = get_profile(request.user)
    if not p or not p.ativo:
        return qs.none()

    if getattr(p, "unidade_id", None):
        return qs.filter(profile__unidade_id=p.unidade_id)

    if getattr(p, "secretaria_id", None):
        return qs.filter(profile__secretaria_id=p.secretaria_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(profile__municipio_id=p.municipio_id)

    return qs.none()


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    error = None
    form = LoginCodigoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        codigo = (form.cleaned_data["codigo_acesso"] or "").strip()
        senha = form.cleaned_data["password"]

        ip = _client_ip(request)
        if is_locked(ip, codigo):
            error = "Muitas tentativas. Aguarde alguns minutos e tente novamente."
            return render(request, "accounts/login.html", {"form": form, "error": error})

        profile = (
            Profile.objects.select_related("user")
            .filter(codigo_acesso__iexact=codigo, ativo=True)
            .first()
        )
        if not profile:
            register_failure(ip, codigo)
            error = "Código de acesso inválido."
            return render(request, "accounts/login.html", {"form": form, "error": error})

        user = authenticate(request, username=profile.user.username, password=senha)
        if user is None:
            register_failure(ip, codigo)
            error = "Senha inválida."
            return render(request, "accounts/login.html", {"form": form, "error": error})

        reset(ip, codigo)
        login(request, user)

        Profile.objects.get_or_create(user=user, defaults={"ativo": True})

        return redirect("core:dashboard")

    return render(request, "accounts/login.html", {"form": form, "error": error})


@login_required
@require_http_methods(["GET", "POST"])
def alterar_senha_view(request):
    p, _ = Profile.objects.get_or_create(user=request.user, defaults={"ativo": True})

    form = AlterarSenhaPrimeiroAcessoForm(request.POST or None)
    error = None

    if request.method == "POST" and form.is_valid():
        senha1 = (form.cleaned_data["password1"] or "").strip()
        senha2 = (form.cleaned_data["password2"] or "").strip()

        if senha1 != senha2:
            error = "As senhas não conferem."
            return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})

        cpf_digits = _only_digits(p.cpf)
        if cpf_digits and _only_digits(senha1) == cpf_digits:
            error = "A nova senha não pode ser igual ao CPF."
            return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})

        try:
            validate_password(senha1, user=request.user)
        except ValidationError as e:
            error = " ".join(e.messages)
            return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})

        request.user.set_password(senha1)
        request.user.save()

        p.must_change_password = False
        p.save(update_fields=["must_change_password"])

        update_session_auth_hash(request, request.user)
        messages.success(request, "Senha alterada com sucesso.")
        return redirect("core:dashboard")

    return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})


@login_required
def logout_view(request):
    logout(request)
    return redirect("accounts:login")



@require_http_methods(["GET", "POST"])
def meu_perfil(request):
    p, _ = Profile.objects.get_or_create(user=request.user, defaults={"ativo": True})

    if request.method == "POST":

        request.user.email = (request.POST.get("email") or "").strip()
        request.user.save(update_fields=["email"])

        if hasattr(p, "telefone"):
            p.telefone = (request.POST.get("telefone") or "").strip()

        if hasattr(p, "endereco"):
            p.endereco = (request.POST.get("endereco") or "").strip()

        # FOTO
        if request.FILES.get("foto"):
            p.foto = request.FILES["foto"]

        p.save()

        messages.success(request, "Perfil atualizado.")
        return redirect("accounts:meu_perfil")

    return render(request, "accounts/meu_perfil.html", {"p": p})


@login_required
@require_perm("accounts.manage_users")
def usuarios_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = User.objects.select_related("profile").all()

    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(profile__codigo_acesso__icontains=q)
        )

    qs = qs.order_by("first_name", "last_name", "username")

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ✅ perm correta do RBAC
    can_manage = can(request.user, "accounts.manage_users") or request.user.is_staff or request.user.is_superuser

    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Novo usuário",
                "url": reverse("accounts:usuario_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "ID", "width": "80px"},
        {"label": "Nome"},
        {"label": "Código", "width": "140px"},
        {"label": "Função", "width": "160px"},
        {"label": "Município"},
        {"label": "Unidade"},
        {"label": "Ativo", "width": "90px"},
    ]

    rows = []
    for u in page_obj:
        nome = (u.get_full_name() or u.username).strip()
        profile = getattr(u, "profile", None)

        codigo = getattr(profile, "codigo_acesso", "") if profile else ""
        role = (profile.get_role_display() if profile and hasattr(profile, "get_role_display") else "")
        municipio = str(getattr(profile, "municipio", "") or "—") if profile else "—"
        unidade = str(getattr(profile, "unidade", "") or "—") if profile else "—"
        ativo = "Sim" if (getattr(profile, "ativo", False) if profile else getattr(u, "is_active", False)) else "Não"

        rows.append(
            {
                "cells": [
                    {"text": str(u.id), "url": ""},
                    {"text": nome, "url": ""},
                    {"text": codigo or "—", "url": ""},
                    {"text": role or "—", "url": ""},
                    {"text": municipio, "url": ""},
                    {"text": unidade, "url": ""},
                    {"text": ativo, "url": ""},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("accounts:usuario_update", args=[u.id]) if can_manage else "",
            }
        )

    # ✅ autocomplete (tem que existir no accounts/urls.py com name="users_autocomplete")
    autocomplete_url = reverse("accounts:users_autocomplete")
    autocomplete_href = reverse("accounts:usuarios_list") + "?q={q}"
    input_attrs = f'data-autocomplete-url="{autocomplete_url}" data-autocomplete-href="{autocomplete_href}"'

    return render(
        request,
        "accounts/users_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("accounts:usuarios_list"),
            "clear_url": reverse("accounts:usuarios_list"),
            "has_filters": False,
            "extra_filters": "",
            "autocomplete_url": autocomplete_url,
            "autocomplete_href": autocomplete_href,
            "input_attrs": input_attrs,
        },
    )



@login_required
@require_http_methods(["GET", "POST"])
def usuario_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para criar usuários.")
        return redirect("core:dashboard")

    p_me = get_profile(request.user)

    form = UsuarioCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        username = f"u{secrets.token_hex(10)}"
        user = User(
            username=username,
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            email=form.cleaned_data["email"] or "",
            is_active=True,
        )

        cpf_digits = _only_digits(form.cleaned_data["cpf"])
        user.set_password(cpf_digits)
        user.save()

        prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

        prof.cpf = form.cleaned_data["cpf"]
        prof.role = form.cleaned_data["role"]
        prof.ativo = bool(form.cleaned_data.get("ativo", True))

        allowed = {
            "MUNICIPAL": {"SECRETARIA", "UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
            "SECRETARIA": {"UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
            "UNIDADE": {"PROFESSOR", "ALUNO", "NEE", "LEITURA"},
        }

        role_me = getattr(p_me, "role", None)

        if not is_admin(request.user):
            if prof.role not in allowed.get(role_me, set()):
                messages.error(request, "Você não pode criar esse tipo de usuário.")
                user.delete()
                return redirect("accounts:usuarios_list")

        if not is_admin(request.user) and p_me:
            prof.municipio_id = getattr(p_me, "municipio_id", None)
            if hasattr(prof, "secretaria_id"):
                prof.secretaria_id = getattr(p_me, "secretaria_id", None)
            prof.unidade_id = getattr(p_me, "unidade_id", None)
        else:
            if "municipio" in form.cleaned_data:
                prof.municipio = form.cleaned_data.get("municipio")
            if "unidade" in form.cleaned_data:
                prof.unidade = form.cleaned_data.get("unidade")

        prof.must_change_password = True
        prof.save()

        # ✅ NOVO: vincula turmas escolhidas (somente professor)
        if prof.role == "PROFESSOR" and "turmas" in form.cleaned_data:
            user.turmas_ministradas.set(form.cleaned_data.get("turmas") or [])
        else:
            # evita resíduos se alguém escolher turmas sem ser professor
            user.turmas_ministradas.clear()

        messages.success(
            request,
            f"Usuário criado. Código de acesso: {prof.codigo_acesso}. Senha inicial: CPF. (Troca obrigatória no 1º acesso)",
        )
        return redirect("accounts:usuarios_list")

    return render(request, "accounts/user_form.html", {"form": form, "mode": "create"})


@login_required
@require_http_methods(["GET", "POST"])
def usuario_update(request, pk: int):
    if not _can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para editar usuários.")
        return redirect("core:dashboard")

    user = get_object_or_404(_scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    initial = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "cpf": prof.cpf,
        "role": prof.role,
        "municipio": getattr(prof, "municipio_id", None),
        "unidade": getattr(prof, "unidade_id", None),
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
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"] or ""
        user.save()

        prof.cpf = form.cleaned_data.get("cpf") or prof.cpf
        prof.role = form.cleaned_data["role"]
        prof.ativo = bool(form.cleaned_data.get("ativo", True))

        p_me = get_profile(request.user)
        if not is_admin(request.user) and p_me:
            prof.municipio_id = getattr(p_me, "municipio_id", None)
            if hasattr(prof, "secretaria_id"):
                prof.secretaria_id = getattr(p_me, "secretaria_id", None)
            prof.unidade_id = getattr(p_me, "unidade_id", None)
        else:
            if "municipio" in form.cleaned_data:
                prof.municipio = form.cleaned_data.get("municipio")
            if "unidade" in form.cleaned_data:
                prof.unidade = form.cleaned_data.get("unidade")

        prof.save()

        # ✅ NOVO: atualiza vínculo de turmas (somente professor)
        if prof.role == "PROFESSOR" and "turmas" in form.cleaned_data:
            user.turmas_ministradas.set(form.cleaned_data.get("turmas") or [])
        else:
            user.turmas_ministradas.clear()

        messages.success(request, "Usuário atualizado.")
        return redirect("accounts:usuarios_list")

    return render(request, "accounts/user_form.html", {"form": form, "mode": "update", "u": user})


@login_required
@require_http_methods(["POST"])
def usuario_reset_senha(request, pk: int):
    if not _can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para redefinir senha.")
        return redirect("core:dashboard")

    user = get_object_or_404(_scope_users_queryset(request), pk=pk)
    prof, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})

    cpf_digits = _only_digits(prof.cpf)
    if not cpf_digits:
        messages.error(request, "Este usuário não tem CPF no perfil. Preencha o CPF antes de redefinir a senha.")
        return redirect("accounts:usuario_update", pk=user.pk)

    user.set_password(cpf_digits)
    user.save()

    prof.must_change_password = True
    prof.save(update_fields=["must_change_password"])

    if user.email:
        try:
            from django.core.mail import send_mail

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

    return redirect("accounts:usuarios_list")

@login_required
def users_autocomplete(request):
    q = request.GET.get("q", "").strip()

    qs = User.objects.select_related("profile")

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(username__icontains=q)
            | Q(profile__codigo_acesso__icontains=q)
        )

    data = {
        "results": [
            {
                "id": u.id,
                "text": f"{u.get_full_name() or u.username}"
            }
            for u in qs.order_by("first_name")[:10]
        ]
    }

    return JsonResponse(data)

@login_required
@require_perm("accounts.manage_users")
def users_autocomplete(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = User.objects.select_related("profile").all()

    qs = qs.filter(
        Q(username__icontains=q)
        | Q(email__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(profile__codigo_acesso__icontains=q)
    ).order_by("first_name", "last_name", "username")[:10]

    results = []
    for u in qs:
        nome = (u.get_full_name() or u.username).strip()
        meta = u.email or ""
        results.append({"id": u.id, "text": nome, "meta": meta})

    return JsonResponse({"results": results})