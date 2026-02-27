from __future__ import annotations


def get_municipio_from_unidade(unidade):
    if not unidade:
        return None
    for chain in [
        ("municipio",),
        ("secretaria", "municipio"),
        ("secretaria", "municipio", "nome"),
        ("municipio", "nome"),
        ("secretaria", "municipio", "nome"),
    ]:
        try:
            obj = unidade
            for attr in chain:
                obj = getattr(obj, attr)
            if hasattr(obj, "nome"):
                return obj.nome
            if isinstance(obj, str):
                return obj
        except Exception:
            continue
    return getattr(unidade, "municipio_nome", None)
