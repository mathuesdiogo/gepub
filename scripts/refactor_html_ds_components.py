#!/usr/bin/env python3
"""Refatoração em lote de templates HTML para padrões DS (forms/tables/actions)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
EXCLUDED_PREFIXES = (
    "templates/core/design_system/",
)

TAG_WITH_CLASS_RE = re.compile(
    r"<(?P<tag>[a-zA-Z][\w:-]*)(?P<before>[^<>]*?)\sclass=\"(?P<class>[^\"]*)\"(?P<after>[^<>]*)>",
    re.IGNORECASE,
)
FORM_OPEN_RE = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
FORM_CLOSE_RE = re.compile(r"</form>", re.IGNORECASE)
TABLE_OPEN_NO_CLASS_RE = re.compile(r"<table\b(?![^>]*\bclass=)([^>]*)>", re.IGNORECASE)
INPUT_RE = re.compile(r"<input\b[^>]*>", re.IGNORECASE)
INPUT_TYPE_RE = re.compile(r'\btype\s*=\s*"([^"]+)"', re.IGNORECASE)
SELECT_OR_TEXTAREA_RE = re.compile(r"<(select|textarea)\b", re.IGNORECASE)

FORM_DS_TOKENS = {
    "form-shell",
    "gp-form",
    "search-and-filters",
    "filter-bar",
    "topbar-search",
    "u-inline-form",
    "gp-inline-form",
    "cc-form",
    "pp-form-inline",
    "pp-form-stack",
    "onboarding-form",
    "publicacoes-filter",
}

INLINE_HINT_TOKENS = {
    "inline-action-form",
    "u-inline-flex",
    "gp-inline-form",
    "u-inline-form",
}

FILTER_HINT_TOKENS = {"filter", "search"}


@dataclass
class FileStats:
    files_changed: int = 0
    class_tags_changed: int = 0
    forms_without_class_fixed: int = 0
    tables_without_class_fixed: int = 0


def split_tokens(class_str: str) -> list[str]:
    return [token for token in class_str.split() if token]


def merge_tokens(tokens: list[str], additions: list[str]) -> list[str]:
    seen = set(tokens)
    out = list(tokens)
    for token in additions:
        if token and token not in seen:
            out.append(token)
            seen.add(token)
    return out


def has_visible_fields(form_html_fragment: str) -> bool:
    if SELECT_OR_TEXTAREA_RE.search(form_html_fragment):
        return True
    for input_match in INPUT_RE.finditer(form_html_fragment):
        tag = input_match.group(0)
        type_match = INPUT_TYPE_RE.search(tag)
        input_type = (type_match.group(1).strip().lower() if type_match else "text")
        if input_type not in {"hidden", "submit", "button", "reset", "image"}:
            return True
    return False


def normalize_class_tag(match: re.Match[str], stats: FileStats) -> str:
    tag = match.group("tag")
    before = match.group("before")
    class_str = match.group("class")
    after = match.group("after")

    tokens = split_tokens(class_str)
    original = list(tokens)
    lower_tokens = {token.lower() for token in tokens}

    # Buttons and action styles
    if "btn" in lower_tokens and "gp-button" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button"])
        lower_tokens = {token.lower() for token in tokens}

    if ("btn-primary" in lower_tokens or "primary" in lower_tokens) and "gp-button--primary" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--primary"])
        lower_tokens = {token.lower() for token in tokens}
    if ("btn-danger" in lower_tokens or "danger" in lower_tokens) and "gp-button--danger" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--danger"])
        lower_tokens = {token.lower() for token in tokens}
    if ("btn-warning" in lower_tokens or "warning" in lower_tokens) and "gp-button--warning" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--warning"])
        lower_tokens = {token.lower() for token in tokens}
    if ("btn-success" in lower_tokens or "success" in lower_tokens) and "gp-button--success" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--success"])
        lower_tokens = {token.lower() for token in tokens}
    if ("btn-default" in lower_tokens or "default" in lower_tokens) and "gp-button--default" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--default"])
        lower_tokens = {token.lower() for token in tokens}
    if ("btn-secondary" in lower_tokens or "secondary" in lower_tokens) and "gp-button--secondary" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--secondary"])
        lower_tokens = {token.lower() for token in tokens}
    if ("btn-outline" in lower_tokens or "outline" in lower_tokens) and "gp-button--outline" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-button--outline"])
        lower_tokens = {token.lower() for token in tokens}

    if "action-bar" in lower_tokens and "gp-action-bar" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-action-bar"])
        lower_tokens = {token.lower() for token in tokens}

    # Data display and feedback alignment
    if "card" in lower_tokens and "gp-card" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-card"])
        lower_tokens = {token.lower() for token in tokens}
    if "badge" in lower_tokens and "gp-badge" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-badge"])
        lower_tokens = {token.lower() for token in tokens}
    if "alert" in lower_tokens and "gp-alert" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-alert"])
        lower_tokens = {token.lower() for token in tokens}

    # Table wrappers
    if "table-shell" in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-table", "gp-table--responsive"])
        lower_tokens = {token.lower() for token in tokens}
    if "table-responsive" in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-table", "gp-table--responsive"])
        lower_tokens = {token.lower() for token in tokens}

    # Tables
    if tag.lower() == "table" and "gp-table__native" not in lower_tokens:
        tokens = merge_tokens(tokens, ["gp-table__native"])
        lower_tokens = {token.lower() for token in tokens}

    # Forms
    if tag.lower() == "form":
        has_ds = any(token.lower() in FORM_DS_TOKENS for token in tokens)
        if not has_ds:
            class_blob = " ".join(tokens).lower()
            looks_like_filter = any(hint in class_blob for hint in FILTER_HINT_TOKENS)
            looks_inline = any(hint in lower_tokens for hint in INLINE_HINT_TOKENS)
            if looks_like_filter:
                tokens = merge_tokens(tokens, ["form-shell", "search-and-filters"])
            elif looks_inline:
                tokens = merge_tokens(tokens, ["u-inline-form"])
            else:
                tokens = merge_tokens(tokens, ["form-shell"])
            lower_tokens = {token.lower() for token in tokens}
        if (
            any(hint in " ".join(tokens).lower() for hint in FILTER_HINT_TOKENS)
            and "search-and-filters" not in lower_tokens
            and "topbar-search" not in lower_tokens
        ):
            tokens = merge_tokens(tokens, ["search-and-filters"])
            lower_tokens = {token.lower() for token in tokens}

    if tokens == original:
        return match.group(0)

    stats.class_tags_changed += 1
    new_class = " ".join(tokens)
    return f"<{tag}{before} class=\"{new_class}\"{after}>"


def add_class_to_forms_without_class(text: str, stats: FileStats) -> str:
    matches = list(FORM_OPEN_RE.finditer(text))
    if not matches:
        return text

    replacements: list[tuple[int, int, str]] = []
    for match in matches:
        tag = match.group(0)
        if re.search(r"\bclass\s*=", tag, re.IGNORECASE):
            continue

        close_match = FORM_CLOSE_RE.search(text, match.end())
        form_content = text[match.end() : close_match.start()] if close_match else ""
        cls = "form-shell" if has_visible_fields(form_content) else "u-inline-form"

        if tag.endswith("/>"):
            new_tag = tag[:-2] + f' class="{cls}" />'
        else:
            new_tag = tag[:-1] + f' class="{cls}">'

        replacements.append((match.start(), match.end(), new_tag))
        stats.forms_without_class_fixed += 1

    if not replacements:
        return text

    out = text
    for start, end, new_value in reversed(replacements):
        out = out[:start] + new_value + out[end:]
    return out


def add_class_to_tables_without_class(text: str, stats: FileStats) -> str:
    def _repl(match: re.Match[str]) -> str:
        stats.tables_without_class_fixed += 1
        suffix = match.group(1) or ""
        if suffix.endswith("/"):
            suffix = suffix[:-1].rstrip()
            return f'<table class="gp-table__native" {suffix} />' if suffix else '<table class="gp-table__native" />'
        return f'<table class="gp-table__native"{suffix}>'

    return TABLE_OPEN_NO_CLASS_RE.sub(_repl, text)


def process_file(path: Path, stats: FileStats) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original

    text = TAG_WITH_CLASS_RE.sub(lambda m: normalize_class_tag(m, stats), text)
    text = add_class_to_forms_without_class(text, stats)
    text = add_class_to_tables_without_class(text, stats)

    if text == original:
        return False

    path.write_text(text, encoding="utf-8")
    stats.files_changed += 1
    return True


def main() -> int:
    stats = FileStats()
    for path in TEMPLATES_DIR.rglob("*.html"):
        path_posix = path.as_posix()
        if any(path_posix.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue
        process_file(path, stats)

    print(f"files_changed={stats.files_changed}")
    print(f"class_tags_changed={stats.class_tags_changed}")
    print(f"forms_without_class_fixed={stats.forms_without_class_fixed}")
    print(f"tables_without_class_fixed={stats.tables_without_class_fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
