from __future__ import annotations

from collections import defaultdict

from apps.accounts.models import Profile
from apps.core.rbac import ROLE_MANAGEMENT_ALLOWED, ROLE_PERMS, ROLE_PERMS_FINE, ROLE_SCOPE_BASE, role_scope_base


ROLE_LABELS: dict[str, str] = {value: label for value, label in Profile.Role.choices}

CATEGORY_ORDER = [
    "governanca",
    "educacao",
    "saude",
    "operacao",
    "portais",
    "integracoes",
    "dados",
    "cidadao",
    "outros",
]

CATEGORY_LABELS = {
    "governanca": "Administração e Governança",
    "educacao": "Educação",
    "saude": "Saúde",
    "operacao": "Operação Administrativa",
    "portais": "Portais e Conteúdo",
    "integracoes": "Integrações e TI",
    "dados": "Dados e BI",
    "cidadao": "Portais do Cidadão",
    "outros": "Outros",
}

ROLE_CATEGORY_HINTS = {
    "ADMIN": "governanca",
    "MUNICIPAL": "governanca",
    "SECRETARIA": "governanca",
    "UNIDADE": "governanca",
    "LEITURA": "governanca",
    "AUDITORIA": "governanca",
    "RH_GESTOR": "operacao",
    "PROTOCOLO": "operacao",
    "CAD_GESTOR": "governanca",
    "CAD_OPER": "governanca",
    "SAU_SECRETARIO": "saude",
    "SAU_DIRETOR": "saude",
    "SAU_COORD": "saude",
    "SAU_MEDICO": "saude",
    "SAU_ENFERMEIRO": "saude",
    "SAU_TEC_ENF": "saude",
    "SAU_ACS": "saude",
    "SAU_RECEPCAO": "saude",
    "SAU_REGULACAO": "saude",
    "SAU_FARMACIA": "saude",
    "EDU_SECRETARIO": "educacao",
    "EDU_DIRETOR": "educacao",
    "EDU_COORD": "educacao",
    "EDU_PROF": "educacao",
    "PROFESSOR": "educacao",
    "EDU_SECRETARIA": "educacao",
    "EDU_TRANSPORTE": "educacao",
    "ALUNO": "cidadao",
    "NEE": "educacao",
    "NEE_COORD_MUN": "educacao",
    "NEE_COORD_ESC": "educacao",
    "NEE_MEDIADOR": "educacao",
    "NEE_TECNICO": "educacao",
    "DADOS_GESTOR": "dados",
    "DADOS_ANALISTA": "dados",
    "INT_TI": "integracoes",
    "INT_GESTAO": "integracoes",
    "INT_LEITOR": "integracoes",
    "PORTAL_ADMIN": "portais",
    "PORTAL_EDITOR": "portais",
    "PORTAL_APROV": "portais",
    "PORTAL_DESIGN": "portais",
    "CAMARA_ADMIN": "portais",
    "CAMARA_SECRETARIA": "portais",
    "CAMARA_COMUNICACAO": "portais",
    "CAMARA_TRANSPARENCIA": "portais",
    "CAMARA_VEREADOR": "portais",
    "CAMARA_AUDITOR": "portais",
    "CIDADAO": "cidadao",
}

APP_LABELS = {
    "accounts": "Contas e Acessos",
    "org": "Organização",
    "educacao": "Educação",
    "avaliacoes": "Avaliações",
    "nee": "NEE",
    "saude": "Saúde",
    "billing": "Plano e Assinatura",
    "financeiro": "Financeiro",
    "processos": "Processos",
    "compras": "Compras",
    "contratos": "Contratos",
    "integracoes": "Integrações",
    "comunicacao": "Comunicação",
    "paineis": "Painéis BI",
    "conversor": "Ferramentas PDF",
    "rh": "RH",
    "ponto": "Ponto",
    "folha": "Folha",
    "patrimonio": "Patrimônio",
    "almoxarifado": "Almoxarifado",
    "frota": "Frota",
    "ouvidoria": "Ouvidoria",
    "tributos": "Tributos",
    "camara": "Câmara",
    "reports": "Relatórios",
    "system": "Sistema",
}

