from __future__ import annotations

import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.accounts.services_access_matrix import build_role_access_matrix


class Command(BaseCommand):
    help = "Gera mapa institucional de perfis/acessos por app do GEPUB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["markdown", "csv", "json"],
            default="markdown",
            help="Formato de saída.",
        )
        parser.add_argument(
            "--output",
            default="",
            help="Arquivo de saída. Se omitido, imprime no stdout.",
        )

    def handle(self, *args, **options):
        fmt = options["format"]
        output_path = (options.get("output") or "").strip()

        rows = build_role_access_matrix(include_engine_roles=True)

        if fmt == "csv":
            content = self._to_csv(rows)
        elif fmt == "json":
            content = self._to_json(rows)
        else:
            content = self._to_markdown(rows)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Mapa de acessos exportado para {path}"))
            return

        self.stdout.write(content)

    @staticmethod
    def _to_markdown(rows: list[dict]) -> str:
        lines = [
            "# Mapa Institucional de Perfis e Acessos (GEPUB)",
            "",
            "| Perfil | Código | Categoria | Escopo | Apps | Atribuído por |",
            "|---|---|---|---|---|---|",
        ]
        for row in rows:
            apps = ", ".join(f"{app['app_label']} ({app['action_summary']})" for app in row["apps"]) or "-"
            managers = ", ".join(row["managed_by_labels"]) or "-"
            lines.append(
                "| {role_label} | {role_code} | {category} | {scope} | {apps} | {managers} |".format(
                    role_label=row["role_label"],
                    role_code=row["role_code"],
                    category=row["category_label"],
                    scope=row["scope_base"],
                    apps=apps,
                    managers=managers,
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _to_csv(rows: list[dict]) -> str:
        out: list[str] = []
        headers = [
            "perfil",
            "codigo",
            "categoria",
            "escopo",
            "apps",
            "permissoes",
            "atribuido_por",
            "disponivel_no_cadastro",
        ]

        class _ListWriter:
            def write(self, value: str):
                out.append(value)

        writer = csv.writer(_ListWriter(), delimiter=";")
        writer.writerow(headers)

        for row in rows:
            writer.writerow(
                [
                    row["role_label"],
                    row["role_code"],
                    row["category_label"],
                    row["scope_base"],
                    ", ".join(f"{app['app_label']} ({app['action_summary']})" for app in row["apps"]),
                    ", ".join(row["permissions"]),
                    ", ".join(row["managed_by_labels"]),
                    "SIM" if row.get("is_profile_choice") else "NAO",
                ]
            )
        return "".join(out)

    @staticmethod
    def _to_json(rows: list[dict]) -> str:
        payload = []
        for row in rows:
            payload.append(
                {
                    "role_code": row["role_code"],
                    "role_label": row["role_label"],
                    "category": row["category_label"],
                    "scope_base": row["scope_base"],
                    "apps": row["apps"],
                    "permissions": row["permissions"],
                    "managed_by": row["managed_by_labels"],
                    "is_profile_choice": row.get("is_profile_choice", False),
                }
            )
        return json.dumps(payload, ensure_ascii=False, indent=2)
