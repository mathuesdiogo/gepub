from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.core.services_auditoria import registrar_auditoria
from apps.educacao.models import Matricula
from apps.educacao.models_diario import Avaliacao as AvaliacaoDiario
from apps.educacao.models_diario import DiarioTurma, Nota

from .forms import option_letters
from .models import AplicacaoAvaliacao, AvaliacaoProva, FolhaResposta, GabaritoProva, QuestaoProva


def normalize_respostas(respostas: dict | None, *, qtd_questoes: int, opcoes: int) -> dict[str, str]:
    letras = set(option_letters(opcoes))
    normalized: dict[str, str] = {}
    for idx in range(1, max(1, int(qtd_questoes or 1)) + 1):
        val = ""
        if respostas:
            raw = respostas.get(str(idx), respostas.get(idx, ""))
            val = str(raw or "").strip().upper()
        if val in letras:
            normalized[str(idx)] = val
    return normalized


def versoes_da_avaliacao(avaliacao: AvaliacaoProva) -> list[str]:
    if avaliacao.tem_versoes:
        return [GabaritoProva.Versao.A, GabaritoProva.Versao.B]
    return [GabaritoProva.Versao.A]


def resolve_scope_from_turma(avaliacao: AvaliacaoProva) -> dict[str, Any]:
    unidade = getattr(avaliacao.turma, "unidade", None)
    secretaria = getattr(unidade, "secretaria", None) if unidade else None
    municipio = getattr(secretaria, "municipio", None) if secretaria else None
    return {
        "municipio": municipio,
        "secretaria": secretaria,
        "unidade": unidade,
    }


def ensure_gabaritos_basicos(avaliacao: AvaliacaoProva, *, actor=None) -> list[GabaritoProva]:
    created: list[GabaritoProva] = []
    for versao in versoes_da_avaliacao(avaliacao):
        gabarito, was_created = GabaritoProva.objects.get_or_create(
            avaliacao=avaliacao,
            versao=versao,
            defaults={"respostas": {}, "atualizado_por": actor},
        )
        if was_created:
            created.append(gabarito)
    return created


def gabarito_para_versao(avaliacao: AvaliacaoProva, versao: str) -> GabaritoProva | None:
    item = (
        GabaritoProva.objects.filter(avaliacao=avaliacao, versao=(versao or "").upper()).order_by("id").first()
    )
    if item:
        return item
    return GabaritoProva.objects.filter(avaliacao=avaliacao, versao=GabaritoProva.Versao.A).order_by("id").first()


@transaction.atomic
def ensure_aplicacoes_da_avaliacao(avaliacao: AvaliacaoProva, *, actor=None) -> dict[str, int]:
    matriculas = (
        Matricula.objects.select_related("aluno")
        .filter(turma=avaliacao.turma, situacao=Matricula.Situacao.ATIVA)
        .order_by("aluno__nome", "id")
    )

    versions = versoes_da_avaliacao(avaliacao)
    created = 0
    updated = 0
    total = 0

    for idx, matricula in enumerate(matriculas):
        total += 1
        versao = versions[idx % len(versions)]

        aplicacao, was_created = AplicacaoAvaliacao.objects.get_or_create(
            avaliacao=avaliacao,
            aluno=matricula.aluno,
            defaults={
                "matricula": matricula,
                "versao": versao,
                "status": AplicacaoAvaliacao.Status.GERADA,
            },
        )

        changed = False
        if aplicacao.matricula_id != matricula.id:
            aplicacao.matricula = matricula
            changed = True
        if aplicacao.versao != versao:
            aplicacao.versao = versao
            changed = True
        if changed:
            aplicacao.save(update_fields=["matricula", "versao"])
            updated += 1

        folha, folha_created = FolhaResposta.objects.get_or_create(
            aplicacao=aplicacao,
            defaults={"versao": versao, "respostas_marcadas": {}},
        )
        if folha.versao != versao:
            folha.versao = versao
            folha.save(update_fields=["versao", "hash_assinado", "atualizado_em"])

        if was_created:
            created += 1
        elif folha_created or changed:
            updated += 1

    ensure_gabaritos_basicos(avaliacao, actor=actor)

    if actor is not None:
        registrar_auditoria(
            municipio=avaliacao.municipio,
            modulo="AVALIACOES",
            evento="APLICACOES_GERADAS",
            entidade="AvaliacaoProva",
            entidade_id=avaliacao.pk,
            usuario=actor,
            depois={"criadas": created, "atualizadas": updated, "total": total},
        )

    return {"criadas": created, "atualizadas": updated, "total": total}


