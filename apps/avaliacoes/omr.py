from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import BinaryIO

from PIL import Image, ImageOps

from .forms import option_letters


class OMRDetectionError(Exception):
    pass


@dataclass
class OMRQuestionResult:
    questao: int
    resposta: str
    confianca: float


def _prepare_image(file_obj) -> Image.Image:
    name = str(getattr(file_obj, "name", "") or "").lower().strip()
    if name.endswith(".pdf"):
        raise OMRDetectionError("OMR automático não suporta PDF diretamente. Envie imagem (JPG/PNG).")

    stream: BinaryIO | object = file_obj
    if hasattr(stream, "open"):
        try:
            stream.open("rb")
        except Exception:
            pass

    if hasattr(stream, "seek"):
        try:
            stream.seek(0)
        except Exception:
            pass

    try:
        img = Image.open(stream)
        img = ImageOps.exif_transpose(img)
        img.load()
    except Exception as exc:
        raise OMRDetectionError("Não foi possível ler a imagem para OMR.") from exc

    if img.width > img.height:
        img = img.rotate(90, expand=True)

    return img.convert("L")


def _dark_ratio(img_gray: Image.Image) -> float:
    pixels = list(img_gray.getdata())
    if not pixels:
        return 0.0
    dark = sum(1 for px in pixels if px < 110)
    return dark / float(len(pixels))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def suggest_answers_from_omr_image(
    file_obj,
    *,
    qtd_questoes: int,
    opcoes: int,
) -> dict:
    """
    OMR semiautomático (beta).
    Assume folha padrão do PDF gerado pelo módulo com grade central em A4.
    """
    img = _prepare_image(file_obj)
    width, height = img.size

    # Região aproximada da grade no layout PDF padrão
    left = int(width * 0.08)
    right = int(width * 0.92)
    top = int(height * 0.32)
    bottom = int(height * 0.92)

    total_q = max(1, int(qtd_questoes or 1))
    letras = option_letters(opcoes)
    total_cols = 1 + len(letras)  # coluna Q + alternativas

    row_h = (bottom - top) / float(total_q + 1)  # +1 cabeçalho
    col_w = (right - left) / float(total_cols)

    resultados: list[OMRQuestionResult] = []
    respostas: dict[str, str] = {}

    for q_idx in range(total_q):
        # linha de questão começa após cabeçalho da tabela
        y0 = top + int((q_idx + 1) * row_h)
        y1 = top + int((q_idx + 2) * row_h)

        scores: list[float] = []
        for opt_idx in range(len(letras)):
            # colunas de resposta começam após a coluna de número
            x0 = left + int((opt_idx + 1) * col_w)
            x1 = left + int((opt_idx + 2) * col_w)

            cx = int((x0 + x1) / 2)
            cy = int((y0 + y1) / 2)
            r = int(min(col_w, row_h) * 0.24)

            patch = img.crop((cx - r, cy - r, cx + r, cy + r))
            score = _dark_ratio(patch)
            scores.append(score)

        if not scores:
            continue

        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        best_idx, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        base = median(scores)

        gain_vs_base = best_score - base
        gain_vs_second = best_score - second_score

        # Heurística semiautomática:
        # aceita marcações leves (scan/foto) exigindo ganho relativo sobre o baseline da linha.
        threshold_abs = max(0.02, base + 0.015)
        if best_score >= threshold_abs and gain_vs_second >= 0.004:
            letter = letras[best_idx]
            confidence = _clamp((gain_vs_base * 4.0) + (gain_vs_second * 3.0), 0.0, 1.0)
            questao = q_idx + 1
            respostas[str(questao)] = letter
            resultados.append(OMRQuestionResult(questao=questao, resposta=letter, confianca=confidence))

    if resultados:
        confianca_media = sum(item.confianca for item in resultados) / len(resultados)
    else:
        confianca_media = 0.0

    return {
        "respostas": respostas,
        "questoes_detectadas": len(resultados),
        "total_questoes": total_q,
        "confianca_media": round(confianca_media * 100.0, 2),
        "detalhes": [
            {
                "questao": item.questao,
                "resposta": item.resposta,
                "confianca": round(item.confianca * 100.0, 2),
            }
            for item in resultados
        ],
    }
