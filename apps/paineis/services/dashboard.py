from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from .ingest import _parse_date, _parse_number, data_dictionary_csv, profile_json_bytes


def load_rows_from_csv_bytes(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = raw.decode("utf-8-sig", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return [], []

    sample = "\n".join(lines[:5])
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    rows = []
    for row in reader:
        rows.append({h: (row.get(h, "") or "").strip() for h in headers})
    return headers, rows


def filter_rows(
    rows: list[dict[str, str]],
    *,
    date_column: str | None,
    date_start: str = "",
    date_end: str = "",
    secretaria: str = "",
    unidade: str = "",
    categoria: str = "",
) -> list[dict[str, str]]:
    date_start_obj = _parse_date(date_start) if date_start else None
    date_end_obj = _parse_date(date_end) if date_end else None

    out: list[dict[str, str]] = []
    for row in rows:
        if secretaria and row.get("secretaria", "") != secretaria:
            continue
        if unidade and row.get("unidade", "") != unidade:
            continue
        if categoria and row.get("categoria", "") != categoria:
            continue

        if date_column:
            row_date = _parse_date(row.get(date_column, ""))
            if date_start_obj and (not row_date or row_date < date_start_obj):
                continue
            if date_end_obj and (not row_date or row_date > date_end_obj):
                continue

        out.append(row)
    return out


def _pick_date_column(schema: list[dict]) -> str | None:
    for col in schema:
        if col.get("type") == "DATA":
            return col.get("name")
    return None


def _pick_numeric_column(schema: list[dict]) -> str | None:
    for col in schema:
        if col.get("type") == "NUMERO":
            return col.get("name")
    return None


def _pick_category_column(schema: list[dict]) -> str | None:
    preferred = ["secretaria", "unidade", "categoria", "setor"]
    by_name = {str(col.get("name", "")): col for col in schema}
    for key in preferred:
        if key in by_name:
            return key

    for col in schema:
        if col.get("type") == "TEXTO":
            return col.get("name")
    return None


def _line_series(rows: list[dict[str, str]], date_col: str | None, value_col: str | None) -> dict:
    if not rows or not date_col:
        return {"labels": [], "values": []}

    grouped = defaultdict(Decimal)
    for row in rows:
        d = _parse_date(row.get(date_col, ""))
        if not d:
            continue
        key = d.strftime("%Y-%m")
        if value_col:
            num = _parse_number(row.get(value_col, "")) or Decimal("0")
            grouped[key] += num
        else:
            grouped[key] += Decimal("1")

    labels = sorted(grouped.keys())
    values = [float(grouped[label]) for label in labels]
    return {"labels": labels, "values": values}


def _ranking(rows: list[dict[str, str]], category_col: str | None, value_col: str | None) -> dict:
    if not rows or not category_col:
        return {"labels": [], "values": []}

    grouped = defaultdict(Decimal)
    for row in rows:
        key = row.get(category_col, "") or "(sem informação)"
        if value_col:
            grouped[key] += _parse_number(row.get(value_col, "")) or Decimal("0")
        else:
            grouped[key] += Decimal("1")

    ordered = sorted(grouped.items(), key=lambda item: item[1], reverse=True)[:12]
    return {
        "labels": [k for k, _ in ordered],
        "values": [float(v) for _, v in ordered],
    }


def _sum_numeric(rows: list[dict[str, str]], value_col: str | None) -> Decimal:
    if not value_col:
        return Decimal("0")
    total = Decimal("0")
    for row in rows:
        total += _parse_number(row.get(value_col, "")) or Decimal("0")
    return total


def build_dashboard_payload(rows: list[dict[str, str]], schema: list[dict], filters: dict) -> dict:
    date_col = _pick_date_column(schema)
    value_col = _pick_numeric_column(schema)
    category_col = _pick_category_column(schema)

    filtered = filter_rows(
        rows,
        date_column=date_col,
        date_start=filters.get("date_start", ""),
        date_end=filters.get("date_end", ""),
        secretaria=filters.get("secretaria", ""),
        unidade=filters.get("unidade", ""),
        categoria=filters.get("categoria", ""),
    )

    line = _line_series(filtered, date_col, value_col)
    ranking = _ranking(filtered, category_col, value_col)
    soma = _sum_numeric(filtered, value_col)

    opts = {
        "secretaria": sorted({row.get("secretaria", "") for row in rows if row.get("secretaria", "")})[:100],
        "unidade": sorted({row.get("unidade", "") for row in rows if row.get("unidade", "")})[:100],
        "categoria": sorted({row.get("categoria", "") for row in rows if row.get("categoria", "")})[:100],
    }

    headers = [col.get("name") for col in schema]

    return {
        "rows": filtered,
        "headers": headers,
        "kpis": {
            "linhas_filtradas": len(filtered),
            "linhas_total": len(rows),
            "colunas": len(headers),
            "soma_principal": f"{soma:.2f}" if value_col else "-",
            "coluna_valor": value_col or "-",
        },
        "line": line,
        "ranking": ranking,
        "date_col": date_col,
        "value_col": value_col,
        "category_col": category_col,
        "filter_options": opts,
    }


def build_dataset_package(dataset, version, schema: list[dict], profile: dict) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if version.arquivo_original:
            with version.arquivo_original.open("rb") as fobj:
                zf.writestr(f"01_original/{version.arquivo_original.name.split('/')[-1]}", fobj.read())

        if version.arquivo_tratado:
            with version.arquivo_tratado.open("rb") as fobj:
                zf.writestr(f"02_tratado/{dataset.nome}_v{version.numero}.csv", fobj.read())

        zf.writestr(
            "03_dicionario/dicionario_dados.csv",
            data_dictionary_csv(schema),
        )
        zf.writestr(
            "03_dicionario/perfil.json",
            profile_json_bytes(profile),
        )

    return out.getvalue()
