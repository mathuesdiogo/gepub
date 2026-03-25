from __future__ import annotations

from pathlib import Path
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import OperationalError, ProgrammingError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.comunicacao.models import NotificationPreference
from apps.org.models import MunicipioThemeConfig

from .forms import AlterarSenhaPrimeiroAcessoForm, LoginCodigoForm
from .models import PasswordHistory, Profile, UserManagementAudit
from .security import is_locked, register_failure, reset


def _client_ip(request) -> str:
    x_forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "0.0.0.0").strip()


def _invalid_credentials_error() -> str:
    # Evita enumeração de usuário/código de acesso por mensagem distinta.
    return "Credenciais inválidas. Verifique código e senha."


def _parse_audit_details(details: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for chunk in (details or "").split(";"):
        item = (chunk or "").strip()
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = (key or "").strip().lower()
        value = (value or "").strip()
        if key:
            parsed[key] = value
    return parsed


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


MFA_SESSION_USER_KEY = "accounts_mfa_pending_user_id"
MFA_SESSION_CODE_KEY = "accounts_mfa_pending_codigo"
MFA_SESSION_BACKEND_KEY = "accounts_mfa_pending_backend"
MFA_CACHE_PREFIX = "accounts:mfa_code:"
MFA_TTL_SECONDS = 10 * 60
MFA_MAX_ATTEMPTS = 5
DEFAULT_PASSWORD_EXPIRE_DAYS = 90


def _default_auth_backend() -> str:
    backends = tuple(getattr(settings, "AUTHENTICATION_BACKENDS", ()) or ())
    if backends:
        return backends[0]
    return "django.contrib.auth.backends.ModelBackend"


def _password_expired(profile: Profile) -> bool:
    days = int(getattr(profile, "password_expires_days", DEFAULT_PASSWORD_EXPIRE_DAYS) or 0)
    if days <= 0:
        return False
    changed_at = getattr(profile, "password_changed_at", None)
    if not changed_at:
        return True
    return timezone.now() >= changed_at + timezone.timedelta(days=days)


def _ensure_password_not_expired(profile: Profile) -> None:
    if _password_expired(profile) and not profile.must_change_password:
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password"])


def _mfa_cache_key(user_id: int) -> str:
    return f"{MFA_CACHE_PREFIX}{int(user_id)}"


def _dispatch_mfa_code(request, *, user, profile: Profile, pref: NotificationPreference | None) -> None:
    code = f"{secrets.randbelow(900000) + 100000}"
    cache.set(
        _mfa_cache_key(user.pk),
        {"code": code, "attempts": 0, "generated_at": timezone.now().isoformat()},
        timeout=MFA_TTL_SECONDS,
    )

    destination = ""
    if pref and pref.allow_email and not pref.opt_out and pref.email:
        destination = pref.email
    elif user.email:
        destination = user.email

    if destination:
        try:
            send_mail(
                subject="GEPUB - Código de verificação",
                message=(
                    f"Seu código de verificação é: {code}\n\n"
                    "Este código expira em 10 minutos."
                ),
                from_email=None,
                recipient_list=[destination],
                fail_silently=True,
            )
        except Exception:
            pass

    messages.info(
        request,
        "Código de verificação enviado. Confira seu e-mail cadastrado para concluir o login.",
    )


def _consume_mfa_code(user_id: int, typed_code: str) -> tuple[bool, str]:
    payload = cache.get(_mfa_cache_key(user_id)) or {}
    code = str(payload.get("code") or "").strip()
    attempts = int(payload.get("attempts") or 0)
    if not code:
        return False, "Código expirado. Solicite um novo envio."

    if str(typed_code or "").strip() != code:
        attempts += 1
        if attempts >= MFA_MAX_ATTEMPTS:
            cache.delete(_mfa_cache_key(user_id))
            return False, "Código inválido. Limite de tentativas atingido."
        payload["attempts"] = attempts
        cache.set(_mfa_cache_key(user_id), payload, timeout=MFA_TTL_SECONDS)
        return False, "Código inválido. Verifique e tente novamente."

    cache.delete(_mfa_cache_key(user_id))
    return True, ""


def _password_reused(user, new_password: str, depth: int = 5) -> bool:
    if not new_password:
        return False
    if check_password(new_password, user.password):
        return True

    histories = PasswordHistory.objects.filter(user=user).order_by("-created_at")[: max(1, int(depth))]
    for item in histories:
        if check_password(new_password, item.password_hash):
            return True
    return False


def _record_password_history(user) -> None:
    if not user.password:
        return
    PasswordHistory.objects.create(user=user, password_hash=user.password)


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    if request.session.get(MFA_SESSION_USER_KEY):
        return redirect("accounts:login_mfa")

    error = None
    form = LoginCodigoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        codigo = (form.cleaned_data["codigo_acesso"] or "").strip()
        senha = form.cleaned_data["password"]

        ip = _client_ip(request)
        if is_locked(ip, codigo):
            error = "Muitas tentativas. Aguarde alguns minutos e tente novamente."
            return render(request, "accounts/login.html", {"form": form, "error": error})

        try:
            profile = (
                Profile.objects.select_related("user")
                .filter(codigo_acesso__iexact=codigo, ativo=True, bloqueado=False)
                .first()
            )
        except (OperationalError, ProgrammingError):
            error = "Banco desatualizado. Execute `python manage.py migrate` e tente novamente."
            return render(request, "accounts/login.html", {"form": form, "error": error})
        if not profile:
            register_failure(ip, codigo)
            error = _invalid_credentials_error()
            return render(request, "accounts/login.html", {"form": form, "error": error})

        user = authenticate(request, username=profile.user.username, password=senha)
        if user is None:
            register_failure(ip, codigo)
            error = _invalid_credentials_error()
            return render(request, "accounts/login.html", {"form": form, "error": error})

        _ensure_password_not_expired(profile)

        if profile.mfa_enabled:
            pref = None
            if profile.municipio_id:
                pref = (
                    NotificationPreference.objects.filter(
                        municipio_id=profile.municipio_id,
                        user=user,
                        aluno__isnull=True,
                    )
                    .order_by("-atualizado_em", "-id")
                    .first()
                )
            request.session[MFA_SESSION_USER_KEY] = user.pk
            request.session[MFA_SESSION_CODE_KEY] = profile.codigo_acesso
            request.session[MFA_SESSION_BACKEND_KEY] = getattr(user, "backend", _default_auth_backend())
            _dispatch_mfa_code(request, user=user, profile=profile, pref=pref)
            return redirect("accounts:login_mfa")

        reset(ip, codigo)
        login(request, user)

        Profile.objects.get_or_create(user=user, defaults={"ativo": True})

        return redirect("core:dashboard")

    return render(request, "accounts/login.html", {"form": form, "error": error})


@require_http_methods(["GET", "POST"])
def login_mfa_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    pending_user_id = request.session.get(MFA_SESSION_USER_KEY)
    codigo_hint = request.session.get(MFA_SESSION_CODE_KEY) or ""
    if not pending_user_id:
        return redirect("accounts:login")

    try:
        profile = (
            Profile.objects.select_related("user")
            .filter(user_id=pending_user_id, ativo=True, bloqueado=False)
            .first()
        )
    except (OperationalError, ProgrammingError):
        messages.error(request, "Banco desatualizado. Execute `python manage.py migrate`.")
        return redirect("accounts:login")
    if not profile:
        request.session.pop(MFA_SESSION_USER_KEY, None)
        request.session.pop(MFA_SESSION_CODE_KEY, None)
        request.session.pop(MFA_SESSION_BACKEND_KEY, None)
        return redirect("accounts:login")

    error = ""
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "resend":
            pref = None
            if profile.municipio_id:
                pref = (
                    NotificationPreference.objects.filter(
                        municipio_id=profile.municipio_id,
                        user=profile.user,
                        aluno__isnull=True,
                    )
                    .order_by("-atualizado_em", "-id")
                    .first()
                )
            _dispatch_mfa_code(request, user=profile.user, profile=profile, pref=pref)
            return redirect("accounts:login_mfa")

        typed_code = (request.POST.get("otp_code") or "").strip()
        ok, error = _consume_mfa_code(profile.user_id, typed_code)
        if ok:
            request.session.pop(MFA_SESSION_USER_KEY, None)
            request.session.pop(MFA_SESSION_CODE_KEY, None)
            backend = request.session.pop(MFA_SESSION_BACKEND_KEY, None) or _default_auth_backend()
            login(request, profile.user, backend=backend)
            reset(_client_ip(request), profile.codigo_acesso or profile.user.username)
            _ensure_password_not_expired(profile)
            return redirect("core:dashboard")

        if "Limite de tentativas" in error:
            request.session.pop(MFA_SESSION_USER_KEY, None)
            request.session.pop(MFA_SESSION_CODE_KEY, None)
            request.session.pop(MFA_SESSION_BACKEND_KEY, None)
            return render(request, "accounts/login.html", {"form": LoginCodigoForm(), "error": error})

    return render(
        request,
        "accounts/login_mfa.html",
        {
            "codigo_hint": codigo_hint,
            "error": error,
        },
    )


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

        if _password_reused(request.user, senha1, depth=5):
            error = "Esta senha já foi utilizada recentemente. Escolha uma senha diferente."
            return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})

        request.user.set_password(senha1)
        request.user.save()
        _record_password_history(request.user)

        p.must_change_password = False
        p.password_changed_at = timezone.now()
        if not p.password_expires_days:
            p.password_expires_days = DEFAULT_PASSWORD_EXPIRE_DAYS
        p.save(update_fields=["must_change_password", "password_changed_at", "password_expires_days"])

        update_session_auth_hash(request, request.user)
        messages.success(request, "Senha alterada com sucesso.")

        if (p.role or "").upper() == "MUNICIPAL":
            return redirect("org:onboarding_wizard")

        return redirect("core:dashboard")

    return render(request, "accounts/alterar_senha.html", {"form": form, "error": error})


