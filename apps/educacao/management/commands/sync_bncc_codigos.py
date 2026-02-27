from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.educacao.models_notas import BNCCCodigo


CODE_PATTERN = re.compile(r"\b(EI\d{2}[A-Z]{2}\d{2}|EF\d{2}[A-Z]{2}\d{2}|EM\d{2}[A-Z]{3}\d{3})\b")


def _derive_metadata(code: str) -> dict:
    if code.startswith("EI"):
        return {
            "modalidade": BNCCCodigo.Modalidade.EDUCACAO_INFANTIL,
            "etapa": BNCCCodigo.Etapa.EDUCACAO_INFANTIL,
            "grupo_codigo": code[2:4],
            "area_codigo": code[4:6],
            "ano_inicial": None,
            "ano_final": None,
        }
    if code.startswith("EF"):
        ano = int(code[2:4])
        return {
            "modalidade": BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL,
            "etapa": (
                BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS
                if ano <= 5
                else BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_FINAIS
            ),
            "grupo_codigo": "",
            "area_codigo": code[4:6],
            "ano_inicial": ano,
            "ano_final": ano,
        }
    return {
        "modalidade": BNCCCodigo.Modalidade.ENSINO_MEDIO,
        "etapa": BNCCCodigo.Etapa.ENSINO_MEDIO,
        "grupo_codigo": code[2:4],
        "area_codigo": code[4:7],
        "ano_inicial": None,
        "ano_final": None,
    }


class Command(BaseCommand):
    help = "Sincroniza códigos BNCC no banco a partir do JSON oficial (ou texto extraído)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            dest="json_path",
            default="apps/educacao/data/bncc_codigos_oficiais.json",
            help="Caminho para JSON com códigos BNCC.",
        )
        parser.add_argument(
            "--txt",
            dest="txt_path",
            default="",
            help="Opcional: caminho para texto bruto para extração dos códigos via regex.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Desativa códigos que não estiverem na origem informada.",
        )

    def handle(self, *args, **options):
        txt_path = (options.get("txt_path") or "").strip()
        if txt_path:
            payload = self._load_from_text(Path(txt_path))
        else:
            json_path = Path(options["json_path"])
            payload = self._load_from_json(json_path)

        if not payload:
            raise CommandError("Nenhum código BNCC encontrado para importar.")

        seen_codes = set()
        created = 0
        updated = 0
        for row in payload:
            codigo = (row.get("codigo") or "").strip().upper()
            if not codigo:
                continue
            meta = _derive_metadata(codigo)
            defaults = {
                "descricao": (row.get("descricao") or "").strip(),
                "modalidade": row.get("modalidade") or meta["modalidade"],
                "etapa": row.get("etapa") or meta["etapa"],
                "grupo_codigo": row.get("grupo_codigo") or meta["grupo_codigo"],
                "area_codigo": (row.get("area_codigo") or meta["area_codigo"] or "").upper(),
                "ano_inicial": row.get("ano_inicial", meta["ano_inicial"]),
                "ano_final": row.get("ano_final", meta["ano_final"]),
                "fonte_url": row.get("fonte_url")
                or "https://basenacionalcomum.mec.gov.br/images/BNCC_EI_EF_110518_versaofinal_site.pdf",
                "ativo": True,
            }
            obj, was_created = BNCCCodigo.objects.update_or_create(codigo=codigo, defaults=defaults)
            seen_codes.add(obj.codigo)
            if was_created:
                created += 1
            else:
                updated += 1

        disabled = 0
        if options.get("replace"):
            disabled = BNCCCodigo.objects.exclude(codigo__in=seen_codes).update(ativo=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"BNCC sincronizado com sucesso. Criados={created}, atualizados={updated}, desativados={disabled}."
            )
        )

    def _load_from_json(self, path: Path) -> list[dict]:
        if not path.exists():
            raise CommandError(f"Arquivo JSON não encontrado: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON inválido em {path}: {exc}") from exc
        if not isinstance(data, list):
            raise CommandError("JSON deve ser uma lista de objetos.")
        return data

    def _load_from_text(self, path: Path) -> list[dict]:
        if not path.exists():
            raise CommandError(f"Arquivo texto não encontrado: {path}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        descriptions = {}
        for line in lines:
            for match in CODE_PATTERN.finditer(line):
                code = match.group(1)
                tail = line[match.end() :].strip(" )\t:-")
                tail = re.sub(r"^[\W_]+", "", tail)
                if code not in descriptions:
                    descriptions[code] = tail
                elif not descriptions[code] and tail:
                    descriptions[code] = tail

        payload = []
        for code in sorted(descriptions):
            meta = _derive_metadata(code)
            payload.append(
                {
                    "codigo": code,
                    "descricao": descriptions[code][:300],
                    "modalidade": meta["modalidade"],
                    "etapa": meta["etapa"],
                    "grupo_codigo": meta["grupo_codigo"],
                    "area_codigo": meta["area_codigo"],
                    "ano_inicial": meta["ano_inicial"],
                    "ano_final": meta["ano_final"],
                }
            )
        return payload
