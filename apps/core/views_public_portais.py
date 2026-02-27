from __future__ import annotations

from datetime import date, timedelta

from django import forms
from django.contrib import messages
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.compras.models import ProcessoLicitatorio
from apps.contratos.models import ContratoAdministrativo
from apps.core.models import (
    CamaraMateria,
    CamaraSessao,
    ConcursoPublico,
    DiarioOficialEdicao,
    PortalBanner,
    PortalMenuPublico,
    PortalMunicipalConfig,
    PortalPaginaPublica,
    PortalTransparenciaArquivo,
    PortalNoticia,
)
from apps.core.portal_public_utils import build_menu_items, default_nav_urls
from apps.educacao.models import Curso, Matricula, Turma
from apps.educacao.models_calendario import CalendarioEducacionalEvento
from apps.org.models import Municipio, Unidade
from apps.ouvidoria.models import OuvidoriaCadastro
from apps.saude.models import DispensacaoSaude, EspecialidadeSaude, ProfissionalSaude


class OuvidoriaPublicForm(forms.Form):
    tipo = forms.ChoiceField(choices=OuvidoriaCadastro.Tipo.choices)
    assunto = forms.CharField(max_length=180)
    descricao = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
    solicitante_nome = forms.CharField(max_length=160)
    solicitante_email = forms.EmailField(required=False)
    solicitante_telefone = forms.CharField(max_length=40, required=False)
    prioridade = forms.ChoiceField(choices=OuvidoriaCadastro.Prioridade.choices)


def _resolve_public_municipio(request):
    if getattr(request, "tenant_lookup_failed", False):
        return None
    return getattr(request, "current_municipio", None)


def _fallback_public_context(municipio: Municipio):
    return {
        "titulo_portal": f"Portal de {municipio.nome}",
        "subtitulo_portal": "Gestão pública integrada e transparente",
        "mensagem_boas_vindas": "",
        "cor_primaria": "#0E4A7E",
        "cor_secundaria": "#2F6EA9",
        "logo_url": "",
        "brasao_url": "",
        "endereco": "",
        "telefone": "",
        "email": "",
        "horario_atendimento": "",
    }


def _portal_context(request, municipio: Municipio):
    cfg = PortalMunicipalConfig.objects.filter(municipio=municipio).first()
    data = _fallback_public_context(municipio)
    if cfg:
        data.update(
            {
                "titulo_portal": cfg.titulo_portal or data["titulo_portal"],
                "subtitulo_portal": cfg.subtitulo_portal or data["subtitulo_portal"],
                "mensagem_boas_vindas": cfg.mensagem_boas_vindas or "",
                "cor_primaria": cfg.cor_primaria or data["cor_primaria"],
                "cor_secundaria": cfg.cor_secundaria or data["cor_secundaria"],
                "logo_url": cfg.logo.url if cfg.logo else "",
                "brasao_url": cfg.brasao.url if cfg.brasao else "",
                "endereco": cfg.endereco or "",
                "telefone": cfg.telefone or "",
                "email": cfg.email or "",
                "horario_atendimento": cfg.horario_atendimento or "",
            }
        )
    nav_urls = default_nav_urls()
    data.update(
        {
            "municipio": municipio,
            "cta_login": getattr(request, "public_login_url", reverse("accounts:login")),
            "nav_urls": nav_urls,
            "menu_items_header": build_menu_items(municipio, posicao=PortalMenuPublico.Posicao.HEADER),
            "menu_items_footer": build_menu_items(municipio, posicao=PortalMenuPublico.Posicao.FOOTER),
            "paginas_publicas": PortalPaginaPublica.objects.filter(municipio=municipio, publicado=True).order_by("ordem", "id"),
        }
    )
    return data


def _tenant_not_found_response(request):
    return render(
        request,
        "core/tenant_not_found.html",
        {
            "slug": getattr(request, "current_municipio_slug", ""),
            "cta_home": reverse("core:institucional_public"),
            "cta_login": getattr(request, "public_login_url", reverse("accounts:login")),
        },
        status=404,
    )


def _ensure_municipio_or_response(request):
    if getattr(request, "tenant_lookup_failed", False):
        return None, _tenant_not_found_response(request)
    municipio = _resolve_public_municipio(request)
    if not municipio:
        return None, redirect("core:institucional_public")
    return municipio, None


def portal_noticias_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    q = (request.GET.get("q") or "").strip()
    categoria = (request.GET.get("categoria") or "").strip()
    qs = PortalNoticia.objects.filter(municipio=municipio, publicado=True)
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(resumo__icontains=q) | Q(conteudo__icontains=q))
    if categoria:
        qs = qs.filter(categoria=categoria)
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Notícias • {municipio.nome}",
            "items": qs.order_by("-publicado_em", "-id"),
            "q": q,
            "categoria": categoria,
            "categorias": PortalNoticia.Categoria.choices,
            "banners": PortalBanner.objects.filter(municipio=municipio, ativo=True).order_by("ordem", "-id")[:6],
        }
    )
    return render(request, "core/public/portal_noticias_list.html", ctx)


