from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AlterarSenhaPrimeiroAcessoForm, LoginCodigoForm
from .models import Profile
from .security import is_locked, register_failure, reset


def _client_ip(request) -> str:
    # simples (p/ dev). Em produção, use X-Forwarded-For com cuidado.
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


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

        # middleware vai cuidar do redirect se precisar trocar senha
        return redirect("core:dashboard")

    return render(request, "accounts/login.html", {"form": form, "error": error})


@login_required
@require_http_methods(["GET", "POST"])
def alterar_senha_view(request):
    p = getattr(request.user, "profile", None)
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
        cpf_digits = "".join(ch for ch in (p.cpf or "") if ch.isdigit())
        if cpf_digits and "".join(ch for ch in senha1 if ch.isdigit()) == cpf_digits:
            error = "A nova senha não pode ser igual ao CPF."
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
