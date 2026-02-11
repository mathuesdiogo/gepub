import base64
import csv
import hashlib
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

from weasyprint import HTML


def export_csv(filename: str, headers: list[str], rows: list[list[str]]):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    # BOM para Excel abrir UTF-8 certo
    response.write("\ufeff")
    w = csv.writer(response, delimiter=";")
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return response


def _make_report_hash(title: str, headers: list[str], rows: list[list[str]], user_str: str, dt_str: str) -> str:
    # Hash curto e estável o suficiente para identificar o relatório impresso
    raw = f"{title}|{user_str}|{dt_str}|{headers}|{rows}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16].upper()


def _try_make_qr_data_uri(text: str) -> str | None:
    """
    Gera QR Code como data URI (PNG base64).
    Se a lib `qrcode` não estiver instalada, retorna None.
    """
    try:
        import qrcode  # type: ignore
    except Exception:
        return None

    img = qrcode.make(text)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def export_pdf_table(
    request,
    *,
    filename: str,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    subtitle: str = "",
    filtros: str = "",
):
    """
    PDF institucional (modelo padrão) via WeasyPrint (UTF-8),
    com:
      - Cabeçalho azul (logo + título centralizado)
      - Metadados: gerado em, usuário que imprimiu
      - Filtros
      - Tabela redesenhada
      - Rodapé com marca + paginação real (Página X de Y)
      - Hash do relatório e QR Code (se disponível)
    Template: templates/core/relatorios/pdf/table.html
    """
    from django.templatetags.static import static

    printed_at = timezone.localtime()
    printed_at_str = printed_at.strftime("%d/%m/%Y %H:%M")
    printed_by = getattr(request.user, "username", "—")

    report_hash = _make_report_hash(title, headers, rows, printed_by, printed_at_str)
    qr_text = f"GEPUB|{title}|{printed_at_str}|{printed_by}|{report_hash}"
    qr_data_uri = _try_make_qr_data_uri(qr_text)

    context = {
        "title": title,
        "subtitle": subtitle,
        "filtros": filtros,
        "printed_at": printed_at_str,
        "printed_by": printed_by,
        "headers": headers,
        "rows": rows,
        "report_hash": report_hash,
        "qr_data_uri": qr_data_uri,
        # Se você trocar a logo no static depois, não precisa mexer aqui
        "logo_url": request.build_absolute_uri(static("img/logo_prefeitura.png")),
    }

    html = render_to_string("core/relatorios/pdf/table.html", context, request=request)

    # base_url é fundamental pro WeasyPrint resolver assets (logo/css/etc.)
    pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp["X-Content-Type-Options"] = "nosniff"
    return resp
