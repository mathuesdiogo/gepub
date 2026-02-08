def get_profile(user):
    if not user.is_authenticated:
        return None
    return getattr(user, "profile", None)


def is_admin(user):
    p = get_profile(user)
    return bool(user.is_superuser or (p and p.role == "ADMIN"))


def scope_filter_unidades(user, qs):
    """
    Recebe queryset de Unidade e devolve filtrado conforme o perfil.
    """
    p = get_profile(user)
    if not p or not p.ativo:
        return qs.none()

    if is_admin(user):
        return qs

    if p.role == "MUNICIPAL" and p.municipio_id:
        return qs.filter(secretaria__municipio_id=p.municipio_id)

    if p.role == "UNIDADE" and p.unidade_id:
        return qs.filter(id=p.unidade_id)

    # NEE e LEITURA: por padrão seguem o município se houver
    if p.municipio_id:
        return qs.filter(secretaria__municipio_id=p.municipio_id)

    return qs.none()
