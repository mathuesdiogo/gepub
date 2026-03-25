#!/usr/bin/env python3
"""Smoke audit de conformidade Design System nas rotas de menu principal."""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.env import load_dotenv_if_exists  # noqa: E402

load_dotenv_if_exists(ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import NoReverseMatch, reverse  # noqa: E402


SIDEBAR_NAV = ROOT / "templates/core/partials/components/layout/sidebar_navigation.html"
REPORT_DIR = ROOT / "reports"
REPORT_PATH = REPORT_DIR / "ds_smoke_report.md"

URL_TAG_RE = re.compile(r"""\{%\s*url\s+['"]([^'"]+)['"]([^%]*)%\}""")
CLASS_ATTR_RE = re.compile(r'class="([^"]+)"')
TABLE_RE = re.compile(r"<table\b", re.IGNORECASE)


def collect_route_names() -> list[dict]:
    content = SIDEBAR_NAV.read_text(encoding="utf-8")
    routes = []
    for match in URL_TAG_RE.finditer(content):
        name = match.group(1).strip()
        raw_args = (match.group(2) or "").strip()
        if ":" not in name:
            continue
        arg_count = 0
        if raw_args:
            tokens = [token for token in raw_args.split() if token]
            arg_count = len(tokens)
        routes.append({"name": name, "arg_count": arg_count})

    dedup = {}
    for route in routes:
        key = route["name"]
        current = dedup.get(key)
        if current is None or route["arg_count"] < current["arg_count"]:
            dedup[key] = route
    return sorted(dedup.values(), key=lambda item: item["name"])


def get_admin_user():
    user_model = get_user_model()
    user = (
        user_model.objects.filter(is_active=True, is_superuser=True)
        .order_by("id")
        .first()
    )
    created = False
    if user is None:
        user = user_model.objects.create_superuser(
            username="codex_smoke_admin",
            email="codex-smoke@example.com",
            password="codex123456",
        )
        created = True
    return user, created


def get_sample_codigo_acesso() -> str:
    from apps.accounts.models import Profile

    code = (
        Profile.objects.exclude(codigo_acesso="")
        .values_list("codigo_acesso", flat=True)
        .first()
    )
    return code or "demo"


def classify_html(html: str) -> dict[str, int]:
    issues = Counter()
    html_lower = html.lower()
    if TABLE_RE.search(html_lower) and "gp-table__native" not in html:
        issues["table_sem_gp_table_native"] += 1

    for match in CLASS_ATTR_RE.finditer(html):
        classes = match.group(1).split()
        class_set = set(classes)
        if "btn" in class_set and "gp-button" not in class_set:
            issues["btn_sem_gp_button"] += 1
        if "card" in class_set and "gp-card" not in class_set:
            issues["card_sem_gp_card"] += 1
        if "badge" in class_set and "gp-badge" not in class_set:
            issues["badge_sem_gp_badge"] += 1
        if "alert" in class_set and "gp-alert" not in class_set:
            issues["alert_sem_gp_alert"] += 1
        if "filter-bar" in class_set and "search-and-filters" not in class_set:
            issues["filter_sem_search_and_filters"] += 1
        if "table-responsive" in class_set and "gp-table" not in class_set:
            issues["table_responsive_sem_gp_table"] += 1
    return dict(issues)


def render_report(summary: dict, rows: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Relatório Smoke DS\n")
    lines.append("## Resumo")
    lines.append(f"- Rotas de menu analisadas: **{summary['routes_total']}**")
    lines.append(f"- Rotas válidas para reverse(): **{summary['routes_resolved']}**")
    lines.append(f"- Rotas com parâmetro auditadas com amostra: **{summary['routes_with_params_audited']}**")
    lines.append(f"- Rotas com parâmetro não auditadas: **{summary['routes_with_params_skipped']}**")
    lines.append(f"- Rotas não resolvidas no menu: **{summary['reverse_unresolved']}**")
    lines.append(f"- Respostas HTTP 200: **{summary['http_200']}**")
    lines.append(f"- Redirecionadas: **{summary['redirected']}**")
    lines.append(f"- Falhas (>=400): **{summary['http_error']}**")
    lines.append(f"- Com issues DS: **{summary['routes_with_issues']}**")
    lines.append("")

    lines.append("## Issues agregadas")
    if not summary["issues_counter"]:
        lines.append("- Nenhuma issue detectada nas páginas 200.")
    else:
        for key, value in sorted(
            summary["issues_counter"].items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"- `{key}`: **{value}**")
    lines.append("")

    lines.append("## Rotas com issue de DS")
    issue_rows = [row for row in rows if row["issues"]]
    if not issue_rows:
        lines.append("- Nenhuma rota com issue detectada.")
    else:
        lines.append("| Rota | URL | Status | Issues |")
        lines.append("| --- | --- | ---: | --- |")
        for row in issue_rows:
            lines.append(
                f"| `{row['name']}` | `{row['url']}` | {row['status']} | {', '.join(row['issues'])} |"
            )
    lines.append("")

    lines.append("## Rotas não resolvidas no sidebar")
    unresolved_rows = [row for row in rows if row["status"] == 0 and row["url"] == ""]
    if not unresolved_rows:
        lines.append("- Nenhuma rota não resolvida.")
    else:
        lines.append("| Rota | Observação |")
        lines.append("| --- | --- |")
        for row in unresolved_rows:
            lines.append(f"| `{row['name']}` | `reverse_unresolved` |")
    lines.append("")

    lines.append("## Rotas paramétricas não auditadas")
    param_rows = [row for row in rows if row["status"] == -1]
    if not param_rows:
        lines.append("- Nenhuma rota paramétrica.")
    else:
        lines.append("| Rota | Argumentos |")
        lines.append("| --- | ---: |")
        for row in param_rows:
            lines.append(f"| `{row['name']}` | {row['arg_count']} |")
    lines.append("")

    lines.append("## Rotas com erro HTTP")
    error_rows = [row for row in rows if row["status"] >= 400]
    if not error_rows:
        lines.append("- Nenhuma rota retornou erro HTTP.")
    else:
        lines.append("| Rota | URL | Status |")
        lines.append("| --- | --- | ---: |")
        for row in error_rows:
            lines.append(f"| `{row['name']}` | `{row['url']}` | {row['status']} |")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    routes = collect_route_names()
    allowed = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
    if "testserver" not in allowed:
        allowed.append("testserver")
    if "localhost" not in allowed:
        allowed.append("localhost")
    if "127.0.0.1" not in allowed:
        allowed.append("127.0.0.1")
    settings.ALLOWED_HOSTS = allowed

    client = Client(HTTP_HOST="localhost")
    user, _created = get_admin_user()
    client.force_login(user)
    sample_codigo = get_sample_codigo_acesso()

    rows: list[dict] = []
    issues_counter: Counter = Counter()

    resolved = 0
    http_200 = 0
    redirected = 0
    http_error = 0

    for route in routes:
        name = route["name"]
        arg_count = route["arg_count"]
        row = {
            "name": name,
            "url": "",
            "status": 0,
            "issues": [],
            "arg_count": arg_count,
        }
        try:
            if arg_count == 0:
                url = reverse(name)
            elif arg_count == 1:
                url = reverse(name, args=[sample_codigo])
                row["sample_arg"] = sample_codigo
            else:
                row["status"] = -1
                rows.append(row)
                continue
        except NoReverseMatch:
            row["status"] = 0
            row["issues"] = []
            rows.append(row)
            continue

        resolved += 1
        row["url"] = url

        try:
            response = client.get(url, follow=True)
        except Exception as exc:  # pragma: no cover - script safety
            row["status"] = 500
            row["issues"] = [f"exception:{type(exc).__name__}"]
            rows.append(row)
            http_error += 1
            continue

        row["status"] = int(response.status_code)
        if response.redirect_chain:
            redirected += 1

        if response.status_code >= 400:
            http_error += 1
            rows.append(row)
            continue

        if response.status_code == 200:
            http_200 += 1
            body = response.content.decode("utf-8", errors="ignore")
            issues = classify_html(body)
            if issues:
                row["issues"] = sorted(issues.keys())
                issues_counter.update(issues)
        rows.append(row)

    routes_with_issues = sum(1 for row in rows if row["issues"] and row["status"] == 200)
    summary = {
        "routes_total": len(routes),
        "routes_resolved": resolved,
        "routes_with_params_audited": len([row for row in rows if row.get("arg_count", 0) > 0 and row["status"] >= 200]),
        "routes_with_params_skipped": len([row for row in rows if row["status"] == -1]),
        "reverse_unresolved": len([row for row in rows if row["status"] == 0 and row["url"] == ""]),
        "http_200": http_200,
        "redirected": redirected,
        "http_error": http_error,
        "routes_with_issues": routes_with_issues,
        "issues_counter": dict(issues_counter),
    }

    render_report(summary, rows)
    print(f"report={REPORT_PATH}")
    print(
        "summary:",
        f"total={summary['routes_total']}",
        f"resolved={summary['routes_resolved']}",
        f"http200={summary['http_200']}",
        f"errors={summary['http_error']}",
        f"routes_with_issues={summary['routes_with_issues']}",
    )
    for key, value in sorted(summary["issues_counter"].items()):
        print(f"issue:{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
