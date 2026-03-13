from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value).replace("%", "").replace(",", ".").strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _parse_any_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raw = str(value or "").strip()
    if not raw:
        return None
    return parse_datetime(raw) or parse_date(raw)


@register.filter(name="gp_currency")
def gp_currency(value):
    amount = _to_decimal(value).quantize(Decimal("0.01"))
    formatted = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


@register.filter(name="gp_format_date")
def gp_format_date(value, fmt="%d/%m/%Y"):
    parsed = _parse_any_date(value)
    if not parsed:
        return ""
    if isinstance(parsed, datetime):
        return parsed.strftime(fmt)
    return datetime.combine(parsed, datetime.min.time()).strftime(fmt)


@register.filter(name="gp_format_document")
def gp_format_document(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    if len(digits) in {10, 11}:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    return str(value or "")


@register.filter(name="gp_status_color")
def gp_status_color(value):
    key = str(value or "").strip().lower()
    mapping = {
        "ativo": "success",
        "ok": "success",
        "concluido": "success",
        "pendente": "warning",
        "atrasado": "warning",
        "erro": "danger",
        "bloqueado": "danger",
        "cancelado": "danger",
        "info": "info",
    }
    return mapping.get(key, "neutral")


@register.filter(name="gp_truncate")
def gp_truncate(value, size=80):
    try:
        max_len = int(size)
    except Exception:
        max_len = 80
    text = str(value or "")
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 1)] + "…"


@register.filter(name="gp_percentage")
def gp_percentage(value, decimals=2):
    amount = _to_decimal(value)
    try:
        d = max(0, int(decimals))
    except Exception:
        d = 2
    return f"{amount:.{d}f}%".replace(".", ",")


@register.simple_tag(name="gp_button")
def gp_button(label, url="#", variant="primary", icon="", attrs=""):
    icon_html = format_html('<i class="{}" aria-hidden="true"></i>', icon) if icon else ""
    return format_html(
        '<a href="{}" class="gp-button gp-button--{}" {}>{} {}</a>',
        url,
        escape(variant),
        mark_safe(attrs or ""),
        icon_html,
        escape(label),
    )


@register.simple_tag(name="gp_card")
def gp_card(title="", body="", footer=""):
    footer_html = format_html('<div class="gp-card__footer">{}</div>', mark_safe(footer)) if footer else ""
    return format_html(
        '<article class="gp-card"><header class="gp-card__header"><h3>{}</h3></header><div class="gp-card__body">{}</div>{}</article>',
        escape(title),
        mark_safe(body),
        footer_html,
    )


@register.simple_tag(name="gp_alert")
def gp_alert(message, variant="info", dismissible=True):
    close_btn = ''
    if dismissible:
        close_btn = '<button type="button" class="alert__close" aria-label="Fechar">&times;</button>'
    return format_html(
        '<div class="gp-alert gp-alert--{} {}">{} {}</div>',
        escape(variant),
        "gp-alert--dismissible" if dismissible else "",
        escape(message),
        mark_safe(close_btn),
    )


@register.simple_tag(name="gp_table")
def gp_table(headers=None, rows=None, striped=True, hover=True, sortable=False):
    headers = headers or []
    rows = rows or []
    classes = ["gp-table", "gp-table--responsive"]
    if striped:
        classes.append("gp-table--striped")
    if hover:
        classes.append("gp-table--hover")
    if sortable:
        classes.append("gp-table--sortable")

    head_html = format_html_join("", "<th>{}</th>", ((escape(h),) for h in headers))
    row_html = []
    for row in rows:
        cols = format_html_join("", "<td>{}</td>", ((mark_safe(c),) for c in row))
        row_html.append(format_html("<tr>{}</tr>", cols))

    return format_html(
        '<div class="{}"><table><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>',
        " ".join(classes),
        head_html,
        mark_safe("".join(str(item) for item in row_html)),
    )


@register.simple_tag(name="gp_badge")
def gp_badge(text, variant="neutral"):
    return format_html('<span class="gp-badge gp-badge--{}">{}</span>', escape(variant), escape(text))


@register.simple_tag(name="gp_progress")
def gp_progress(value=0, max_value=100, indeterminate=False):
    if indeterminate:
        return format_html('<div class="gp-progress gp-progress--indeterminate"><span class="gp-progress__value"></span></div>')
    current = _to_decimal(value)
    max_dec = _to_decimal(max_value)
    pct = Decimal("0") if max_dec <= 0 else (current / max_dec) * Decimal("100")
    pct = max(Decimal("0"), min(Decimal("100"), pct))
    return format_html(
        '<div class="gp-progress" style="--gp-progress:{}%;"><span class="gp-progress__value"></span></div>',
        str(pct.quantize(Decimal("0.01"))),
    )


@register.simple_tag(name="gp_chart")
def gp_chart(chart_id, chart_type="line", title=""):
    cls = f"gp-chart-{escape(chart_type)}"
    return format_html(
        '<section class="{}" id="{}" role="img" aria-label="{}"><h4>{}</h4><div class="gp-chart__canvas"></div></section>',
        cls,
        escape(chart_id),
        escape(title or "Gráfico"),
        escape(title or "Gráfico"),
    )


@register.simple_tag(name="gp_form")
def gp_form(action="#", method="post", content=""):
    return format_html('<form action="{}" method="{}" class="gp-form">{}</form>', action, method, mark_safe(content))


@register.simple_tag(name="gp_modal")
def gp_modal(modal_id, title="", content=""):
    return format_html(
        '<div id="{}" class="gp-modal" role="dialog" aria-modal="true" aria-labelledby="{}-title" hidden>'
        '<div class="gp-modal__dialog">'
        '<header class="gp-modal__header"><h3 id="{}-title">{}</h3></header>'
        '<div class="gp-modal__body">{}</div>'
        '</div></div>',
        escape(modal_id),
        escape(modal_id),
        escape(modal_id),
        escape(title),
        mark_safe(content),
    )
