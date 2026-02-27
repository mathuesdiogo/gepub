from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    PortalBanner,
    PortalHomeBloco,
    PortalMenuPublico,
    PortalMunicipalConfig,
    PortalPaginaPublica,
    PortalNoticia,
)


@dataclass(slots=True)
class PortalSeedResult:
    config_created: bool
    banners_created: int
    noticias_created: int
    paginas_created: int
    menus_created: int
    blocos_created: int

    @property
    def created_total(self) -> int:
        return (
            int(self.config_created)
            + self.banners_created
            + self.noticias_created
            + self.paginas_created
            + self.menus_created
            + self.blocos_created
        )


def _config_defaults(municipio) -> dict:
    return {
        "titulo_portal": f"Portal da Prefeitura de {municipio.nome}",
        "subtitulo_portal": "Serviços públicos, transparência e atendimento ao cidadão",
        "mensagem_boas_vindas": (
            "Bem-vindo ao portal oficial. Aqui você acompanha notícias, documentos públicos, "
            "licitações, contratos e canais de atendimento."
        ),
        "cor_primaria": "#0E4A7E",
        "cor_secundaria": "#2F6EA9",
        "endereco": municipio.endereco_prefeitura or "",
        "telefone": municipio.telefone_prefeitura or "",
        "email": municipio.email_prefeitura or "",
        "horario_atendimento": "Segunda a sexta, 08h às 14h",
    }


def _banner_defaults() -> list[dict]:
    return [
        {
            "titulo": "Portal da Transparência",
            "subtitulo": "Receitas, despesas, empenhos e pagamentos atualizados",
            "link": "/transparencia/",
            "ordem": 1,
            "ativo": True,
        },
        {
            "titulo": "e-SIC e Ouvidoria",
            "subtitulo": "Abra solicitações e acompanhe por protocolo",
            "link": "/esic-ouvidoria/",
            "ordem": 2,
            "ativo": True,
        },
        {
            "titulo": "Licitações e Contratos",
            "subtitulo": "Acesso público aos processos de compras e contratos",
            "link": "/licitacoes/",
            "ordem": 3,
            "ativo": True,
        },
    ]


def _noticia_defaults(municipio) -> list[dict]:
    return [
        {
            "slug": "bem-vindo-ao-portal",
            "titulo": f"{municipio.nome}: portal municipal no ar",
            "resumo": "A prefeitura passa a concentrar publicações e serviços em um único ambiente.",
            "conteudo": (
                "Este portal reúne informações institucionais, transparência, atendimento ao cidadão e "
                "publicações oficiais do município."
            ),
            "categoria": PortalNoticia.Categoria.PREFEITURA,
            "destaque": True,
        },
        {
            "slug": "transparencia-publica-ativa",
            "titulo": "Transparência pública ativa no município",
            "resumo": "Acompanhe licitações, contratos, despesas e demais eventos públicos.",
            "conteudo": (
                "A área de transparência foi configurada para oferecer consulta com filtros por período, "
                "fornecedor e secretaria."
            ),
            "categoria": PortalNoticia.Categoria.TRANSPARENCIA,
            "destaque": True,
        },
        {
            "slug": "atendimento-esic-ouvidoria",
            "titulo": "Canal e-SIC e Ouvidoria disponível para o cidadão",
            "resumo": "Solicitações, denúncias, reclamações e sugestões com número de protocolo.",
            "conteudo": (
                "Os atendimentos podem ser registrados online com acompanhamento de status e histórico de respostas."
            ),
            "categoria": PortalNoticia.Categoria.OUVIDORIA,
            "destaque": False,
        },
        {
            "slug": "subportais-saude-e-educacao",
            "titulo": "Subportais de Saúde e Educação habilitados",
            "resumo": "Unidades, agenda de eventos e notícias setoriais no portal municipal.",
            "conteudo": (
                "As secretarias podem publicar comunicados próprios e manter informações públicas atualizadas "
                "por área finalística."
            ),
            "categoria": PortalNoticia.Categoria.GERAL,
            "destaque": False,
        },
    ]


def _pagina_defaults() -> list[dict]:
    return [
        {
            "slug": "a-prefeitura",
            "titulo": "A Prefeitura",
            "resumo": "Conheça a gestão municipal, estrutura e responsabilidades institucionais.",
            "conteudo": (
                "Esta página apresenta a estrutura da prefeitura, secretarias e canais oficiais de atendimento."
            ),
            "mostrar_no_menu": True,
            "mostrar_no_rodape": True,
            "ordem": 10,
            "publicado": True,
        },
        {
            "slug": "servicos-ao-cidadao",
            "titulo": "Serviços ao Cidadão",
            "resumo": "Acesse orientações e serviços públicos municipais.",
            "conteudo": (
                "Aqui você encontra links rápidos para protocolos, ouvidoria, transparência e serviços digitais."
            ),
            "mostrar_no_menu": True,
            "mostrar_no_rodape": True,
            "ordem": 20,
            "publicado": True,
        },
        {
            "slug": "contato-oficial",
            "titulo": "Contato Oficial",
            "resumo": "Canais oficiais para atendimento institucional.",
            "conteudo": (
                "Utilize os canais oficiais da prefeitura para informações, solicitações e acompanhamento de processos."
            ),
            "mostrar_no_menu": True,
            "mostrar_no_rodape": True,
            "ordem": 30,
            "publicado": True,
        },
    ]


