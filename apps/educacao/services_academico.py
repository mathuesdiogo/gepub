from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .models_diario import Aula, Avaliacao, Frequencia, Nota


def _mean_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return (sum(values) / Decimal(str(len(values)))).quantize(Decimal("0.01"))


def _mean_float(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / float(len(values)), 1)


def calc_periodo_metrics_by_aluno(*, turma, periodo, aluno_ids: list[int]) -> tuple[dict[int, Decimal | None], dict[int, float | None], int]:
    """
    Retorna (media_map, freq_map, total_aulas_periodo) para os alunos informados.
    """
    if not aluno_ids:
        return {}, {}, 0

    diarios = list(turma.diarios.values_list("id", flat=True))
    if not diarios:
        return {aid: None for aid in aluno_ids}, {aid: None for aid in aluno_ids}, 0

    avals = Avaliacao.objects.filter(
        diario_id__in=diarios,
        data__gte=periodo.inicio,
        data__lte=periodo.fim,
    ).only("id", "peso")
    aval_ids = list(avals.values_list("id", flat=True))
    pesos_map = {a.id: Decimal(str(a.peso or 1)) for a in avals}

    soma = {aid: Decimal("0") for aid in aluno_ids}
    soma_peso = {aid: Decimal("0") for aid in aluno_ids}

    notas_qs = Nota.objects.filter(avaliacao_id__in=aval_ids, aluno_id__in=aluno_ids).values("avaliacao_id", "aluno_id", "valor")
    for n in notas_qs:
        aluno_id = n["aluno_id"]
        valor = n["valor"]
        if valor is None:
            continue
        try:
            peso = pesos_map.get(n["avaliacao_id"], Decimal("1"))
            soma[aluno_id] += Decimal(str(valor)) * peso
            soma_peso[aluno_id] += peso
        except (InvalidOperation, ValueError):
            continue

    media_map: dict[int, Decimal | None] = {}
    for aluno_id in aluno_ids:
        media_map[aluno_id] = (soma[aluno_id] / soma_peso[aluno_id]).quantize(Decimal("0.01")) if soma_peso[aluno_id] else None

    aulas_ids = list(
        Aula.objects.filter(
            diario_id__in=diarios,
            data__gte=periodo.inicio,
            data__lte=periodo.fim,
        ).values_list("id", flat=True)
    )
    total_aulas = len(aulas_ids)
    if total_aulas == 0:
        return media_map, {aid: None for aid in aluno_ids}, 0

    presentes = {aid: 0 for aid in aluno_ids}
    freq_qs = Frequencia.objects.filter(aula_id__in=aulas_ids, aluno_id__in=aluno_ids).values("aluno_id", "status")
    for f in freq_qs:
        if f["status"] == Frequencia.Status.PRESENTE:
            presentes[f["aluno_id"]] += 1

    freq_map = {aid: round((presentes[aid] / total_aulas) * 100, 1) for aid in aluno_ids}
    return media_map, freq_map, total_aulas


def classify_resultado(*, media: Decimal | None, frequencia: float | None, media_corte: Decimal, frequencia_corte: Decimal) -> str:
    if media is None or frequencia is None:
        return "Sem dados"

    media_recuperacao = (media_corte - Decimal("1.00")).quantize(Decimal("0.01"))

    if media >= media_corte and Decimal(str(frequencia)) >= frequencia_corte:
        return "Aprovado"
    if media >= media_recuperacao and Decimal(str(frequencia)) >= frequencia_corte:
        return "Recuperação"
    return "Reprovado"


def calc_historico_resumo(*, turma, periodos, aluno_id: int, media_corte: Decimal = Decimal("6.00"), frequencia_corte: Decimal = Decimal("75.00")):
    medias: list[Decimal] = []
    freqs: list[float] = []

    for periodo in periodos:
        media_map, freq_map, _ = calc_periodo_metrics_by_aluno(turma=turma, periodo=periodo, aluno_ids=[aluno_id])
        media = media_map.get(aluno_id)
        freq = freq_map.get(aluno_id)
        if media is not None:
            medias.append(media)
        if freq is not None:
            freqs.append(freq)

    media_final = _mean_decimal(medias)
    freq_final = _mean_float(freqs)
    resultado = classify_resultado(
        media=media_final,
        frequencia=freq_final,
        media_corte=media_corte,
        frequencia_corte=frequencia_corte,
    )
    return media_final, freq_final, resultado