def portal_noticia_detail_public(request, slug: str):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    noticia = get_object_or_404(PortalNoticia, municipio=municipio, publicado=True, slug=slug)
    relacionados = (
        PortalNoticia.objects.filter(municipio=municipio, publicado=True)
        .exclude(pk=noticia.pk)
        .order_by("-publicado_em", "-id")[:6]
    )
    ctx = _portal_context(request, municipio)
    ctx.update({"title": noticia.titulo, "item": noticia, "relacionados": relacionados})
    return render(request, "core/public/portal_noticia_detail.html", ctx)


def portal_pagina_public(request, slug: str):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    pagina = get_object_or_404(PortalPaginaPublica, municipio=municipio, publicado=True, slug=slug)
    ctx = _portal_context(request, municipio)
    ctx.update({"title": pagina.titulo, "item": pagina})
    return render(request, "core/public/portal_pagina.html", ctx)


def _gerar_protocolo_ouvidoria(municipio: Municipio) -> str:
    date_prefix = timezone.localdate().strftime("%Y%m%d")
    base = f"OUV-{municipio.id}-{date_prefix}"
    seq = (
        OuvidoriaCadastro.objects.filter(municipio=municipio, protocolo__startswith=base)
        .count()
        + 1
    )
    return f"{base}-{seq:04d}"


def portal_ouvidoria_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response

    form = OuvidoriaPublicForm(request.POST or None)
    protocolo_busca = (request.GET.get("protocolo") or "").strip()
    acompanhamento = None

    if protocolo_busca:
        acompanhamento = (
            OuvidoriaCadastro.objects.filter(municipio=municipio, protocolo__iexact=protocolo_busca)
            .prefetch_related("respostas")
            .first()
        )

    if request.method == "POST" and form.is_valid():
        prazo = timezone.localdate() + timedelta(days=20)
        chamado = OuvidoriaCadastro.objects.create(
            municipio=municipio,
            protocolo=_gerar_protocolo_ouvidoria(municipio),
            assunto=form.cleaned_data["assunto"],
            tipo=form.cleaned_data["tipo"],
            prioridade=form.cleaned_data["prioridade"],
            descricao=form.cleaned_data["descricao"],
            solicitante_nome=form.cleaned_data["solicitante_nome"],
            solicitante_email=form.cleaned_data["solicitante_email"],
            solicitante_telefone=form.cleaned_data["solicitante_telefone"],
            status=OuvidoriaCadastro.Status.ABERTO,
            prazo_resposta=prazo,
        )
        messages.success(request, f"Solicitação registrada com protocolo {chamado.protocolo}.")
        return redirect(reverse("core:portal_ouvidoria_public") + f"?protocolo={chamado.protocolo}")

    respostas_publicas = []
    if acompanhamento:
        respostas_publicas = list(acompanhamento.respostas.filter(publico=True).order_by("criado_em"))

    recentes = OuvidoriaCadastro.objects.filter(municipio=municipio).order_by("-criado_em", "-id")[:8]
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"e-SIC e Ouvidoria • {municipio.nome}",
            "form": form,
            "acompanhamento": acompanhamento,
            "respostas_publicas": respostas_publicas,
            "protocolo_busca": protocolo_busca,
            "recentes": recentes,
        }
    )
    return render(request, "core/public/portal_ouvidoria.html", ctx)


def portal_licitacoes_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    q = (request.GET.get("q") or "").strip()
    modalidade = (request.GET.get("modalidade") or "").strip()
    status = (request.GET.get("status") or "").strip()
    base_qs = ProcessoLicitatorio.objects.filter(municipio=municipio)
    qs = base_qs
    if q:
        qs = qs.filter(Q(numero_processo__icontains=q) | Q(objeto__icontains=q) | Q(vencedor_nome__icontains=q))
    if modalidade:
        qs = qs.filter(modalidade=modalidade)
    if status:
        qs = qs.filter(status=status)
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Licitações • {municipio.nome}",
            "items": qs.order_by("-data_abertura", "-id"),
            "indicadores": {
                "total": base_qs.count(),
                "em_curso": base_qs.filter(status=ProcessoLicitatorio.Status.EM_CURSO).count(),
                "homologado": base_qs.filter(status=ProcessoLicitatorio.Status.HOMOLOGADO).count(),
                "fracassado": base_qs.filter(status=ProcessoLicitatorio.Status.FRACASSADO).count(),
            },
            "q": q,
            "modalidade": modalidade,
            "status": status,
            "modalidades": ProcessoLicitatorio.Modalidade.choices,
            "status_choices": ProcessoLicitatorio.Status.choices,
        }
    )
    return render(request, "core/public/portal_licitacoes.html", ctx)


