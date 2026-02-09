from __future__ import annotations

import secrets

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import (
    AlterarSenhaPrimeiroAcessoForm,
    LoginCodigoForm,
    UsuarioCreateForm,
    UsuarioUpdateForm,
)
from .models import Profile
from .security import is_locked, register_failure, reset
from core.rbac import get_profile, is_admin


User = get_user_model()


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _can_manage_users(user) -> bool:
    # Admin global sempre.
    if is_admin(user):
        return True
    p = get_profile(user)
    # MUNICIPAL / SECRETARIA / UNIDADE podem gerenciar dentro do escopo
    return bool(p and p.ativo and p.role in {"MUNICIPAL", "SECRETARIA", "UNIDADE", "ADMIN"})



def _scope_users_queryset(request):
    """
    Escopo:
    - ADMIN: todos
    - UNIDADE: apenas usuários da unidade dele
    - SECRETARIA: apenas usuários da secretaria dele (se existir no Profile)
    - MUNICIPAL: apenas usuários do município dele
    """
    qs = User.objects.select_related("profile").all().order_by("id")
    if is_admin(request.user):
        return qs

    p = get_profile(request.user)
    if not p or not p.ativo:
        return qs.none()

    # prioridade: UNIDADE > SECRETARIA > MUNICÍPIO
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
        return redirect("core:dashboard")

    return render(request, "accounts/login.html", {"form": form, "error": error})


@login_required
@require_http_methods(["GET", "POST"])
def alterar_senha_view(request):
    p: Profile | None = getattr(request.user, "profile", None)
    if not p:
        return redirect("core:dashboard")

    form = AlterarSenhaPrimeiroAcessoForm(request.POST or None)
    error = None

    if request.method == "POST" and form.is_valid():
        senha1 = (form.cleaned_data["password1"] or "").strip()
        senha2 = (form.cleaned_data["password2"] or "").strip()

        if senha1 != senha2:
            error = "As senhas não conferem."
            return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})

        # bloqueia manter CPF como senha
        cpf_digits = _only_digits(p.cpf)
        if cpf_digits and _only_digits(senha1) == cpf_digits:
            error = "A nova senha não pode ser igual ao CPF."
            return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})

        # valida força (usa validators do Django)
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


# =========================
# MEU PERFIL
# =========================
@login_required
@require_http_methods(["GET", "POST"])
def meu_perfil(request):
    p: Profile | None = getattr(request.user, "profile", None)
    if not p:
        messages.error(request, "Perfil não encontrado.")
        return redirect("core:dashboard")

    if request.method == "POST":
        request.user.first_name = (request.POST.get("first_name") or "").strip()
        request.user.last_name = (request.POST.get("last_name") or "").strip()
        request.user.email = (request.POST.get("email") or "").strip()
        request.user.save()
        messages.success(request, "Perfil atualizado.")
        return redirect("accounts:meu_perfil")

    return render(request, "accounts/meu_perfil.html", {"p": p})


# =========================
# GESTÃO DE USUÁRIOS (RBAC)
# =========================
@login_required
def usuarios_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para gerenciar usuários.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = _scope_users_queryset(request)

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(profile__codigo_acesso__icontains=q)
        )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "accounts/users_list.html", {"q": q, "page_obj": page_obj})


@login_required
@require_http_methods(["GET", "POST"])
def usuario_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, "Você não tem permissão para criar usuários.")
        return redirect("core:dashboard")

    p_me = get_profile(request.user)

    form = UsuarioCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        # cria User com username interno aleatório (login é via codigo_acesso)
        username = f"u{secrets.token_hex(10)}"
        user = User(
            username=username,
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            email=form.cleaned_data["email"] or "",
            is_active=True,
        )

        cpf_digits = _only_digits(form.cleaned_data["cpf"])
        user.set_password(cpf_digits)  # senha inicial = CPF
        user.save()  # signals cria o Profile

        prof = user.profile
        prof.cpf = form.cleaned_data["cpf"]
        prof.role = form.cleaned_data["role"]
        prof.ativo = bool(form.cleaned_data.get("ativo"))
        prof.cpf = form.cleaned_data["cpf"]
        prof.role = form.cleaned_data["role"]
        prof.ativo = bool(form.cleaned_data.get("ativo"))

            # Limita quais roles cada gestor pode criar
        role_me = getattr(p_me, "role", None)

        allowed = {
        "MUNICIPAL": {"SECRETARIA", "UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
        "SECRETARIA": {"UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
        "UNIDADE": {"PROFESSOR", "ALUNO", "NEE", "LEITURA"},
    }


        if not is_admin(request.user):
            if prof.role not in allowed.get(role_me, set()):
                messages.error(request, "Você não pode criar esse tipo de usuário.")
                user.delete()
                return redirect("accounts:usuarios_list")

                # RBAC: herda escopo do criador (trava no backend)
        if not is_admin(request.user) and p_me:
            prof.municipio_id = getattr(p_me, "municipio_id", None)
            if hasattr(prof, "secretaria_id"):
                prof.secretaria_id = getattr(p_me, "secretaria_id", None)
            prof.unidade_id = getattr(p_me, "unidade_id", None)
        else:
            prof.municipio = form.cleaned_data.get("municipio")
            prof.unidade = form.cleaned_data.get("unidade")
            if hasattr(prof, "secretaria") and "secretaria" in form.cleaned_data:
                prof.secretaria = form.cleaned_data.get("secretaria")


        prof.must_change_password = True
        prof.save()

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
    prof = user.profile

    initial = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "cpf": prof.cpf,
        "role": prof.role,
        "municipio": prof.municipio_id,
        "unidade": prof.unidade_id,
        "ativo": prof.ativo,
    }

    form = UsuarioUpdateForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"] or ""
        user.save()

        prof.cpf = form.cleaned_data["cpf"] or prof.cpf
        prof.role = form.cleaned_data["role"]
        prof.ativo = bool(form.cleaned_data.get("ativo"))

       # RBAC: trava escopo no backend (não deixa mover usuário)
        p_me = get_profile(request.user)
        if not is_admin(request.user) and p_me:
            prof.municipio_id = getattr(p_me, "municipio_id", None)
            if hasattr(prof, "secretaria_id"):
                prof.secretaria_id = getattr(p_me, "secretaria_id", None)
            prof.unidade_id = getattr(p_me, "unidade_id", None)
        else:
            prof.municipio = form.cleaned_data.get("municipio")
            prof.unidade = form.cleaned_data.get("unidade")
            if hasattr(prof, "secretaria") and "secretaria" in form.cleaned_data:
                prof.secretaria = form.cleaned_data.get("secretaria")

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
    prof = user.profile

    cpf_digits = _only_digits(prof.cpf)
    if not cpf_digits:
        messages.error(request, "Este usuário não tem CPF no perfil. Preencha o CPF antes de redefinir a senha.")
        return redirect("accounts:usuario_update", pk=user.pk)

    # redefine senha para CPF e força troca
    user.set_password(cpf_digits)
    user.save()

    prof.must_change_password = True
    prof.save(update_fields=["must_change_password"])

    # (opcional) e-mail — por enquanto só se seu projeto tiver EMAIL_BACKEND configurado
    if user.email:
        try:
            from django.core.mail import send_mail
            send_mail(
                subject="GEPUB — Senha redefinida",
                message=(
                    f"Sua senha foi redefinida para o CPF (apenas números).\n\n"
                    f"Código de acesso: {prof.codigo_acesso}\n"
                    f"No primeiro login, você será obrigado a criar uma nova senha."
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
