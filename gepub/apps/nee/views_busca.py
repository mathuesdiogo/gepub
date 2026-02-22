from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

@login_required
def buscar_aluno(request):
    """Página simples para localizar alunos e acessar recursos NEE.
    No momento, direciona para a listagem geral de alunos no módulo Educação.
    """
    context = {
        "actions": [
            {
                "label": "Ver alunos",
                "url": reverse("educacao:aluno_list"),
                "icon": "fa-solid fa-users",
                "variant": "primary",
            },
        ],
    }
    return render(request, "nee/buscar_aluno.html", context)