def _home_bloco_defaults() -> list[dict]:
    return [
        {
            "titulo": "Portal da Transparência",
            "descricao": "Consulte receitas, despesas, empenhos e pagamentos publicados.",
            "icone": "fa-solid fa-chart-column",
            "link": "/transparencia/",
            "ordem": 1,
            "ativo": True,
        },
        {
            "titulo": "e-SIC e Ouvidoria",
            "descricao": "Abra solicitações e acompanhe protocolo público.",
            "icone": "fa-solid fa-comments",
            "link": "/esic-ouvidoria/",
            "ordem": 2,
            "ativo": True,
        },
        {
            "titulo": "Licitações e Contratos",
            "descricao": "Publicações oficiais de compras, contratos e aditivos.",
            "icone": "fa-solid fa-file-contract",
            "link": "/licitacoes/",
            "ordem": 3,
            "ativo": True,
        },
        {
            "titulo": "Subportais de Saúde e Educação",
            "descricao": "Acompanhe unidades, notícias e informações por secretaria.",
            "icone": "fa-solid fa-building-columns",
            "link": "/educacao-publica/",
            "ordem": 4,
            "ativo": True,
        },
    ]


def _menu_defaults() -> list[dict]:
    return [
        {
            "titulo": "Início",
            "posicao": PortalMenuPublico.Posicao.HEADER,
            "tipo_destino": PortalMenuPublico.TipoDestino.INTERNO,
            "rota_interna": PortalMenuPublico.RotaInterna.HOME,
            "ordem": 1,
        },
        {
            "titulo": "Notícias",
            "posicao": PortalMenuPublico.Posicao.HEADER,
            "tipo_destino": PortalMenuPublico.TipoDestino.INTERNO,
            "rota_interna": PortalMenuPublico.RotaInterna.NOTICIAS,
            "ordem": 2,
        },
        {
            "titulo": "Licitações",
            "posicao": PortalMenuPublico.Posicao.HEADER,
            "tipo_destino": PortalMenuPublico.TipoDestino.INTERNO,
            "rota_interna": PortalMenuPublico.RotaInterna.LICITACOES,
            "ordem": 3,
        },
        {
            "titulo": "Contratos",
            "posicao": PortalMenuPublico.Posicao.HEADER,
            "tipo_destino": PortalMenuPublico.TipoDestino.INTERNO,
            "rota_interna": PortalMenuPublico.RotaInterna.CONTRATOS,
            "ordem": 4,
        },
        {
            "titulo": "Transparência",
            "posicao": PortalMenuPublico.Posicao.HEADER,
            "tipo_destino": PortalMenuPublico.TipoDestino.INTERNO,
            "rota_interna": PortalMenuPublico.RotaInterna.TRANSPARENCIA,
            "ordem": 5,
        },
        {
            "titulo": "e-SIC/Ouvidoria",
            "posicao": PortalMenuPublico.Posicao.HEADER,
            "tipo_destino": PortalMenuPublico.TipoDestino.INTERNO,
            "rota_interna": PortalMenuPublico.RotaInterna.OUVIDORIA,
            "ordem": 6,
        },
        {
            "titulo": "A Prefeitura",
            "posicao": PortalMenuPublico.Posicao.FOOTER,
            "tipo_destino": PortalMenuPublico.TipoDestino.PAGINA,
            "pagina_slug": "a-prefeitura",
            "ordem": 10,
        },
        {
            "titulo": "Serviços",
            "posicao": PortalMenuPublico.Posicao.FOOTER,
            "tipo_destino": PortalMenuPublico.TipoDestino.PAGINA,
            "pagina_slug": "servicos-ao-cidadao",
            "ordem": 20,
        },
        {
            "titulo": "Contato",
            "posicao": PortalMenuPublico.Posicao.FOOTER,
            "tipo_destino": PortalMenuPublico.TipoDestino.PAGINA,
            "pagina_slug": "contato-oficial",
            "ordem": 30,
        },
    ]


