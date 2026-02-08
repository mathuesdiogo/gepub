from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect


def login_view(request):
    if request.user.is_authenticated:
        return redirect(getattr(settings, "LOGIN_REDIRECT_URL", "/"))

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next") or getattr(settings, "LOGIN_REDIRECT_URL", "/")
            return redirect(next_url)

        error = "Usuário ou senha inválidos."

    return render(request, "accounts/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", "/accounts/login/"))