APP_ORDER = [
    "accounts",
    "org",
    "educacao",
    "avaliacoes",
    "nee",
    "saude",
    "financeiro",
    "processos",
    "compras",
    "contratos",
    "rh",
    "ponto",
    "folha",
    "patrimonio",
    "almoxarifado",
    "frota",
    "ouvidoria",
    "tributos",
    "camara",
    "integracoes",
    "comunicacao",
    "paineis",
    "conversor",
    "billing",
    "reports",
    "system",
]

ACTION_LABELS = {
    "view": "ver",
    "manage": "operar",
    "admin": "administrar",
    "send": "enviar",
    "audit": "auditar",
    "publish": "publicar",
    "contabilidade": "contabilidade",
    "tesouraria": "tesouraria",
}


def _humanize_code(code: str) -> str:
    return (code or "").replace("_", " ").title().strip() or "Sem descrição"


def role_label(role_code: str) -> str:
    role = (role_code or "").strip().upper()
    return ROLE_LABELS.get(role, _humanize_code(role))


def _role_category(role_code: str) -> str:
    role = (role_code or "").strip().upper()
    if role in ROLE_CATEGORY_HINTS:
        return ROLE_CATEGORY_HINTS[role]

    if role.startswith("EDU") or role.startswith("NEE") or role in {"PROFESSOR", "ALUNO"}:
        return "educacao"
    if role.startswith("SAU"):
        return "saude"
    if role.startswith("PORTAL") or role.startswith("CAMARA"):
        return "portais"
    if role.startswith("INT"):
        return "integracoes"
    if role.startswith("DADOS"):
        return "dados"
    return "outros"


def _action_label(action: str) -> str:
    raw = (action or "").strip().lower()
    if not raw:
        return "ver"
    if raw in ACTION_LABELS:
        return ACTION_LABELS[raw]
    if raw.endswith(".manage"):
        feature = raw.rsplit(".", 1)[0].replace("_", " ")
        return f"operar {feature}"
    return raw.replace("_", " ")


def _permission_tokens_for_role(role_code: str) -> set[str]:
    role = (role_code or "").strip().upper()
    tokens = set(ROLE_PERMS_FINE.get(role, set()))
    for macro in ROLE_PERMS.get(role, set()):
        tokens.add(f"{macro}.view")
    return tokens


def _apps_from_tokens(permission_tokens: set[str]) -> list[dict]:
    grouped: dict[str, set[str]] = defaultdict(set)

    for perm in sorted(permission_tokens):
        token = (perm or "").strip().lower()
        if not token:
            continue
        if "." in token:
            app, action = token.split(".", 1)
        else:
            app, action = token, "view"
        grouped[app].add(action)

    def app_sort_key(app_key: str):
        if app_key in APP_ORDER:
            return (APP_ORDER.index(app_key), APP_LABELS.get(app_key, app_key))
        return (10_000, APP_LABELS.get(app_key, app_key))

    rows = []
    for app_key in sorted(grouped.keys(), key=app_sort_key):
        actions = sorted(grouped[app_key], key=lambda a: (_action_label(a), a))
        action_labels = [_action_label(a) for a in actions]
        rows.append(
            {
                "app_key": app_key,
                "app_label": APP_LABELS.get(app_key, app_key.title()),
                "actions": actions,
                "action_labels": action_labels,
                "action_summary": ", ".join(action_labels),
            }
        )
    return rows


def _managed_by_map() -> dict[str, list[str]]:
    relation: dict[str, set[str]] = defaultdict(set)
    for manager_role, managed_roles in ROLE_MANAGEMENT_ALLOWED.items():
        for managed in managed_roles:
            relation[(managed or "").strip().upper()].add((manager_role or "").strip().upper())

    output: dict[str, list[str]] = {}
    for managed, managers in relation.items():
        output[managed] = sorted(managers, key=lambda code: role_label(code).lower())
    return output


