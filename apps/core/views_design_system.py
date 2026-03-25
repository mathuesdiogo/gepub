from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .design_system import GEPUB_DS_VERSION, resolve_admin_theme_context

THEME_TOKEN_PRESETS = {
    "kassya": {
        "--gp-primary": "#2670e8",
        "--gp-primary-hover": "#1a56b8",
        "--gp-secondary": "#05152e",
        "--gp-background": "#eaf1ff",
        "--gp-surface": "#ffffff",
    },
    "inclusao": {
        "--gp-primary": "#111111",
        "--gp-primary-hover": "#000000",
        "--gp-secondary": "#111111",
        "--gp-background": "#ffffff",
        "--gp-surface": "#ffffff",
    },
    "institucional": {
        "--gp-primary": "#a1431f",
        "--gp-primary-hover": "#7f3218",
        "--gp-secondary": "#2f2a27",
        "--gp-background": "#faf5ef",
        "--gp-surface": "#ffffff",
    },
}

WEB_STANDARDS_RULES = [
    "Utilizar 4 espaços ao invés de tabs.",
    "Não utilizar o atributo style em tags HTML (preferir classes utilitárias/componentes do DS).",
    "Não utilizar tags obsoletas/deprecadas no HTML5, como center e font.",
    "Toda página deve possuir apenas uma tag h1, representando o título principal da página.",
]

SEMANTIC_HTML_TAGS = [
    {
        "tag": "a",
        "descricao": "Links de navegação e ações contextuais.",
        "usar_em": "Quando o usuário navega para outra URL.",
        "exemplo": "Consulte as informações solicitadas pelo servidor.",
        "codigo": '<a href="#">Consulte as informações solicitadas pelo servidor</a>',
    },
    {
        "tag": "strong",
        "descricao": "Destaque de importância semântica.",
        "usar_em": "Termos críticos no texto.",
        "exemplo": "O servidor não forneceu as informações solicitadas.",
        "codigo": 'O <strong>servidor</strong> não forneceu as informações solicitadas.',
    },
    {
        "tag": "em",
        "descricao": "Ênfase na leitura do conteúdo.",
        "usar_em": "Trechos que exigem entonação específica.",
        "exemplo": "O servidor não forneceu as informações solicitadas.",
        "codigo": 'O servidor <em>não</em> forneceu as informações solicitadas.',
    },
    {
        "tag": "ul/ol/li",
        "descricao": "Listas não ordenadas e ordenadas.",
        "usar_em": "Coleções de itens relacionados.",
        "exemplo": "1. Um, 2. Dois, 3. Três",
        "codigo": "<ol><li>Um</li><li>Dois</li><li>Três</li></ol>",
    },
    {
        "tag": "small",
        "descricao": "Informação lateral/auxiliar.",
        "usar_em": "Metadados, observações e datas.",
        "exemplo": "Informações solicitadas em 15/07/2014.",
        "codigo": "Informações solicitadas <small>em 15/07/2014</small>.",
    },
]

NOMENCLATURE_GUIDELINES = [
    "Manter títulos e labels com a primeira inicial maiúscula, exceto nomes próprios.",
    "Pontuar corretamente mensagens direcionadas ao usuário.",
]

NOMENCLATURE_RECOMMENDATIONS = [
    {"recomendado": "Adicionar", "nao_recomendado": "Cadastrar"},
    {"recomendado": "Editar", "nao_recomendado": "Atualizar, Alterar"},
    {"recomendado": "Remover", "nao_recomendado": "Excluir, Apagar, Deletar"},
    {"recomendado": "Visualizar", "nao_recomendado": "Ver, Abrir"},
]

TEMPLATE_FILTER_SPECS = [
    {
        "nome": "format",
        "descricao": "Formata a variável se for data ou usuário.",
        "codigo": "{{ variavel|format }}",
    },
    {
        "nome": "status",
        "descricao": "Envolve o valor com span e aplica classe baseada em slugify.",
        "codigo": "{{ variavel|status }}",
    },
    {
        "nome": "text_small",
        "descricao": "Envolve o valor na tag small para comentários/metadados.",
        "codigo": "{{ variavel|text_small }}",
    },
]

TEMPLATE_TAG_SPECS = [
    {
        "nome": "render_form",
        "descricao": "Renderiza formulário Django com estrutura padrão de campos (<code>form.as_p</code>).",
        "codigo": "{% render_form form %}",
    },
    {
        "nome": "icon",
        "descricao": "Renderiza ícone de ação (visualizar, editar, remover) com parâmetros opcionais de título, classe extra e confirmação.",
        "codigo": '{% icon "view" "#" "Visualizar" "extra_class" "Confirma a ação?" %}',
    },
    {
        "nome": "icone",
        "descricao": "Converte nome em ícone Font Awesome.",
        "codigo": '{% icone "user" %}',
    },
]


@login_required
def design_system_docs(request):
    theme_ctx = resolve_admin_theme_context(request)
    return render(
        request,
        "core/design_system/index.html",
        {
            "docs_page": "index",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "theme_tokens_preview": THEME_TOKEN_PRESETS,
            "ds_version": GEPUB_DS_VERSION,
            "theme_ctx": theme_ctx,
            "web_standards_rules": WEB_STANDARDS_RULES,
            "semantic_html_tags": SEMANTIC_HTML_TAGS,
            "nomenclature_guidelines": NOMENCLATURE_GUIDELINES,
            "nomenclature_recommendations": NOMENCLATURE_RECOMMENDATIONS,
            "template_filter_specs": TEMPLATE_FILTER_SPECS,
            "template_tag_specs": TEMPLATE_TAG_SPECS,
        },
    )


@login_required
def design_system_components(request):
    return render(
        request,
        "core/design_system/components.html",
        {
            "docs_page": "components",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "ds_version": GEPUB_DS_VERSION,
        },
    )


@login_required
def design_system_themes(request):
    return render(
        request,
        "core/design_system/themes.html",
        {
            "docs_page": "themes",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "theme_tokens_preview": THEME_TOKEN_PRESETS,
            "ds_version": GEPUB_DS_VERSION,
        },
    )


@login_required
def design_system_tokens_api(request):
    theme_ctx = resolve_admin_theme_context(request)
    base = dict(THEME_TOKEN_PRESETS.get(theme_ctx.theme, {}))
    merged = {**base, **theme_ctx.token_overrides}
    return JsonResponse(
        {
            "version": theme_ctx.version,
            "theme": theme_ctx.theme,
            "tokens": merged,
            "tenant_overrides": theme_ctx.token_overrides,
            "themes": THEME_TOKEN_PRESETS,
        }
    )


@login_required
def frontend_lab(request):
    return render(
        request,
        "core/design_system/frontend_lab.html",
        {
            "docs_page": "frontend-lab",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "ds_version": GEPUB_DS_VERSION,
        },
    )
