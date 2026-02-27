from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from apps.core.services_auditoria import registrar_auditoria

from .models import ConversionJob


class ConversionError(RuntimeError):
    pass


def _command_exists(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _copy_field_file(field_file, dest: Path) -> Path:
    with field_file.open("rb") as src, open(dest, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return dest


def _collect_input_paths(job: ConversionJob, workdir: Path) -> list[Path]:
    files = []
    if job.input_file:
        files.append(job.input_file)
    files.extend(item.arquivo for item in job.inputs.order_by("ordem", "id"))

    paths: list[Path] = []
    for idx, fobj in enumerate(files, start=1):
        safe_name = os.path.basename(fobj.name) or f"arquivo_{idx}"
        path = workdir / f"in_{idx}_{safe_name}"
        paths.append(_copy_field_file(fobj, path))
    return paths


def _run_docx_to_pdf(input_paths: list[Path], workdir: Path) -> tuple[str, bytes, str]:
    if not input_paths:
        raise ConversionError("Nenhum arquivo DOCX informado.")

    binary = _command_exists("libreoffice", "soffice")
    if not binary:
        raise ConversionError("LibreOffice headless não encontrado no servidor.")

    input_path = input_paths[0]
    cmd = [binary, "--headless", "--convert-to", "pdf", "--outdir", str(workdir), str(input_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ConversionError((proc.stderr or proc.stdout or "Falha no LibreOffice").strip())

    out_file = workdir / f"{input_path.stem}.pdf"
    if not out_file.exists():
        raise ConversionError("Arquivo PDF não foi gerado pelo LibreOffice.")

    return out_file.name, out_file.read_bytes(), (proc.stdout or "Conversão DOCX concluída.").strip()


def _run_img_to_pdf(input_paths: list[Path], workdir: Path) -> tuple[str, bytes, str]:
    if not input_paths:
        raise ConversionError("Nenhuma imagem enviada para conversão.")

    images = []
    try:
        for path in input_paths:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)

        output = workdir / "imagens_convertidas.pdf"
        first, others = images[0], images[1:]
        first.save(output, "PDF", save_all=True, append_images=others)
        return output.name, output.read_bytes(), f"{len(images)} imagem(ns) convertida(s) para PDF."
    finally:
        for img in images:
            try:
                img.close()
            except Exception:
                pass


def _require_pypdf():
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception as exc:  # pragma: no cover
        raise ConversionError("Dependência 'pypdf' não instalada para operações de PDF.") from exc
    return PdfReader, PdfWriter


def _run_pdf_merge(input_paths: list[Path], workdir: Path) -> tuple[str, bytes, str]:
    if len(input_paths) < 2:
        raise ConversionError("Merge exige ao menos dois PDFs.")

    PdfReader, PdfWriter = _require_pypdf()
    writer = PdfWriter()
    total_pages = 0

    for path in input_paths:
        reader = PdfReader(str(path))
        total_pages += len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)

    output = workdir / "pdf_unificado.pdf"
    with open(output, "wb") as fobj:
        writer.write(fobj)

    return output.name, output.read_bytes(), f"{len(input_paths)} PDF(s) unificados ({total_pages} páginas)."


def _parse_pages_spec(spec: str, total_pages: int) -> list[int]:
    if not spec:
        return list(range(1, total_pages + 1))

    selected: set[int] = set()
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            start_raw, end_raw = [x.strip() for x in part.split("-", 1)]
            start = int(start_raw)
            end = int(end_raw)
            if start > end:
                start, end = end, start
            for page in range(start, end + 1):
                if 1 <= page <= total_pages:
                    selected.add(page)
        else:
            page = int(part)
            if 1 <= page <= total_pages:
                selected.add(page)

    if not selected:
        raise ConversionError("Faixa de páginas inválida para split.")

    return sorted(selected)


def _run_pdf_split(input_paths: list[Path], workdir: Path, pages_spec: str) -> tuple[str, bytes, str]:
    if not input_paths:
        raise ConversionError("Nenhum PDF enviado para separação.")

    PdfReader, PdfWriter = _require_pypdf()
    reader = PdfReader(str(input_paths[0]))
    pages = _parse_pages_spec(pages_spec, len(reader.pages))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for page_num in pages:
            writer = PdfWriter()
            writer.add_page(reader.pages[page_num - 1])
            single = io.BytesIO()
            writer.write(single)
            zf.writestr(f"pagina_{page_num:03d}.pdf", single.getvalue())

    return "pdf_split.zip", zip_buffer.getvalue(), f"Split concluído para {len(pages)} página(s)."


def _run_pdf_to_images(input_paths: list[Path], workdir: Path) -> tuple[str, bytes, str]:
    if not input_paths:
        raise ConversionError("Nenhum PDF enviado para conversão em imagem.")

    input_path = input_paths[0]
    out_prefix = workdir / "page"

    pdftoppm = _command_exists("pdftoppm")
    if not pdftoppm:
        raise ConversionError("Ferramenta 'pdftoppm' não está disponível no servidor.")

    cmd = [pdftoppm, "-png", str(input_path), str(out_prefix)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ConversionError((proc.stderr or proc.stdout or "Falha no pdftoppm").strip())

    files = sorted(workdir.glob("page-*.png"))
    if not files:
        raise ConversionError("Nenhuma imagem gerada a partir do PDF.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.writestr(file.name, file.read_bytes())

    return "pdf_imagens.zip", zip_buffer.getvalue(), f"{len(files)} imagem(ns) gerada(s)."


def process_conversion_job(job: ConversionJob) -> ConversionJob:
    started = time.monotonic()
    job.status = ConversionJob.Status.PROCESSANDO
    job.save(update_fields=["status", "atualizado_em"])

    try:
        with tempfile.TemporaryDirectory(prefix="gepub-conversor-") as tmp:
            workdir = Path(tmp)
            input_paths = _collect_input_paths(job, workdir)

            if not input_paths:
                raise ConversionError("Nenhum arquivo encontrado no job.")

            if job.tipo == ConversionJob.Tipo.DOCX_TO_PDF:
                out_name, out_bytes, logs = _run_docx_to_pdf(input_paths, workdir)
            elif job.tipo == ConversionJob.Tipo.IMG_TO_PDF:
                out_name, out_bytes, logs = _run_img_to_pdf(input_paths, workdir)
            elif job.tipo == ConversionJob.Tipo.PDF_MERGE:
                out_name, out_bytes, logs = _run_pdf_merge(input_paths, workdir)
            elif job.tipo == ConversionJob.Tipo.PDF_SPLIT:
                pages = str((job.parametros_json or {}).get("pages") or "").strip()
                out_name, out_bytes, logs = _run_pdf_split(input_paths, workdir, pages)
            elif job.tipo == ConversionJob.Tipo.PDF_TO_IMAGES:
                out_name, out_bytes, logs = _run_pdf_to_images(input_paths, workdir)
            else:
                raise ConversionError("Tipo de conversão não suportado.")

            duration = int((time.monotonic() - started) * 1000)
            job.output_file.save(out_name, ContentFile(out_bytes), save=False)
            job.status = ConversionJob.Status.CONCLUIDO
            job.logs = logs
            job.tamanho_saida = len(out_bytes)
            job.duracao_ms = duration
            job.concluido_em = timezone.now()
            job.save(
                update_fields=[
                    "output_file",
                    "status",
                    "logs",
                    "tamanho_saida",
                    "duracao_ms",
                    "concluido_em",
                    "atualizado_em",
                ]
            )

    except Exception as exc:
        duration = int((time.monotonic() - started) * 1000)
        job.status = ConversionJob.Status.ERRO
        job.logs = str(exc)
        job.duracao_ms = duration
        job.concluido_em = timezone.now()
        job.save(update_fields=["status", "logs", "duracao_ms", "concluido_em", "atualizado_em"])

    return job


def process_conversion_job_with_audit(job_id: int, *, actor_id: int | None = None, actor=None) -> ConversionJob:
    job = (
        ConversionJob.objects.select_related("municipio", "criado_por")
        .filter(pk=job_id)
        .first()
    )
    if not job:
        raise ValueError("Job de conversão não encontrado.")

    resolved_actor = actor
    if resolved_actor is None and actor_id:
        User = get_user_model()
        resolved_actor = User.objects.filter(pk=actor_id).first()
    if resolved_actor is None:
        resolved_actor = job.criado_por

    process_conversion_job(job)

    if job.status == ConversionJob.Status.CONCLUIDO:
        registrar_auditoria(
            municipio=job.municipio,
            modulo="CONVERSOR",
            evento="CONVERSAO_CONCLUIDA",
            entidade="ConversionJob",
            entidade_id=job.pk,
            usuario=resolved_actor,
            depois={
                "tipo": job.tipo,
                "duracao_ms": job.duracao_ms,
                "tamanho_saida": job.tamanho_saida,
            },
        )
    else:
        registrar_auditoria(
            municipio=job.municipio,
            modulo="CONVERSOR",
            evento="CONVERSAO_ERRO",
            entidade="ConversionJob",
            entidade_id=job.pk,
            usuario=resolved_actor,
            depois={"tipo": job.tipo, "erro": (job.logs or "")[:400]},
        )

    return job
