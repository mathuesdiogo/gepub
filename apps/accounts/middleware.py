from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Se o usuário estiver logado e must_change_password=True,
    redireciona sempre para a tela de alteração de senha.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            p = getattr(request.user, "profile", None)
            if p and p.must_change_password:
                allowed = {
                    reverse("accounts:login"),
                    reverse("accounts:logout"),
                    reverse("accounts:alterar_senha"),
                }
                if request.path not in allowed and not request.path.startswith("/admin/"):
                    return redirect("accounts:alterar_senha")

        return self.get_response(request)