def ensure_portal_seed_for_municipio(municipio, *, autor=None, force: bool = False) -> PortalSeedResult:
    if municipio is None:
        return PortalSeedResult(
            config_created=False,
            banners_created=0,
            noticias_created=0,
            paginas_created=0,
            menus_created=0,
            blocos_created=0,
        )

    banners_created = 0
    noticias_created = 0
    paginas_created = 0
    menus_created = 0
    blocos_created = 0
    with transaction.atomic():
        config, config_created = PortalMunicipalConfig.objects.get_or_create(
            municipio=municipio,
            defaults=_config_defaults(municipio),
        )
        if not config_created:
            update_fields: list[str] = []
            defaults = _config_defaults(municipio)
            for field in ("titulo_portal", "subtitulo_portal", "mensagem_boas_vindas", "cor_primaria", "cor_secundaria"):
                current = getattr(config, field, "")
                if force and current != defaults[field]:
                    setattr(config, field, defaults[field])
                    update_fields.append(field)

            # Só preenche contato se vier vazio (não sobrescreve edição manual).
            for field in ("endereco", "telefone", "email", "horario_atendimento"):
                current = (getattr(config, field, "") or "").strip()
                if not current and defaults.get(field):
                    setattr(config, field, defaults[field])
                    update_fields.append(field)

            if update_fields:
                update_fields.append("atualizado_em")
                config.save(update_fields=sorted(set(update_fields)))

        for item in _banner_defaults():
            lookup = {"municipio": municipio, "titulo": item["titulo"]}
            if force:
                _, created = PortalBanner.objects.update_or_create(defaults=item, **lookup)
                banners_created += int(created)
                continue
            if PortalBanner.objects.filter(**lookup).exists():
                continue
            PortalBanner.objects.create(municipio=municipio, **item)
            banners_created += 1

        now = timezone.now()
        for item in _noticia_defaults(municipio):
            slug = item["slug"]
            defaults = {
                "titulo": item["titulo"],
                "resumo": item["resumo"],
                "conteudo": item["conteudo"],
                "categoria": item["categoria"],
                "destaque": item["destaque"],
                "publicado": True,
                "publicado_em": now,
                "autor": autor,
            }
            lookup = {"municipio": municipio, "slug": slug}
            if force:
                _, created = PortalNoticia.objects.update_or_create(defaults=defaults, **lookup)
                noticias_created += int(created)
                continue
            if PortalNoticia.objects.filter(**lookup).exists():
                continue
            PortalNoticia.objects.create(**lookup, **defaults)
            noticias_created += 1

        for item in _pagina_defaults():
            slug = item["slug"]
            defaults = {
                "titulo": item["titulo"],
                "resumo": item["resumo"],
                "conteudo": item["conteudo"],
                "mostrar_no_menu": item["mostrar_no_menu"],
                "mostrar_no_rodape": item["mostrar_no_rodape"],
                "ordem": item["ordem"],
                "publicado": item["publicado"],
                "criado_por": autor,
            }
            lookup = {"municipio": municipio, "slug": slug}
            if force:
                _, created = PortalPaginaPublica.objects.update_or_create(defaults=defaults, **lookup)
                paginas_created += int(created)
                continue
            if PortalPaginaPublica.objects.filter(**lookup).exists():
                continue
            PortalPaginaPublica.objects.create(**lookup, **defaults)
            paginas_created += 1

        page_by_slug = {
            p.slug: p
            for p in PortalPaginaPublica.objects.filter(
                municipio=municipio,
                slug__in=[m.get("pagina_slug") for m in _menu_defaults() if m.get("pagina_slug")],
            )
        }
        for item in _menu_defaults():
            defaults = {
                "tipo_destino": item["tipo_destino"],
                "rota_interna": item.get("rota_interna", ""),
                "pagina": page_by_slug.get(item.get("pagina_slug")),
                "url_externa": item.get("url_externa", ""),
                "abrir_em_nova_aba": bool(item.get("abrir_em_nova_aba", False)),
                "ordem": item["ordem"],
                "ativo": True,
            }
            lookup = {"municipio": municipio, "titulo": item["titulo"], "posicao": item["posicao"]}
            if force:
                _, created = PortalMenuPublico.objects.update_or_create(defaults=defaults, **lookup)
                menus_created += int(created)
                continue
            if PortalMenuPublico.objects.filter(**lookup).exists():
                continue
            PortalMenuPublico.objects.create(**lookup, **defaults)
            menus_created += 1

        for item in _home_bloco_defaults():
            lookup = {"municipio": municipio, "titulo": item["titulo"]}
            if force:
                _, created = PortalHomeBloco.objects.update_or_create(defaults=item, **lookup)
                blocos_created += int(created)
                continue
            if PortalHomeBloco.objects.filter(**lookup).exists():
                continue
            PortalHomeBloco.objects.create(municipio=municipio, **item)
            blocos_created += 1

    return PortalSeedResult(
        config_created=config_created,
        banners_created=banners_created,
        noticias_created=noticias_created,
        paginas_created=paginas_created,
        menus_created=menus_created,
        blocos_created=blocos_created,
    )