def portal_contratos_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    base_qs = ContratoAdministrativo.objects.filter(municipio=municipio).prefetch_related("aditivos", "medicoes")
    qs = base_qs
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(objeto__icontains=q) | Q(fornecedor_nome__icontains=q))
    if status:
        qs = qs.filter(status=status)
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Contratos • {municipio.nome}",
            "items": qs.order_by("-vigencia_inicio", "-id"),
            "indicadores": {
                "total": base_qs.count(),
                "ativos": base_qs.filter(status=ContratoAdministrativo.Status.ATIVO).count(),
                "encerrados": base_qs.filter(status=ContratoAdministrativo.Status.ENCERRADO).count(),
                "valor_total": base_qs.aggregate(total=models.Sum("valor_total")).get("total"),
            },
            "q": q,
            "status": status,
            "status_choices": ContratoAdministrativo.Status.choices,
        }
    )
    return render(request, "core/public/portal_contratos.html", ctx)


def portal_diario_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()
    mes = (request.GET.get("mes") or "").strip()
    inicio_raw = (request.GET.get("inicio") or "").strip()
    fim_raw = (request.GET.get("fim") or "").strip()

    qs_base = DiarioOficialEdicao.objects.filter(municipio=municipio, publicado=True)
    qs = qs_base

    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(resumo__icontains=q))
    ano_int = int(ano) if ano.isdigit() else None
    if ano_int:
        qs = qs.filter(data_publicacao__year=ano_int)

    mes_int = int(mes) if mes.isdigit() else None
    if mes_int and 1 <= mes_int <= 12:
        qs = qs.filter(data_publicacao__month=mes_int)
        mes = f"{mes_int:02d}"
    else:
        mes = ""

    inicio = None
    fim = None
    try:
        if inicio_raw:
            inicio = date.fromisoformat(inicio_raw)
    except ValueError:
        inicio = None
        inicio_raw = ""
    try:
        if fim_raw:
            fim = date.fromisoformat(fim_raw)
    except ValueError:
        fim = None
        fim_raw = ""

    if inicio:
        qs = qs.filter(data_publicacao__gte=inicio)
    if fim:
        qs = qs.filter(data_publicacao__lte=fim)

    anos = list(
        qs_base.dates("data_publicacao", "year", order="DESC")
    )
    meses = [
        ("01", "Janeiro"),
        ("02", "Fevereiro"),
        ("03", "Março"),
        ("04", "Abril"),
        ("05", "Maio"),
        ("06", "Junho"),
        ("07", "Julho"),
        ("08", "Agosto"),
        ("09", "Setembro"),
        ("10", "Outubro"),
        ("11", "Novembro"),
        ("12", "Dezembro"),
    ]

    edicao_atual = qs_base.order_by("-data_publicacao", "-id").first()
    total_edicoes = qs_base.count()
    total_com_pdf = qs_base.filter(arquivo_pdf__isnull=False).exclude(arquivo_pdf="").count()
    total_sem_pdf = max(total_edicoes - total_com_pdf, 0)
    primeira_edicao = qs_base.order_by("data_publicacao", "id").first()

    items = qs.order_by("-data_publicacao", "-id")
    edicoes_anteriores = items
    if edicao_atual:
        edicoes_anteriores = edicoes_anteriores.exclude(pk=edicao_atual.pk)

    filtros_ativos = bool(q or ano_int or mes or inicio_raw or fim_raw)

    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Diário Oficial • {municipio.nome}",
            "edicao_atual": edicao_atual,
            "items": items,
            "edicoes_anteriores": edicoes_anteriores,
            "total_edicoes": total_edicoes,
            "total_com_pdf": total_com_pdf,
            "total_sem_pdf": total_sem_pdf,
            "primeira_edicao": primeira_edicao,
            "ultima_edicao": edicao_atual,
            "total_filtrado": items.count(),
            "filtros_ativos": filtros_ativos,
            "q": q,
            "ano": ano,
            "mes": mes,
            "inicio": inicio_raw,
            "fim": fim_raw,
            "anos": anos,
            "meses": meses,
        }
    )
    return render(request, "core/public/portal_diario.html", ctx)


def portal_concursos_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = ConcursoPublico.objects.filter(municipio=municipio, publicado=True).prefetch_related("etapas")
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(descricao__icontains=q))
    if status:
        qs = qs.filter(status=status)
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Concursos • {municipio.nome}",
            "items": qs.order_by("-criado_em", "-id"),
            "q": q,
            "status": status,
            "status_choices": ConcursoPublico.Status.choices,
        }
    )
    return render(request, "core/public/portal_concursos.html", ctx)


