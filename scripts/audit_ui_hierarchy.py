#!/usr/bin/env python3
"""Audita hierarquia de UI (tamanhos/espaçamentos) por app em templates."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
REPORT_PATH = ROOT / "reports" / "ui_hierarchy_audit.md"

CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]+)"', re.IGNORECASE)
INLINE_SPACING_RE = re.compile(r'style\s*=\s*"[^"]*(?:margin|padding)\s*:', re.IGNORECASE)
RAW_SPACING_TOKEN_RE = re.compile(r"^(?:m[trblxy]-\d+|p[trblxy]-\d+|mt-20|mb-20)$")


@dataclass
class AppStats:
    files: int = 0
    module_templates: int = 0
    raw_spacing_tokens: int = 0
    inline_spacing_styles: int = 0
    page_head_usage: int = 0
    table_shell_usage: int = 0
    form_shell_usage: int = 0


def app_name_for(path: Path) -> str:
    rel = path.relative_to(TEMPLATES_DIR)
    return rel.parts[0] if rel.parts else "root"


def main() -> int:
    app_stats: dict[str, AppStats] = defaultdict(AppStats)
    raw_spacing_files: Counter[str] = Counter()
    inline_style_files: Counter[str] = Counter()

    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        app = app_name_for(path)
        stats = app_stats[app]
        stats.files += 1

        text = path.read_text(encoding="utf-8", errors="ignore")
        if "{% block module_content %}" in text:
            stats.module_templates += 1
        if "page_head.html" in text:
            stats.page_head_usage += 1
        if "table_shell.html" in text:
            stats.table_shell_usage += 1
        if "form-shell" in text:
            stats.form_shell_usage += 1

        inline_hits = len(INLINE_SPACING_RE.findall(text))
        if inline_hits:
            stats.inline_spacing_styles += inline_hits
            inline_style_files[str(path.relative_to(ROOT))] += inline_hits

        raw_hits = 0
        for class_match in CLASS_ATTR_RE.finditer(text):
            tokens = [token.strip() for token in class_match.group(1).split() if token.strip()]
            for token in tokens:
                if token.startswith("u-") or token.startswith("gp-"):
                    continue
                if RAW_SPACING_TOKEN_RE.match(token):
                    raw_hits += 1
        if raw_hits:
            stats.raw_spacing_tokens += raw_hits
            raw_spacing_files[str(path.relative_to(ROOT))] += raw_hits

    lines: list[str] = []
    lines.append("# Auditoria de Hierarquia UI")
    lines.append("")
    lines.append("Critérios auditados por app:")
    lines.append("- quantidade de templates HTML")
    lines.append("- cobertura de `module_content`, `page_head`, `table_shell`, `form-shell`")
    lines.append("- ocorrências de classes de espaçamento legadas (`mt-*`, `mb-*`, `pt-*`, `pb-*`, etc.)")
    lines.append("- ocorrências de `style=\"...margin/padding...\"`")
    lines.append("")
    lines.append("| App | HTML | Module | Page Head | Table Shell | Form Shell | Legacy Spacing | Inline Style Spacing |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for app in sorted(app_stats):
        s = app_stats[app]
        lines.append(
            f"| `{app}` | {s.files} | {s.module_templates} | {s.page_head_usage} | "
            f"{s.table_shell_usage} | {s.form_shell_usage} | {s.raw_spacing_tokens} | {s.inline_spacing_styles} |"
        )

    lines.append("")
    lines.append("## Arquivos com mais classes de espaçamento legado")
    if raw_spacing_files:
        for path, count in raw_spacing_files.most_common(25):
            lines.append(f"- `{path}`: {count}")
    else:
        lines.append("- Nenhum arquivo com classes legadas de espaçamento detectado.")

    lines.append("")
    lines.append("## Arquivos com style inline de margin/padding")
    if inline_style_files:
        for path, count in inline_style_files.most_common(25):
            lines.append(f"- `{path}`: {count}")
    else:
        lines.append("- Nenhum style inline de espaçamento detectado.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report={REPORT_PATH}")
    print(f"apps={len(app_stats)}")
    print(f"legacy_spacing_total={sum(s.raw_spacing_tokens for s in app_stats.values())}")
    print(f"inline_spacing_total={sum(s.inline_spacing_styles for s in app_stats.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

