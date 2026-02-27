from django import template
from django.utils.html import format_html

register = template.Library()

@register.simple_tag
def autocomplete_attrs(url, href=None, min_chars=2, max_items=5):
    """
    Retorna atributos HTML padronizados pro autocomplete institucional GEPUB.
    - url: endpoint JSON {results:[{id,text,meta?}]}
    - href: (opcional) link de navegação ao clicar numa sugestão (com {q})
    """
    parts = [
        format_html('data-autocomplete-url="{}"', url),
        format_html('data-autocomplete-min="{}"', int(min_chars)),
        format_html('data-autocomplete-max="{}"', int(max_items)),
    ]
    if href:
        parts.append(format_html('data-autocomplete-href="{}"', href))
    return format_html(" ".join([str(p) for p in parts]))