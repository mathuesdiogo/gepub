from __future__ import annotations

from dataclasses import dataclass
import os

from django.core.management.base import BaseCommand

from apps.accounts.models import Profile
from apps.core.security import derive_cpf_security_fields, mask_cpf, resolve_cpf_digits
from apps.educacao.models import Aluno
from apps.saude.models import AtendimentoSaude, ProfissionalSaude


@dataclass
class BackfillStats:
    scanned: int = 0
    changed: int = 0
    skipped: int = 0


class Command(BaseCommand):
    help = "Preenche campos de segurança de CPF (enc/hash/last4) a partir dos campos legados."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Só calcula, sem persistir.")
        parser.add_argument(
            "--redact-legacy",
            action="store_true",
            help="Mascara campo legado de CPF (ex.: ***.***.***-12) após preencher campos seguros.",
        )
        parser.add_argument("--batch-size", type=int, default=500, help="Tamanho do lote para bulk_update.")

    def _backfill_model(
        self,
        *,
        qs,
        raw_field: str,
        enc_field: str,
        hash_field: str,
        last4_field: str,
        batch_size: int,
        dry_run: bool,
        redact_legacy: bool,
    ) -> BackfillStats:
        stats = BackfillStats()
        pending = []

        for obj in qs.iterator(chunk_size=batch_size):
            stats.scanned += 1
            raw_val = getattr(obj, raw_field, "")
            enc_val = getattr(obj, enc_field, "")
            hash_val = getattr(obj, hash_field, "")
            last4_val = getattr(obj, last4_field, "")

            digits = resolve_cpf_digits(raw_val, enc_val)
            enc_new, hash_new, last4_new = derive_cpf_security_fields(digits)

            # Não apaga dados já protegidos quando as chaves de ambiente não
            # estão configuradas (enc/hash novos vazios).
            final_enc = enc_val if (digits and not enc_new and enc_val) else enc_new
            final_hash = hash_val if (digits and not hash_new and hash_val) else hash_new
            final_raw = mask_cpf(digits) if redact_legacy else raw_val

            if (
                (enc_val or "") == final_enc
                and (hash_val or "") == final_hash
                and (last4_val or "") == last4_new
                and (raw_val or "") == (final_raw or "")
            ):
                stats.skipped += 1
                continue

            setattr(obj, enc_field, final_enc)
            setattr(obj, hash_field, final_hash)
            setattr(obj, last4_field, last4_new)
            setattr(obj, raw_field, final_raw)
            pending.append(obj)
            stats.changed += 1

            if not dry_run and len(pending) >= batch_size:
                obj.__class__.objects.bulk_update(
                    pending,
                    [raw_field, enc_field, hash_field, last4_field],
                    batch_size=batch_size,
                )
                pending = []

        if not dry_run and pending:
            pending[0].__class__.objects.bulk_update(
                pending,
                [raw_field, enc_field, hash_field, last4_field],
                batch_size=batch_size,
            )

        return stats

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        batch_size = int(options["batch_size"] or 500)
        redact_legacy = bool(options["redact_legacy"])

        if not os.getenv("DJANGO_CPF_HASH_KEY"):
            self.stdout.write(
                self.style.WARNING("DJANGO_CPF_HASH_KEY não definida: cpf_hash não será preenchido nesta execução.")
            )
        if not os.getenv("DJANGO_CPF_ENCRYPTION_KEY"):
            self.stdout.write(
                self.style.WARNING("DJANGO_CPF_ENCRYPTION_KEY não definida: cpf_enc não será preenchido nesta execução.")
            )

        self.stdout.write(
            self.style.WARNING(
                f"Backfill CPF security iniciado (dry_run={dry_run}, batch_size={batch_size})"
            )
        )

        jobs = [
            ("accounts.Profile", Profile.objects.all(), "cpf", "cpf_enc", "cpf_hash", "cpf_last4"),
            ("educacao.Aluno", Aluno.objects.all(), "cpf", "cpf_enc", "cpf_hash", "cpf_last4"),
            ("saude.ProfissionalSaude", ProfissionalSaude.objects.all(), "cpf", "cpf_enc", "cpf_hash", "cpf_last4"),
            (
                "saude.AtendimentoSaude",
                AtendimentoSaude.objects.all(),
                "paciente_cpf",
                "paciente_cpf_enc",
                "paciente_cpf_hash",
                "paciente_cpf_last4",
            ),
        ]

        total_scanned = 0
        total_changed = 0
        total_skipped = 0

        for label, qs, raw_field, enc_field, hash_field, last4_field in jobs:
            stats = self._backfill_model(
                qs=qs,
                raw_field=raw_field,
                enc_field=enc_field,
                hash_field=hash_field,
                last4_field=last4_field,
                batch_size=batch_size,
                dry_run=dry_run,
                redact_legacy=redact_legacy,
            )
            total_scanned += stats.scanned
            total_changed += stats.changed
            total_skipped += stats.skipped
            self.stdout.write(
                f"{label}: scanned={stats.scanned} changed={stats.changed} skipped={stats.skipped}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído: scanned={total_scanned} changed={total_changed} skipped={total_skipped}"
            )
        )
