from .rbac import get_user_perms, _tree_from_perms


def permissions(request):
    """
    Injeta `perms` no template (substitui o `perms` do Django auth),
    no formato:
      perms.org.view, perms.educacao.edit, perms.accounts.manage...
    """
    perms_set = get_user_perms(request.user)
    return {"perms": _tree_from_perms(perms_set)}
