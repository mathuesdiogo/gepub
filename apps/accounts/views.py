from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AlterarSenhaPrimeiroAcessoForm, LoginCodigoForm
from .models import Profile
from .security import is_locked, register_failure, reset


def _client_ip(request) -> str:
    x_forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "0.0.0.0").strip()


def _invalid_credentials_error() -> str:
    # Evita enumeração de usuário/código de acesso por mensagem distinta.
    return "Credenciais inválidas. Verifique código e senha."


def _validate_profile_photo(uploaded) -> None:
    if not uploaded:
        return
    max_bytes = int(getattr(settings, "GEPUB_PROFILE_MAX_UPLOAD_BYTES", 2 * 1024 * 1024))
    if uploaded.size > max_bytes:
        raise ValidationError(f"A imagem deve ter no máximo {max_bytes // (1024 * 1024)}MB.")

    ext = Path(uploaded.name or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError("Formato de imagem inválido. Use JPG, PNG ou WEBP.")

    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise ValidationError("Arquivo inválido para foto de perfil.")


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
            .filter(codigo_acesso__iexact=codigo, ativo=True, bloqueado=False)
            .first()
        )
        if not profile:
            register_failure(ip, codigo)
            error = _invalid_credentials_error()
            return render(request, "accounts/login.html", {"form": form, "error": error})

        user = authenticate(request, username=profile.user.username, password=senha)
        if user is None:
            register_failure(ip, codigo)
            error = _invalid_credentials_error()
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

        cpf_digits = p.cpf_digits
        if cpf_digits and "".join(ch for ch in (senha1 or "") if ch.isdigit()) == cpf_digits:
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

        if (p.role or "").upper() == "MUNICIPAL":
            return redirect("org:onboarding_primeiro_acesso")

        return redirect("core:dashboard")

    return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})


@login_required
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@login_required
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

        foto_upload = request.FILES.get("foto")
        if foto_upload:
            try:
                _validate_profile_photo(foto_upload)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect("accounts:meu_perfil")
            p.foto = foto_upload

        p.save()

        messages.success(request, "Perfil atualizado.")
        return redirect("accounts:meu_perfil")

    return render(request, "accounts/meu_perfil.html", {"p": p})
