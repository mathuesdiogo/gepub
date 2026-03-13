#!/usr/bin/env python3
"""Intake de materiais de estudo para skills de apps do GEPUB.

Fluxo principal:
  1) Adicionar materiais (links, csv em lote, arquivo fisico)
  2) Auditar padrao e deduplicar automaticamente
  3) Gerar catalogo e backlog tecnico por app

Uso rapido:
  python3 scripts/gepub_materials.py init --all
  python3 scripts/gepub_materials.py add --app educacao --source https://... --objetivo "..."
  python3 scripts/gepub_materials.py add-links --app financeiro --links <url1> <url2>
  python3 scripts/gepub_materials.py add-file --app camara --file /caminho/ata.pdf
  python3 scripts/gepub_materials.py bulk --app saude --input /caminho/fontes.csv
  python3 scripts/gepub_materials.py build --app camara
  python3 scripts/gepub_materials.py build --all
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

CSV_HEADER = [
    "id",
    "tipo",
    "titulo",
    "url_ou_caminho",
    "tema",
    "objetivo_funcional",
    "prioridade",
    "status",
    "owner",
    "observacoes",
]

ALLOWED_TIPOS = {"video", "pdf", "pagina"}
ALLOWED_PRIORIDADES = {"alta", "media", "baixa"}
ALLOWED_STATUS = {"novo", "triado", "analisado", "backlog", "implementado"}
PRIORITY_ORDER = {"alta": 0, "media": 1, "baixa": 2}
STATUS_ORDER = {"novo": 0, "triado": 1, "analisado": 2, "backlog": 3, "implementado": 4}
TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "seq_no",
    "replytocom",
    "amp",
}


def list_app_names() -> list[str]:
    apps: list[str] = []
    for directory in sorted(SKILLS_DIR.glob("gepub-app-*")):
        name = directory.name.replace("gepub-app-", "", 1)
        if name:
            apps.append(name)
    return apps


def normalize_app(app: str) -> str:
    value = (app or "").strip().lower()
    if not value:
        raise ValueError("Informe --app")
    if value.startswith("gepub-app-"):
        value = value.replace("gepub-app-", "", 1)
    return value


def skill_dir_for_app(app: str) -> Path:
    d = SKILLS_DIR / f"gepub-app-{app}"
    if not d.exists():
        raise ValueError(f"Skill de app nao encontrada: {d}")
    return d


def refs_paths(app: str) -> dict[str, Path]:
    skill_dir = skill_dir_for_app(app)
    refs = skill_dir / "references"
    assets_dir = skill_dir / "assets" / "materiais"
    return {
        "skill": skill_dir,
        "refs": refs,
        "assets": assets_dir,
        "csv": refs / "fontes_estudo.csv",
        "bulk": refs / "fontes_estudo_bulk_template.csv",
        "catalog": refs / "conhecimento_catalogo.md",
        "backlog": refs / "conhecimento_backlog.md",
    }


def default_owner(app: str) -> str:
    return f"time-{app}"


def default_objetivo(app: str) -> str:
    return f"avaliar aplicacao do material no app {app}"


def is_default_objetivo(app: str, value: str) -> bool:
    return (value or "").strip().lower().startswith(default_objetivo(app))


def prefix_for_app(app: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]", "", app).upper()
    if not base:
        return "APP"
    if len(base) <= 4:
        return base
    return base[:4]


def valid_id_for_app(app: str, value: str) -> bool:
    prefix = prefix_for_app(app)
    return bool(re.fullmatch(rf"{re.escape(prefix)}-\d+", (value or "").strip()))


def generate_next_id(app: str, used_ids: set[str]) -> str:
    prefix = prefix_for_app(app)
    pattern = re.compile(rf"{re.escape(prefix)}-(\d+)$")
    highest = 0
    for item in used_ids:
        m = pattern.fullmatch(item)
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{prefix}-{highest + 1:03d}"


def ensure_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=CSV_HEADER)
            writer.writeheader()
        return

    with path.open("r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        fields = reader.fieldnames or []
    missing = [f for f in CSV_HEADER if f not in fields]
    if missing:
        raise ValueError(f"CSV invalido em {path}: faltam colunas {', '.join(missing)}")


def ensure_bulk_template(path: Path, app: str) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    owner = default_owner(app)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerow(
            {
                "id": "",
                "tipo": "video",
                "titulo": "",
                "url_ou_caminho": "https://youtube.com/watch?v=EXEMPLO",
                "tema": "geral",
                "objetivo_funcional": default_objetivo(app),
                "prioridade": "media",
                "status": "novo",
                "owner": owner,
                "observacoes": "",
            }
        )


def load_rows(path: Path) -> list[dict[str, str]]:
    ensure_csv(path)
    with path.open("r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        rows: list[dict[str, str]] = []
        for row in reader:
            clean = {k: (row.get(k) or "").strip() for k in CSV_HEADER}
            if any(clean.values()):
                rows.append(clean)
        return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_csv(path)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            clean = {k: (row.get(k) or "").strip() for k in CSV_HEADER}
            writer.writerow(clean)


def infer_tipo(source: str) -> str:
    value = source.strip().lower()
    if value.endswith(".pdf"):
        return "pdf"
    if value.endswith((".mp4", ".mov", ".mkv", ".avi", ".webm")):
        return "video"
    if any(host in value for host in ("youtube.com", "youtu.be", "vimeo.com")):
        return "video"
    return "pagina"


def infer_titulo(source: str) -> str:
    value = source.strip()
    low = value.lower()
    if "youtube.com/watch" in low:
        m = re.search(r"[?&]v=([^&]+)", value)
        if m:
            return f"Video Youtube {m.group(1)}"
        return "Video Youtube"
    if "youtu.be/" in low:
        slug = value.rstrip("/").split("/")[-1]
        return f"Video Youtube {slug}" if slug else "Video Youtube"

    cleaned = re.sub(r"[?#].*$", "", value)
    slug = cleaned.rstrip("/").split("/")[-1]
    if not slug:
        return "Material de referencia"
    slug = re.sub(r"\.[a-zA-Z0-9]{1,8}$", "", slug)
    slug = slug.replace("_", " ").replace("-", " ").strip()
    if not slug or slug.lower() in {"watch", "view", "index", "home"}:
        return "Material de referencia"
    return " ".join(w.capitalize() for w in slug.split())


def is_generic_title(value: str) -> bool:
    low = (value or "").strip().lower()
    return low in {"material de referencia", "video youtube", ""}


def normalize_source_key(source: str) -> str:
    value = (source or "").strip()
    if not value:
        return ""

    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        parsed = urlparse(value)
        query = []
        for key, val in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in TRACKING_QUERY_KEYS:
                continue
            query.append((key, val))
        query.sort()
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=parsed.path.rstrip("/"),
            query=urlencode(query),
            fragment="",
        )
        return urlunparse(normalized)

    path = Path(value).expanduser()
    if path.exists():
        try:
            return str(path.resolve()).lower()
        except Exception:
            pass
    return value.replace("\\", "/").lower()


def extract_sha256(obs: str) -> str:
    m = re.search(r"\bsha256=([0-9a-fA-F]{64})\b", obs or "")
    return m.group(1).lower() if m else ""


def merge_observacoes(current: str, incoming: str) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for raw in [current or "", incoming or ""]:
        for part in raw.split(";"):
            token = part.strip()
            if not token:
                continue
            if token.lower() in seen:
                continue
            seen.add(token.lower())
            merged.append(token)
    return "; ".join(merged)


def normalize_row(app: str, row: dict[str, str], used_ids: set[str]) -> dict[str, str] | None:
    source = (row.get("url_ou_caminho") or "").strip()
    if not source:
        return None

    row_id = (row.get("id") or "").strip()
    if not valid_id_for_app(app, row_id) or row_id in used_ids:
        row_id = generate_next_id(app, used_ids)

    tipo = (row.get("tipo") or "").strip().lower()
    if tipo not in ALLOWED_TIPOS:
        tipo = infer_tipo(source)

    prioridade = (row.get("prioridade") or "").strip().lower()
    if prioridade not in ALLOWED_PRIORIDADES:
        prioridade = "media"

    status = (row.get("status") or "").strip().lower()
    if status not in ALLOWED_STATUS:
        status = "novo"

    titulo = (row.get("titulo") or "").strip() or infer_titulo(source)
    tema = (row.get("tema") or "").strip() or "geral"
    objetivo = (row.get("objetivo_funcional") or "").strip() or default_objetivo(app)
    owner = (row.get("owner") or "").strip() or default_owner(app)
    obs = (row.get("observacoes") or "").strip()

    return {
        "id": row_id,
        "tipo": tipo,
        "titulo": titulo,
        "url_ou_caminho": source,
        "tema": tema,
        "objetivo_funcional": objetivo,
        "prioridade": prioridade,
        "status": status,
        "owner": owner,
        "observacoes": obs,
    }


def merge_rows(app: str, current: dict[str, str], incoming: dict[str, str]) -> tuple[dict[str, str], bool]:
    merged = dict(current)
    changed = False

    if is_generic_title(merged.get("titulo", "")) and incoming.get("titulo"):
        merged["titulo"] = incoming["titulo"]
        changed = True

    if (merged.get("tema") or "").strip().lower() == "geral" and (incoming.get("tema") or "").strip().lower() != "geral":
        merged["tema"] = incoming["tema"]
        changed = True

    if is_default_objetivo(app, merged.get("objetivo_funcional", "")) and not is_default_objetivo(app, incoming.get("objetivo_funcional", "")):
        merged["objetivo_funcional"] = incoming["objetivo_funcional"]
        changed = True

    if PRIORITY_ORDER.get(incoming.get("prioridade", "media"), 99) < PRIORITY_ORDER.get(merged.get("prioridade", "media"), 99):
        merged["prioridade"] = incoming["prioridade"]
        changed = True

    if STATUS_ORDER.get(incoming.get("status", "novo"), -1) > STATUS_ORDER.get(merged.get("status", "novo"), -1):
        merged["status"] = incoming["status"]
        changed = True

    default_owner_value = default_owner(app)
    if (merged.get("owner") or "").strip().lower() in {"", default_owner_value} and (incoming.get("owner") or "").strip().lower() not in {"", default_owner_value}:
        merged["owner"] = incoming["owner"]
        changed = True

    obs_merged = merge_observacoes(merged.get("observacoes", ""), incoming.get("observacoes", ""))
    if obs_merged != (merged.get("observacoes") or ""):
        merged["observacoes"] = obs_merged
        changed = True

    return merged, changed


def standardize_and_dedup(app: str, rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, int]]:
    used_ids: set[str] = set()
    by_source: dict[str, int] = {}
    standardized: list[dict[str, str]] = []
    stats = {
        "input": len(rows),
        "output": 0,
        "dedup_source": 0,
        "fixed": 0,
    }

    for raw in rows:
        normalized = normalize_row(app, raw, used_ids)
        if not normalized:
            continue

        key = normalize_source_key(normalized["url_ou_caminho"])
        idx = by_source.get(key)
        if idx is None:
            used_ids.add(normalized["id"])
            by_source[key] = len(standardized)
            standardized.append(normalized)
            if normalized != {k: (raw.get(k) or "").strip() for k in CSV_HEADER}:
                stats["fixed"] += 1
            continue

        merged, changed = merge_rows(app, standardized[idx], normalized)
        standardized[idx] = merged
        stats["dedup_source"] += 1
        if changed:
            stats["fixed"] += 1

    stats["output"] = len(standardized)
    return standardized, stats


def upsert_rows(app: str, csv_path: Path, incoming_rows: list[dict[str, str]]) -> dict[str, int]:
    existing_raw = load_rows(csv_path)
    existing, _ = standardize_and_dedup(app, existing_raw)

    used_ids = {row["id"] for row in existing}
    by_source = {normalize_source_key(row["url_ou_caminho"]): i for i, row in enumerate(existing)}
    by_hash: dict[str, int] = {}
    for idx, row in enumerate(existing):
        h = extract_sha256(row.get("observacoes", ""))
        if h:
            by_hash[h] = idx

    inserted = 0
    updated = 0

    for incoming_raw in incoming_rows:
        normalized = normalize_row(app, incoming_raw, used_ids)
        if not normalized:
            continue

        inc_hash = extract_sha256(normalized.get("observacoes", ""))
        idx = None
        if inc_hash and inc_hash in by_hash:
            idx = by_hash[inc_hash]
        else:
            idx = by_source.get(normalize_source_key(normalized["url_ou_caminho"]))

        if idx is not None:
            merged, changed = merge_rows(app, existing[idx], normalized)
            existing[idx] = merged
            if changed:
                updated += 1
            continue

        if normalized["id"] in used_ids:
            normalized["id"] = generate_next_id(app, used_ids)
        used_ids.add(normalized["id"])

        existing.append(normalized)
        source_key = normalize_source_key(normalized["url_ou_caminho"])
        by_source[source_key] = len(existing) - 1
        if inc_hash:
            by_hash[inc_hash] = len(existing) - 1
        inserted += 1

    final_rows, audit_stats = standardize_and_dedup(app, existing)
    write_rows(csv_path, final_rows)

    return {
        "inserted": inserted,
        "updated": updated,
        "dedup_source": audit_stats["dedup_source"],
        "total": len(final_rows),
    }


def init_app(app: str) -> None:
    paths = refs_paths(app)
    paths["refs"].mkdir(parents=True, exist_ok=True)
    ensure_csv(paths["csv"])
    ensure_bulk_template(paths["bulk"], app)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_physical_file(app: str, file_path: Path, obs: str = "") -> dict[str, str]:
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"Arquivo fisico nao encontrado: {file_path}")

    paths = refs_paths(app)
    paths["assets"].mkdir(parents=True, exist_ok=True)

    digest = sha256_file(file_path)
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", file_path.name)
    target_name = f"{digest[:8]}_{sanitized}"
    target = paths["assets"] / target_name
    if not target.exists():
        shutil.copy2(file_path, target)

    rel = str(target.relative_to(ROOT))
    extra_obs = f"sha256={digest}; origem={file_path}"
    merged_obs = merge_observacoes(obs, extra_obs)
    original_title = file_path.stem.replace("_", " ").replace("-", " ").strip()
    if original_title:
        original_title = " ".join(word.capitalize() for word in original_title.split())

    return {
        "id": "",
        "tipo": "",
        "titulo": original_title or "Material de referencia",
        "url_ou_caminho": rel,
        "tema": "geral",
        "objetivo_funcional": default_objetivo(app),
        "prioridade": "media",
        "status": "novo",
        "owner": default_owner(app),
        "observacoes": merged_obs,
    }


def build_catalog(app: str) -> tuple[Path, Path, int]:
    paths = refs_paths(app)
    rows = load_rows(paths["csv"])
    clean_rows, _ = standardize_and_dedup(app, rows)
    write_rows(paths["csv"], clean_rows)

    lines: list[str] = [
        f"# Catalogo de Conhecimento - {app}",
        "",
        f"Total de fontes: {len(clean_rows)}",
        "",
        "## Itens",
        "",
    ]
    for row in clean_rows:
        lines.append(f"### {row.get('id', '').strip()} - {row.get('titulo', '').strip()}")
        lines.append(f"- Tipo: {row.get('tipo', '').strip()}")
        lines.append(f"- Tema: {row.get('tema', '').strip()}")
        lines.append(f"- Objetivo funcional: {row.get('objetivo_funcional', '').strip()}")
        lines.append(f"- Prioridade: {row.get('prioridade', '').strip()}")
        lines.append(f"- Status: {row.get('status', '').strip()}")
        lines.append(f"- Owner: {row.get('owner', '').strip()}")
        lines.append(f"- Fonte: {row.get('url_ou_caminho', '').strip()}")
        obs = row.get("observacoes", "").strip()
        if obs:
            lines.append(f"- Observacoes: {obs}")
        lines.append("")
    paths["catalog"].write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    pending = [r for r in clean_rows if r.get("status") != "implementado"]
    pending.sort(key=lambda r: (PRIORITY_ORDER.get(r.get("prioridade", "media"), 99), r.get("id", "")))

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pending:
        groups[row.get("prioridade", "media")].append(row)

    backlog: list[str] = [
        f"# Backlog de Conhecimento - {app}",
        "",
        f"Total de itens (nao implementados): {len(pending)}",
        "",
    ]
    for p in ("alta", "media", "baixa"):
        if not groups.get(p):
            continue
        backlog.append(f"## Prioridade {p.upper()}")
        backlog.append("")
        for row in groups[p]:
            backlog.append(f"### {row.get('id', '').strip()} - {row.get('titulo', '').strip()}")
            backlog.append(f"- Tema: {row.get('tema', '').strip()}")
            backlog.append(f"- Fonte: {row.get('url_ou_caminho', '').strip()}")
            backlog.append(f"- Owner: {row.get('owner', '').strip()}")
            backlog.append(
                "- Story inicial: Como equipe do app, queremos "
                f"{row.get('objetivo_funcional', '').strip()}, para evoluir o tema {row.get('tema', '').strip() or 'geral'}."
            )
            backlog.append("- Criterios de aceite (base):")
            backlog.append("  - Fluxo funcional implementado no app alvo.")
            backlog.append("  - Permissoes e escopo municipal validados.")
            backlog.append("  - Testes minimos adicionados/atualizados.")
            backlog.append("")
    paths["backlog"].write_text("\n".join(backlog).rstrip() + "\n", encoding="utf-8")

    return paths["catalog"], paths["backlog"], len(clean_rows)


def cmd_init(args: argparse.Namespace) -> None:
    apps = list_app_names() if args.all else [normalize_app(args.app)]
    for app in apps:
        init_app(app)
        build_catalog(app)
        print(f"Inicializado: gepub-app-{app}")


def cmd_add(args: argparse.Namespace) -> None:
    app = normalize_app(args.app)
    init_app(app)
    paths = refs_paths(app)
    row = {
        "id": args.id,
        "tipo": args.tipo,
        "titulo": args.titulo,
        "url_ou_caminho": args.source,
        "tema": args.tema,
        "objetivo_funcional": args.objetivo.strip() or default_objetivo(app),
        "prioridade": args.prioridade,
        "status": args.status,
        "owner": args.owner,
        "observacoes": args.obs,
    }
    result = upsert_rows(app, paths["csv"], [row])
    print(f"{app}: +{result['inserted']} inseridos, {result['updated']} atualizados, total={result['total']}")


def cmd_add_links(args: argparse.Namespace) -> None:
    app = normalize_app(args.app)
    links = [item.strip() for item in args.links if item.strip()]
    if not links:
        raise SystemExit("Informe ao menos um link em --links")

    init_app(app)
    paths = refs_paths(app)

    incoming = []
    for source in links:
        incoming.append(
            {
                "id": "",
                "tipo": args.tipo,
                "titulo": "",
                "url_ou_caminho": source,
                "tema": args.tema,
                "objetivo_funcional": args.objetivo.strip() or default_objetivo(app),
                "prioridade": args.prioridade,
                "status": args.status,
                "owner": args.owner,
                "observacoes": args.obs,
            }
        )

    result = upsert_rows(app, paths["csv"], incoming)
    print(f"{app}: +{result['inserted']} inseridos, {result['updated']} atualizados, total={result['total']}")


def cmd_add_file(args: argparse.Namespace) -> None:
    app = normalize_app(args.app)
    init_app(app)
    paths = refs_paths(app)

    file_path = Path(args.file).expanduser().resolve()
    row = ingest_physical_file(app, file_path, args.obs)
    row["tema"] = args.tema
    row["objetivo_funcional"] = args.objetivo.strip() or default_objetivo(app)
    row["prioridade"] = args.prioridade
    row["status"] = args.status
    row["owner"] = args.owner
    row["tipo"] = args.tipo
    if args.titulo.strip():
        row["titulo"] = args.titulo.strip()

    result = upsert_rows(app, paths["csv"], [row])
    print(f"{app}: arquivo ingerido | +{result['inserted']} inseridos, {result['updated']} atualizados, total={result['total']}")


def cmd_bulk(args: argparse.Namespace) -> None:
    app = normalize_app(args.app)
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Arquivo de entrada nao encontrado: {src}")

    init_app(app)
    paths = refs_paths(app)

    incoming: list[dict[str, str]] = []
    with src.open("r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for raw in reader:
            source = (raw.get("url_ou_caminho") or "").strip()
            if not source:
                continue
            incoming.append(
                {
                    "id": (raw.get("id") or "").strip(),
                    "tipo": (raw.get("tipo") or "").strip(),
                    "titulo": (raw.get("titulo") or "").strip(),
                    "url_ou_caminho": source,
                    "tema": (raw.get("tema") or "geral").strip(),
                    "objetivo_funcional": (raw.get("objetivo_funcional") or default_objetivo(app)).strip(),
                    "prioridade": (raw.get("prioridade") or "media").strip(),
                    "status": (raw.get("status") or "novo").strip(),
                    "owner": (raw.get("owner") or default_owner(app)).strip(),
                    "observacoes": (raw.get("observacoes") or "").strip(),
                }
            )

    if not incoming:
        print("Nenhum material valido no CSV de entrada")
        return

    if args.dry_run:
        print(f"Simulacao {app}: {len(incoming)} materiais seriam processados")
        return

    result = upsert_rows(app, paths["csv"], incoming)
    print(f"{app}: +{result['inserted']} inseridos, {result['updated']} atualizados, total={result['total']}")


def cmd_audit(args: argparse.Namespace) -> None:
    apps = list_app_names() if args.all else [normalize_app(args.app)]
    for app in apps:
        init_app(app)
        paths = refs_paths(app)
        raw = load_rows(paths["csv"])
        clean, stats = standardize_and_dedup(app, raw)
        changed = raw != clean
        if changed and not args.dry_run:
            write_rows(paths["csv"], clean)
        status = "ALTERADO" if changed else "OK"
        if changed and args.dry_run:
            status = "ALTERARIA"
        print(
            f"{app}: {status} | entrada={stats['input']} saida={stats['output']} "
            f"dedup={stats['dedup_source']} ajustes={stats['fixed']}"
        )


def cmd_build(args: argparse.Namespace) -> None:
    apps = list_app_names() if args.all else [normalize_app(args.app)]
    for app in apps:
        init_app(app)
        catalog, backlog, total = build_catalog(app)
        print(f"{app}: {total} fontes | catalogo={catalog} | backlog={backlog}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gestao de materiais para skills de app")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Inicializar arquivos de conhecimento")
    p_init.add_argument("--app", default="", help="Nome do app (ex.: educacao)")
    p_init.add_argument("--all", action="store_true", help="Inicializar todos os apps")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Adicionar material por URL/caminho")
    p_add.add_argument("--app", required=True)
    p_add.add_argument("--source", required=True, help="URL ou caminho do material")
    p_add.add_argument("--objetivo", default="")
    p_add.add_argument("--tema", default="geral")
    p_add.add_argument("--prioridade", default="media")
    p_add.add_argument("--status", default="novo")
    p_add.add_argument("--owner", default="")
    p_add.add_argument("--obs", default="")
    p_add.add_argument("--tipo", default="")
    p_add.add_argument("--titulo", default="")
    p_add.add_argument("--id", default="")
    p_add.set_defaults(func=cmd_add)

    p_links = sub.add_parser("add-links", help="Adicionar varios links de uma vez")
    p_links.add_argument("--app", required=True)
    p_links.add_argument("--objetivo", default="")
    p_links.add_argument("--links", nargs="+", required=True)
    p_links.add_argument("--tema", default="geral")
    p_links.add_argument("--prioridade", default="media")
    p_links.add_argument("--status", default="novo")
    p_links.add_argument("--owner", default="")
    p_links.add_argument("--obs", default="")
    p_links.add_argument("--tipo", default="")
    p_links.set_defaults(func=cmd_add_links)

    p_file = sub.add_parser("add-file", help="Adicionar arquivo fisico")
    p_file.add_argument("--app", required=True)
    p_file.add_argument("--file", required=True, help="Caminho local do arquivo")
    p_file.add_argument("--objetivo", default="")
    p_file.add_argument("--tema", default="geral")
    p_file.add_argument("--prioridade", default="media")
    p_file.add_argument("--status", default="novo")
    p_file.add_argument("--owner", default="")
    p_file.add_argument("--obs", default="")
    p_file.add_argument("--tipo", default="")
    p_file.add_argument("--titulo", default="")
    p_file.set_defaults(func=cmd_add_file)

    p_bulk = sub.add_parser("bulk", help="Importar materiais via CSV")
    p_bulk.add_argument("--app", required=True)
    p_bulk.add_argument("--input", required=True)
    p_bulk.add_argument("--dry-run", action="store_true")
    p_bulk.set_defaults(func=cmd_bulk)

    p_audit = sub.add_parser("audit", help="Auditar/completar/deduplicar CSV existente")
    p_audit.add_argument("--app", default="", help="Nome do app")
    p_audit.add_argument("--all", action="store_true", help="Auditar todos os apps")
    p_audit.add_argument("--dry-run", action="store_true", help="Apenas simular ajustes")
    p_audit.set_defaults(func=cmd_audit)

    p_build = sub.add_parser("build", help="Gerar catalogo e backlog")
    p_build.add_argument("--app", default="", help="Nome do app")
    p_build.add_argument("--all", action="store_true", help="Gerar para todos apps")
    p_build.set_defaults(func=cmd_build)

    return p


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