@login_required
def logout_view(request):
    if request.user.is_authenticated:
        UserManagementAudit.objects.create(
            actor=request.user,
            target=request.user,
            action=UserManagementAudit.Action.UPDATE,
            details="LOGOUT",
        )
    logout(request)
    return redirect("accounts:login")


@login_required
@require_http_methods(["GET", "POST"])
def meu_perfil(request):
    p, _ = Profile.objects.get_or_create(user=request.user, defaults={"ativo": True})
    pref = None
    theme_config = None
    can_choose_theme = False
    if p.municipio_id:
        pref, _ = NotificationPreference.objects.get_or_create(
            municipio=p.municipio,
            user=request.user,
            aluno=None,
            defaults={
                "nome_contato": request.user.get_full_name() or request.user.username,
                "email": request.user.email or "",
                "allow_email": True,
                "allow_sms": True,
                "allow_whatsapp": True,
                "opt_out": False,
            },
        )
        theme_config = MunicipioThemeConfig.objects.filter(municipio=p.municipio).first()
        # Regra de produto: usuário pode escolher livremente entre os temas internos.
        can_choose_theme = True

    if request.method == "POST":
        request.user.email = (request.POST.get("email") or "").strip()
        request.user.save(update_fields=["email"])

        if hasattr(p, "telefone"):
            p.telefone = (request.POST.get("telefone") or "").strip()

        if hasattr(p, "endereco"):
            p.endereco = (request.POST.get("endereco") or "").strip()

        foto_upload = request.FILES.get("foto")
        remove_foto = bool(request.POST.get("remove_foto"))
        if remove_foto and p.foto:
            p.foto.delete(save=False)
            p.foto = None
        elif foto_upload:
            try:
                _validate_profile_photo(foto_upload)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect("accounts:meu_perfil")
            p.foto = foto_upload

        if pref:
            pref.email = request.user.email or ""
            pref.telefone = (request.POST.get("pref_telefone") or "").strip()
            pref.whatsapp = (request.POST.get("pref_whatsapp") or "").strip()
            pref.allow_email = bool(request.POST.get("allow_email"))
            pref.allow_sms = bool(request.POST.get("allow_sms"))
            pref.allow_whatsapp = bool(request.POST.get("allow_whatsapp"))
            pref.opt_out = bool(request.POST.get("opt_out"))
            pref.horario_inicio = (request.POST.get("horario_inicio") or "").strip() or None
            pref.horario_fim = (request.POST.get("horario_fim") or "").strip() or None
            pref.nome_contato = request.user.get_full_name() or request.user.username
            pref.atualizado_por = request.user

        p.mfa_enabled = bool(request.POST.get("mfa_enabled"))
        if can_choose_theme:
            candidate_theme = (request.POST.get("ui_theme") or "").strip().lower()
            if candidate_theme in {Profile.UITheme.KASSYA, Profile.UITheme.INCLUSAO, Profile.UITheme.INSTITUCIONAL}:
                p.ui_theme = candidate_theme
            elif not candidate_theme:
                p.ui_theme = ""
        expires_raw = (request.POST.get("password_expires_days") or "").strip()
        if expires_raw.isdigit():
            p.password_expires_days = max(0, min(365, int(expires_raw)))

        p.save()
        if pref:
            pref.save()

        messages.success(request, "Perfil atualizado.")
        return redirect("accounts:meu_perfil")

    expires_at = None
    if p.password_changed_at and p.password_expires_days and p.password_expires_days > 0:
        expires_at = p.password_changed_at + timezone.timedelta(days=int(p.password_expires_days))

    quick_actions_url = reverse("core:dashboard")
    quick_documents_url = reverse("core:dashboard")
    meus_dados_url = ""
    documentos_total = 0
    if p.aluno_id:
        try:
            from apps.educacao.models import AlunoCertificado, AlunoDocumento
            from apps.educacao.models_beneficios import BeneficioEditalInscricaoDocumento

            documentos_total = (
                AlunoDocumento.objects.filter(aluno_id=p.aluno_id, ativo=True).count()
                + AlunoCertificado.objects.filter(aluno_id=p.aluno_id, ativo=True).count()
                + BeneficioEditalInscricaoDocumento.objects.filter(inscricao__aluno_id=p.aluno_id).count()
            )
            quick_documents_url = reverse("educacao:historico_aluno", args=[p.aluno_id])
            codigo_aluno = (p.codigo_acesso or request.user.username or str(p.aluno_id)).strip()
            meus_dados_url = reverse("educacao:aluno_meus_dados", args=[codigo_aluno])
            quick_actions_url = meus_dados_url
        except Exception:
            documentos_total = 0

    audit_qs = UserManagementAudit.objects.filter(target=request.user).select_related("actor").order_by("-created_at")
    actions_total = audit_qs.count()
    recent_actions = list(audit_qs[:6])

    groups_history: list[dict[str, object]] = []
    transfer_history: list[dict[str, object]] = []
    role_labels = dict(Profile.Role.choices)
    for row in audit_qs[:30]:
        parsed = _parse_audit_details(row.details or "")
        role_code = (parsed.get("role") or "").upper()
        if role_code and len(groups_history) < 8:
            groups_history.append(
                {
                    "title": f"Perfil aplicado: {role_labels.get(role_code, role_code)}",
                    "meta": f"Atualizado por {getattr(row.actor, 'username', 'sistema')}",
                    "created_at": row.created_at,
                }
            )

        if len(transfer_history) >= 8:
            continue
        scope_parts = []
        for key, label in (
            ("municipio", "Município"),
            ("secretaria", "Secretaria"),
            ("unidade", "Unidade"),
            ("setor", "Setor"),
            ("local_estrutural", "Local estrutural"),
        ):
            value = (parsed.get(key) or "").strip()
            if value and value.lower() not in {"none", "null", "n/a"}:
                scope_parts.append(f"{label} #{value}")
        if scope_parts:
            transfer_history.append(
                {
                    "title": "Escopo atualizado",
                    "meta": " • ".join(scope_parts),
                    "created_at": row.created_at,
                }
            )

    if not groups_history:
        groups_history = [
            {
                "title": f"Perfil atual: {p.get_role_display()}",
                "meta": "Sem alterações de grupo registradas.",
                "created_at": None,
            }
        ]

    if not transfer_history:
        transfer_history = [
            {
                "title": "Sem transferências e manejos",
                "meta": "Nenhuma alteração de escopo registrada até o momento.",
                "created_at": None,
            }
        ]

    selected_theme = (p.ui_theme or getattr(theme_config, "default_theme", "") or Profile.UITheme.KASSYA).lower()
    selected_theme_label = dict(Profile.UITheme.choices).get(selected_theme, selected_theme.title())

    return render(
        request,
        "accounts/meu_perfil.html",
        {
            "p": p,
            "pref": pref,
            "password_expires_at": expires_at,
            "theme_config": theme_config,
            "can_choose_theme": can_choose_theme,
            "ui_theme_choices": Profile.UITheme.choices,
            "quick_actions_url": quick_actions_url,
            "quick_documents_url": quick_documents_url,
            "meus_dados_url": meus_dados_url,
            "documentos_total": documentos_total,
            "actions_total": actions_total,
            "recent_actions": recent_actions,
            "groups_history": groups_history,
            "transfer_history": transfer_history,
            "selected_theme": selected_theme,
            "selected_theme_label": selected_theme_label,
            "current_session_ip": _client_ip(request),
            "current_user_agent": (request.META.get("HTTP_USER_AGENT") or "").strip(),
        },
    )