def portal_camara_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    tipo = (request.GET.get("tipo") or "").strip()
    status = (request.GET.get("status") or "").strip()
    materias = CamaraMateria.objects.filter(municipio=municipio, publicado=True)
    if tipo:
        materias = materias.filter(tipo=tipo)
    if status:
        materias = materias.filter(status=status)
    sessoes = CamaraSessao.objects.filter(municipio=municipio, publicado=True).order_by("-data_sessao", "-id")
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Câmara • {municipio.nome}",
            "materias": materias.order_by("-data_publicacao", "-id"),
            "sessoes": sessoes[:40],
            "tipo": tipo,
            "status": status,
            "tipos": CamaraMateria.Tipo.choices,
            "status_choices": CamaraMateria.Status.choices,
        }
    )
    return render(request, "core/public/portal_camara.html", ctx)


def portal_saude_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    unidades = Unidade.objects.filter(
        secretaria__municipio=municipio,
        tipo=Unidade.Tipo.SAUDE,
        ativo=True,
    ).order_by("nome")
    profissionais = ProfissionalSaude.objects.filter(unidade__secretaria__municipio=municipio, ativo=True)
    especialidades = EspecialidadeSaude.objects.filter(ativo=True).order_by("nome")
    noticias = PortalNoticia.objects.filter(
        municipio=municipio,
        publicado=True,
        categoria=PortalNoticia.Categoria.SAUDE,
    ).order_by("-publicado_em", "-id")[:6]
    arquivos_medicamentos = PortalTransparenciaArquivo.objects.filter(
        municipio=municipio,
        publico=True,
        categoria=PortalTransparenciaArquivo.Categoria.MEDICAMENTOS,
    ).order_by("ordem", "-publicado_em", "-id")[:20]
    dispensacoes = DispensacaoSaude.objects.filter(unidade__secretaria__municipio=municipio)
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Portal da Saúde • {municipio.nome}",
            "unidades": unidades,
            "noticias": noticias,
            "arquivos_medicamentos": arquivos_medicamentos,
            "indicadores": {
                "unidades": unidades.count(),
                "profissionais": profissionais.count(),
                "especialidades": especialidades.count(),
                "dispensacoes": dispensacoes.count(),
            },
        }
    )
    return render(request, "core/public/portal_saude.html", ctx)


def portal_educacao_public(request):
    municipio, response = _ensure_municipio_or_response(request)
    if response:
        return response
    unidades = Unidade.objects.filter(
        secretaria__municipio=municipio,
        tipo=Unidade.Tipo.EDUCACAO,
        ativo=True,
    ).order_by("nome")
    turmas = Turma.objects.filter(unidade__secretaria__municipio=municipio, ativo=True)
    cursos_qs = Curso.objects.filter(turmas__in=turmas, ativo=True).distinct().order_by("nome")
    cursos = cursos_qs[:50]
    eventos = CalendarioEducacionalEvento.objects.filter(
        secretaria__municipio=municipio,
        ativo=True,
        data_inicio__gte=timezone.localdate(),
    ).order_by("data_inicio", "id")[:20]
    noticias = PortalNoticia.objects.filter(
        municipio=municipio,
        publicado=True,
        categoria=PortalNoticia.Categoria.EDUCACAO,
    ).order_by("-publicado_em", "-id")[:6]
    matriculas_qs = Matricula.objects.filter(turma__unidade__secretaria__municipio=municipio)
    arquivos_educacao = PortalTransparenciaArquivo.objects.filter(
        municipio=municipio,
        publico=True,
        categoria__in=[
            PortalTransparenciaArquivo.Categoria.EDUCACAO_MATRICULAS,
            PortalTransparenciaArquivo.Categoria.EDUCACAO_ESPERA_CRECHE,
            PortalTransparenciaArquivo.Categoria.EDUCACAO_LISTA_ALUNOS,
        ],
    ).order_by("categoria", "ordem", "-publicado_em", "-id")[:30]
    ctx = _portal_context(request, municipio)
    ctx.update(
        {
            "title": f"Portal da Educação • {municipio.nome}",
            "unidades": unidades,
            "cursos": cursos,
            "eventos": eventos,
            "noticias": noticias,
            "arquivos_educacao": arquivos_educacao,
            "indicadores": {
                "unidades": unidades.count(),
                "turmas": turmas.count(),
                "cursos": cursos_qs.count(),
                "matriculas": matriculas_qs.count(),
            },
        }
    )
    return render(request, "core/public/portal_educacao.html", ctx)