def build_role_access_matrix(*, include_engine_roles: bool = True) -> list[dict]:
    role_codes = set()

    if include_engine_roles:
        role_codes.update((code or "").strip().upper() for code in ROLE_SCOPE_BASE.keys())
        role_codes.update((code or "").strip().upper() for code in ROLE_PERMS.keys())
        role_codes.update((code or "").strip().upper() for code in ROLE_PERMS_FINE.keys())

    role_codes.update((code or "").strip().upper() for code in ROLE_LABELS.keys())

    managed_by_map = _managed_by_map()

    rows: list[dict] = []
    for role_code in role_codes:
        if not role_code:
            continue
        permissions = _permission_tokens_for_role(role_code)
        apps = _apps_from_tokens(permissions)
        managers = managed_by_map.get(role_code, [])
        category_key = _role_category(role_code)
        rows.append(
            {
                "role_code": role_code,
                "role_label": role_label(role_code),
                "category_key": category_key,
                "category_label": CATEGORY_LABELS.get(category_key, CATEGORY_LABELS["outros"]),
                "scope_base": role_scope_base(role_code),
                "permissions": sorted(permissions),
                "permissions_count": len(permissions),
                "apps": apps,
                "app_keys": sorted({app["app_key"] for app in apps}),
                "apps_count": len(apps),
                "managed_by": managers,
                "managed_by_labels": [role_label(code) for code in managers],
                "is_profile_choice": role_code in ROLE_LABELS,
            }
        )

    def _row_sort_key(row: dict):
        category_key = row["category_key"]
        category_idx = CATEGORY_ORDER.index(category_key) if category_key in CATEGORY_ORDER else 10_000
        return (
            category_idx,
            row["role_label"].lower(),
            row["role_code"],
        )

    return sorted(rows, key=_row_sort_key)


def filter_role_access_matrix(rows: list[dict], *, q: str = "", category: str = "", app_key: str = "") -> list[dict]:
    query = (q or "").strip().lower()
    category_filter = (category or "").strip().lower()
    app_filter = (app_key or "").strip().lower()

    filtered = []
    for row in rows:
        if category_filter and row["category_key"] != category_filter:
            continue
        if app_filter and app_filter not in row["app_keys"]:
            continue
        if query:
            bag = [
                row["role_code"],
                row["role_label"],
                row["category_label"],
                row["scope_base"],
                " ".join(row["app_keys"]),
                " ".join(row["managed_by"]),
            ]
            if not any(query in (item or "").lower() for item in bag):
                continue
        filtered.append(row)
    return filtered


def available_category_options(rows: list[dict]) -> list[tuple[str, str]]:
    keys = {row["category_key"] for row in rows}
    ordered = [key for key in CATEGORY_ORDER if key in keys]
    return [(key, CATEGORY_LABELS.get(key, key.title())) for key in ordered]


def available_app_options(rows: list[dict]) -> list[tuple[str, str]]:
    keys = set()
    for row in rows:
        keys.update(row["app_keys"])

    def app_sort_key(key: str):
        if key in APP_ORDER:
            return (APP_ORDER.index(key), APP_LABELS.get(key, key))
        return (10_000, APP_LABELS.get(key, key))

    ordered = sorted(keys, key=app_sort_key)
    return [(key, APP_LABELS.get(key, key.title())) for key in ordered]


def build_app_overview(rows: list[dict]) -> list[dict]:
    apps: dict[str, dict] = {}

    for row in rows:
        for app in row["apps"]:
            key = app["app_key"]
            if key not in apps:
                apps[key] = {
                    "app_key": key,
                    "app_label": app["app_label"],
                    "roles": set(),
                    "managers": set(),
                }
            apps[key]["roles"].add(row["role_code"])
            apps[key]["managers"].update(row["managed_by"])

    def app_sort_key(item: dict):
        key = item["app_key"]
        if key in APP_ORDER:
            return (APP_ORDER.index(key), item["app_label"])
        return (10_000, item["app_label"])

    output = []
    for item in apps.values():
        output.append(
            {
                "app_key": item["app_key"],
                "app_label": item["app_label"],
                "roles_count": len(item["roles"]),
                "managers_count": len(item["managers"]),
            }
        )

    return sorted(output, key=app_sort_key)


def preview_role_options() -> list[tuple[str, str]]:
    rows = build_role_access_matrix(include_engine_roles=True)
    return [(row["role_code"], row["role_label"]) for row in rows]
