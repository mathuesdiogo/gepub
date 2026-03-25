#!/usr/bin/env python3
"""Audita aderência mínima dos templates ao Design System do GEPUB."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
DS_DOCS_FILES = (
    ROOT / "templates/core/design_system/index.html",
    ROOT / "templates/core/design_system/components.html",
)

REFERENCE_SECTIONS = {
    "geral": (
        "Padrões web",
        "Nomenclaturas",
        "Template Filters",
        "Template Tags",
    ),
    "botoes_acoes": (
        "Botões",
        "Barra de ações",
        "Ícones de ações",
    ),
    "formularios": (
        "Formulários",
        "Avaliação com estrelas",
        "Barra de busca e filtros",
        "Botão: Switch",
        "Checkbox: Marcar todos",
    ),
    "tabelas_listas": (
        "Tabelas e listas",
        "Lista de definições",
        "Listas de links",
        "Lista com botão de ação",
    ),
    "mensagens": (
        "Alertas",
        "Estilo tooltip",
        "Situações",
    ),
    "navegacao": (
        "Abas",
        "Âncoras",
        "Pills",
    ),
    "caixas_sessoes": (
        "Accordion/Box",
        "Board",
        "Caixa Links",
        "Caixa Indicadores",
        "Caixa Textos",
        "Caixa Geral",
        "Card",
        "Farol",
        "Fotos",
        "General Box",
        "Totalizadores",
    ),
    "componentes": (
        "Badges",
        "Barra de carregamento",
        "Barra de progresso",
        "Calendários",
        "Checklist",
        "Foto de Pessoa",
        "Gráficos",
        "Passos",
        "Timeline",
    ),
}

CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')
TABLE_RE = re.compile(r"<table\b", re.IGNORECASE)


def iter_class_tokens():
    for path in TEMPLATES_DIR.rglob("*.html"):
        if "core/design_system/" in path.as_posix():
            continue
        content = path.read_text(encoding="utf-8")
        for match in CLASS_ATTR_RE.finditer(content):
            tokens = tuple(token for token in match.group(1).split() if token)
            yield path, tokens


def main() -> int:
    metrics = Counter()
    template_count = 0
    table_count = 0
    table_with_ds = 0

    for path in TEMPLATES_DIR.rglob("*.html"):
        if "core/design_system/" in path.as_posix():
            continue
        template_count += 1
        content = path.read_text(encoding="utf-8")
        table_count += len(TABLE_RE.findall(content))
        table_with_ds += len(
            re.findall(r'<table(?=[^>]*class="[^"]*\bgp-table__native\b)[^>]*>', content)
        )

    for _path, classes in iter_class_tokens():
        class_set = set(classes)
        if "btn" in class_set:
            metrics["btn_total"] += 1
            if "gp-button" in class_set:
                metrics["btn_with_ds"] += 1
        if "card" in class_set:
            metrics["card_total"] += 1
            if "gp-card" in class_set:
                metrics["card_with_ds"] += 1
        if "badge" in class_set:
            metrics["badge_total"] += 1
            if "gp-badge" in class_set:
                metrics["badge_with_ds"] += 1
        if "alert" in class_set:
            metrics["alert_total"] += 1
            if "gp-alert" in class_set:
                metrics["alert_with_ds"] += 1
        if "gp-table__filters" in class_set:
            metrics["filters_total"] += 1
            if "search-and-filters" in class_set:
                metrics["filters_with_ds"] += 1
        if "gp-form" in class_set:
            metrics["forms_total"] += 1
            if "form-shell" in class_set:
                metrics["forms_with_ds"] += 1

    print(f"templates={template_count}")
    print(f"tables={table_count} tables_with_gp_table_native={table_with_ds}")
    print(f"btn_total={metrics['btn_total']} btn_with_ds={metrics['btn_with_ds']}")
    print(f"card_total={metrics['card_total']} card_with_ds={metrics['card_with_ds']}")
    print(f"badge_total={metrics['badge_total']} badge_with_ds={metrics['badge_with_ds']}")
    print(f"alert_total={metrics['alert_total']} alert_with_ds={metrics['alert_with_ds']}")
    print(
        f"filters_total={metrics['filters_total']} "
        f"filters_with_ds={metrics['filters_with_ds']}"
    )
    print(f"forms_total={metrics['forms_total']} forms_with_ds={metrics['forms_with_ds']}")

    docs_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in DS_DOCS_FILES
        if path.exists()
    ).lower()
    print("section_coverage:")
    for key, labels in REFERENCE_SECTIONS.items():
        found = sum(1 for label in labels if label.lower() in docs_text)
        total = len(labels)
        pct = round((found / total) * 100, 1) if total else 0.0
        print(f"  {key}={found}/{total} ({pct}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
