from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class ForcePasswordChangeMiddleware:
    """
    Se o usuário estiver logado e must_change_password=True,
    redireciona sempre para a tela de alteração de senha.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if path.startswith(static_url) or path.startswith(media_url):
            return self.get_response(request)

        if request.user.is_authenticated:
            p = getattr(request.user, "profile", None)
            role = ((getattr(p, "role", None) or "") + "").strip().upper()
            is_municipal = bool(p and getattr(p, "ativo", True) and role == "MUNICIPAL")
            onboarding_prefix = "/org/onboarding/"

            if p and getattr(p, "password_expires_days", 0) and getattr(p, "password_changed_at", None):
                expires_at = p.password_changed_at + timezone.timedelta(days=int(p.password_expires_days))
                if timezone.now() >= expires_at and not p.must_change_password:
                    p.must_change_password = True
                    p.save(update_fields=["must_change_password"])

            if p and p.must_change_password:
                allowed = {
                    reverse("accounts:login"),
                    reverse("accounts:logout"),
                    reverse("accounts:alterar_senha"),
                }
                if is_municipal:
                    if (
                        path not in allowed
                        and not path.startswith(onboarding_prefix)
                        and not path.startswith("/admin/")
                    ):
                        return redirect("org:onboarding_wizard_step", step=1)
                elif path not in allowed and not path.startswith("/admin/"):
                    return redirect("accounts:alterar_senha")

            if is_municipal and not self._onboarding_completed(request.user):
                allowed_paths = {
                    reverse("accounts:login"),
                    reverse("accounts:logout"),
                    reverse("accounts:alterar_senha"),
                }
                if (
                    path not in allowed_paths
                    and not path.startswith(onboarding_prefix)
                    and not path.startswith("/admin/")
                ):
                    return redirect("org:onboarding_wizard")

        return self.get_response(request)

    def _onboarding_completed(self, user) -> bool:
        try:
            from apps.org.models import MunicipioOnboardingWizard

            wizard = (
                MunicipioOnboardingWizard.objects.only("completed_at")
                .filter(user_id=user.id)
                .first()
            )
            return bool(wizard and wizard.completed_at)
        except Exception:
            return False
