from django.http import HttpResponseForbidden
from django.urls import resolve

from .rbac import (
    can,
    PERM_ORG_VIEW, PERM_ORG_EDIT,
    PERM_EDU_VIEW, PERM_EDU_EDIT,
    PERM_NEE_VIEW, PERM_NEE_EDIT, PERM_NEE_REPORTS,
    PERM_ACCOUNTS_PROFILE, PERM_ACCOUNTS_MANAGE,
)


# ✅ Regra geral por namespace:
# - qualquer página do namespace precisa do "...view"
NAMESPACE_BASE = {
    "org": PERM_ORG_VIEW,
    "educacao": PERM_EDU_VIEW,
    "nee": PERM_NEE_VIEW,
    "accounts": PERM_ACCOUNTS_PROFILE,
}

# ✅ Views “de edição” (create/update) por namespace
# Se o url_name estiver nessa lista, exige permissão edit/manage.
EDIT_RULES = {
    "org": {
        "municipio_create": PERM_ORG_EDIT,
        "municipio_update": PERM_ORG_EDIT,
        "secretaria_create": PERM_ORG_EDIT,
        "secretaria_update": PERM_ORG_EDIT,
        "unidade_create": PERM_ORG_EDIT,
        "unidade_update": PERM_ORG_EDIT,
        "setor_create": PERM_ORG_EDIT,
        "setor_update": PERM_ORG_EDIT,
    },
    "educacao": {
        "turma_create": PERM_EDU_EDIT,
        "turma_update": PERM_EDU_EDIT,
        "aluno_create": PERM_EDU_EDIT,
        "aluno_update": PERM_EDU_EDIT,
        "matricula_create": PERM_EDU_EDIT,
        "matricula_update": PERM_EDU_EDIT,
        # se você tiver apoio/matrícula editável dentro da educação/nee, ajusta aqui
    },
    "nee": {
        # Tipos e cadastros do NEE (CRUD)
        "tipo_create": PERM_NEE_EDIT,
        "tipo_update": PERM_NEE_EDIT,
    },
    "accounts": {
        # gestão de usuários
        "usuarios_list": PERM_ACCOUNTS_MANAGE,
        "usuario_create": PERM_ACCOUNTS_MANAGE,
        "usuario_update": PERM_ACCOUNTS_MANAGE,
        "usuario_reset_senha": PERM_ACCOUNTS_MANAGE,
        # perfil/troca de senha continua PERM_ACCOUNTS_PROFILE
    },
}

# ✅ Relatórios do NEE exigem perm específica de relatórios
NEE_REPORT_URLNAMES = {"relatorios_index", "relatorio_por_tipo", "relatorio_por_municipio", "relatorio_por_unidade"}


class RBACMiddleware:
    """
    Bloqueia backend de verdade.
    Mesmo que o usuário digite a URL na mão, se não tiver permissão, recebe 403.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ignora assets e admin do Django (o próprio Django já protege /admin/)
        path = request.path or ""
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        # Se não está logado, deixa o Django lidar com login_required nas views
        if not request.user.is_authenticated:
            return self.get_response(request)

        try:
            match = resolve(path)
        except Exception:
            return self.get_response(request)

        namespace = match.namespace or ""
        url_name = match.url_name or ""

        # Só controla namespaces do nosso sistema
        if namespace in NAMESPACE_BASE:
            # 1) perm base (view)
            required = NAMESPACE_BASE[namespace]
            if not can(request.user, required):
                return HttpResponseForbidden("Sem permissão para acessar esta área.")

            # 2) regras de edição por url_name
            required_edit = EDIT_RULES.get(namespace, {}).get(url_name)
            if required_edit and not can(request.user, required_edit):
                return HttpResponseForbidden("Sem permissão para executar esta ação.")

            # 3) relatórios do NEE
            if namespace == "nee" and url_name in NEE_REPORT_URLNAMES:
                if not can(request.user, PERM_NEE_REPORTS):
                    return HttpResponseForbidden("Sem permissão para acessar relatórios.")

        return self.get_response(request)