def _ensure_avaliacao_diario(avaliacao_prova: AvaliacaoProva, *, actor) -> AvaliacaoDiario | None:
    if avaliacao_prova.avaliacao_diario_id:
        return avaliacao_prova.avaliacao_diario

    ano_letivo = avaliacao_prova.data_aplicacao.year
    diario = DiarioTurma.objects.filter(turma=avaliacao_prova.turma, ano_letivo=ano_letivo).order_by("id").first()

    if diario is None:
        professor = avaliacao_prova.criado_por or actor
        if professor is None:
            return None
        diario = DiarioTurma.objects.create(turma=avaliacao_prova.turma, professor=professor, ano_letivo=ano_letivo)

    diario_avaliacao = AvaliacaoDiario.objects.create(
        diario=diario,
        titulo=avaliacao_prova.titulo,
        peso=avaliacao_prova.peso,
        nota_maxima=avaliacao_prova.nota_maxima,
        data=avaliacao_prova.data_aplicacao,
        ativo=True,
    )

    avaliacao_prova.avaliacao_diario = diario_avaliacao
    avaliacao_prova.save(update_fields=["avaliacao_diario", "atualizado_em"])
    return diario_avaliacao


def lancar_nota_no_diario(aplicacao: AplicacaoAvaliacao, *, actor, nota: Decimal) -> Nota | None:
    diario_avaliacao = _ensure_avaliacao_diario(aplicacao.avaliacao, actor=actor)
    if diario_avaliacao is None:
        return None

    nota_obj, _ = Nota.objects.update_or_create(
        avaliacao=diario_avaliacao,
        aluno=aplicacao.aluno,
        defaults={"valor": nota},
    )
    return nota_obj


@transaction.atomic
def corrigir_folha_manual(
    folha: FolhaResposta,
    *,
    respostas_marcadas: dict,
    actor,
    anexar_imagem=None,
) -> dict[str, Any]:
    aplicacao = folha.aplicacao
    avaliacao = aplicacao.avaliacao

    respostas_norm = normalize_respostas(
        respostas_marcadas,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
    )
    folha.respostas_marcadas = respostas_norm
    folha.versao = aplicacao.versao
    if anexar_imagem is not None:
        folha.imagem_original = anexar_imagem
    folha.save()

    gabarito = gabarito_para_versao(avaliacao, aplicacao.versao)
    if gabarito is None:
        raise ValueError("Gabarito não configurado para esta avaliação/versão.")

    gabarito_norm = normalize_respostas(
        gabarito.respostas,
        qtd_questoes=avaliacao.qtd_questoes,
        opcoes=avaliacao.opcoes,
    )

    pesos_map = {
        int(q.numero): (q.peso if q.peso is not None else Decimal("1.00"))
        for q in QuestaoProva.objects.filter(avaliacao=avaliacao)
    }

    total_peso = Decimal("0")
    pontos = Decimal("0")
    acertos = 0
    avaliadas = 0

    for idx in range(1, int(avaliacao.qtd_questoes or 0) + 1):
        key = str(idx)
        esperado = gabarito_norm.get(key, "")
        if not esperado:
            continue

        peso = Decimal(pesos_map.get(idx, Decimal("1.00")))
        total_peso += peso
        avaliadas += 1

        if respostas_norm.get(key, "") == esperado:
            pontos += peso
            acertos += 1

    if total_peso > 0:
        percentual = (pontos / total_peso) * Decimal("100")
        nota = (pontos / total_peso) * Decimal(avaliacao.nota_maxima or Decimal("10.00"))
    else:
        percentual = Decimal("0")
        nota = Decimal("0")

    nota = nota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    percentual = percentual.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    nota_diario = lancar_nota_no_diario(aplicacao, actor=actor, nota=nota)

    aplicacao.status = AplicacaoAvaliacao.Status.CORRIGIDA
    aplicacao.nota = nota
    aplicacao.percentual = percentual
    aplicacao.corrigido_em = timezone.now()
    aplicacao.corrigido_por = actor
    if nota_diario is not None:
        aplicacao.nota_diario = nota_diario
    aplicacao.save()

    registrar_auditoria(
        municipio=avaliacao.municipio,
        modulo="AVALIACOES",
        evento="FOLHA_CORRIGIDA",
        entidade="FolhaResposta",
        entidade_id=folha.pk,
        usuario=actor,
        depois={
            "avaliacao": avaliacao.pk,
            "aluno": aplicacao.aluno_id,
            "nota": str(nota),
            "percentual": str(percentual),
            "acertos": acertos,
            "questoes_avaliadas": avaliadas,
        },
    )

    return {
        "nota": nota,
        "percentual": percentual,
        "acertos": acertos,
        "questoes_avaliadas": avaliadas,
        "pontos": pontos.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_peso": total_peso.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


def resumo_avaliacao(avaliacao: AvaliacaoProva) -> dict[str, Any]:
    qs = avaliacao.aplicacoes.all()
    stats = qs.aggregate(
        total=Count("id"),
        corrigidas=Count("id", filter=Q(status=AplicacaoAvaliacao.Status.CORRIGIDA)),
        media=Avg("nota"),
    )
    return {
        "total": int(stats.get("total") or 0),
        "corrigidas": int(stats.get("corrigidas") or 0),
        "media": (stats.get("media") or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if stats.get("media") is not None
        else Decimal("0.00"),
    }


def resultados_por_questao(avaliacao: AvaliacaoProva) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    corrected = (
        FolhaResposta.objects.select_related("aplicacao", "aplicacao__avaliacao")
        .filter(aplicacao__avaliacao=avaliacao, aplicacao__status=AplicacaoAvaliacao.Status.CORRIGIDA)
        .order_by("id")
    )
    total_corrigidas = corrected.count()

    if total_corrigidas == 0:
        for idx in range(1, int(avaliacao.qtd_questoes or 0) + 1):
            rows.append(
                {
                    "numero": idx,
                    "gabarito": "-",
                    "acertos": 0,
                    "erros": 0,
                    "taxa_acerto": Decimal("0.00"),
                    "marcacoes": {},
                }
            )
        return rows

    gabaritos = {
        versao: normalize_respostas(
            gab.respostas,
            qtd_questoes=avaliacao.qtd_questoes,
            opcoes=avaliacao.opcoes,
        )
        for versao, gab in {
            item.versao: item for item in GabaritoProva.objects.filter(avaliacao=avaliacao)
        }.items()
    }

    for idx in range(1, int(avaliacao.qtd_questoes or 0) + 1):
        key = str(idx)
        acertos = 0
        erros = 0
        marcacoes = Counter()

        for folha in corrected:
            versao = folha.versao or folha.aplicacao.versao or GabaritoProva.Versao.A
            gabarito = gabaritos.get(versao) or gabaritos.get(GabaritoProva.Versao.A) or {}
            esperado = gabarito.get(key, "")
            marcado = str((folha.respostas_marcadas or {}).get(key, "") or "").upper().strip()
            if marcado:
                marcacoes[marcado] += 1

            if esperado and marcado == esperado:
                acertos += 1
            elif esperado:
                erros += 1

        taxa = Decimal("0")
        if total_corrigidas > 0:
            taxa = (Decimal(acertos) / Decimal(total_corrigidas) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        gabarito_display = "-"
        for versao in versoes_da_avaliacao(avaliacao):
            resposta = (gabaritos.get(versao) or {}).get(key)
            if resposta:
                gabarito_display = resposta
                break

        rows.append(
            {
                "numero": idx,
                "gabarito": gabarito_display,
                "acertos": acertos,
                "erros": erros,
                "taxa_acerto": taxa,
                "marcacoes": dict(marcacoes),
            }
        )

    return rows


def public_validation_payload(folha: FolhaResposta) -> dict[str, Any]:
    aplicacao = folha.aplicacao
    aluno = aplicacao.aluno
    avaliacao = aplicacao.avaliacao

    nome = (aluno.nome or "").strip()
    if len(nome) <= 3:
        nome_mascarado = "***"
    else:
        nome_mascarado = nome[:2] + "***" + nome[-1:]

    return {
        "avaliacao": avaliacao,
        "aplicacao": aplicacao,
        "folha": folha,
        "nome_mascarado": nome_mascarado,
        "integridade_ok": folha.integridade_ok(),
    }


def build_validation_url(request, folha: FolhaResposta) -> str:
    return request.build_absolute_uri(reverse("avaliacoes:folha_validar", args=[folha.token]))
