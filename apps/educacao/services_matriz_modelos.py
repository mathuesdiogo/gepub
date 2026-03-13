from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable

from django.db import transaction

from .models import MatrizComponente, MatrizComponenteEquivalenciaGrupo, MatrizComponenteEquivalenciaItem, MatrizComponenteRelacao, MatrizCurricular
from .models_notas import BNCCCodigo, ComponenteCurricular


@dataclass
class AplicacaoModelosResumo:
    matrizes_criadas: int = 0
    matrizes_atualizadas: int = 0
    matrizes_ignoradas: int = 0
    componentes_criados: int = 0
    componentes_atualizados: int = 0


MODELO_REDE_CHOICES: tuple[tuple[str, str], ...] = (
    ("MUNICIPAL", "Rede Municipal (anual)"),
    ("ESTADUAL", "Rede Estadual (anual)"),
)


def _componentes_infantil() -> list[dict[str, object]]:
    return [
        {"nome": "O eu, o outro e o nós", "sigla": "EON", "aulas": 5, "ch": 200, "area": "EI"},
        {"nome": "Corpo, gestos e movimentos", "sigla": "CGM", "aulas": 5, "ch": 200, "area": "EI"},
        {"nome": "Traços, sons, cores e formas", "sigla": "TSCF", "aulas": 5, "ch": 200, "area": "EI"},
        {"nome": "Escuta, fala, pensamento e imaginação", "sigla": "EFPI", "aulas": 5, "ch": 200, "area": "EI"},
        {
            "nome": "Espaços, tempos, quantidades, relações e transformações",
            "sigla": "ETQRT",
            "aulas": 5,
            "ch": 200,
            "area": "EI",
        },
    ]


def _componentes_fund_iniciais(rede: str) -> list[dict[str, object]]:
    base = [
        {"nome": "Língua Portuguesa", "sigla": "LP", "aulas": 7, "ch": 280, "area": "LP"},
        {"nome": "Matemática", "sigla": "MAT", "aulas": 6, "ch": 240, "area": "MA"},
        {"nome": "Ciências", "sigla": "CIE", "aulas": 3, "ch": 120, "area": "CI"},
        {"nome": "História", "sigla": "HIS", "aulas": 2, "ch": 80, "area": "HI"},
        {"nome": "Geografia", "sigla": "GEO", "aulas": 2, "ch": 80, "area": "GE"},
        {"nome": "Arte", "sigla": "ART", "aulas": 1, "ch": 40, "area": "AR"},
        {"nome": "Educação Física", "sigla": "EDF", "aulas": 2, "ch": 80, "area": "EF"},
        {"nome": "Ensino Religioso", "sigla": "ER", "aulas": 1, "ch": 40, "area": "ER"},
    ]
    if rede == "MUNICIPAL":
        base.append({"nome": "Projeto de Leitura", "sigla": "PLE", "aulas": 1, "ch": 40, "area": "LP"})
    return base


def _componentes_fund_finais(rede: str) -> list[dict[str, object]]:
    base = [
        {"nome": "Língua Portuguesa", "sigla": "LP", "aulas": 5, "ch": 200, "area": "LP"},
        {"nome": "Matemática", "sigla": "MAT", "aulas": 5, "ch": 200, "area": "MA"},
        {"nome": "Ciências", "sigla": "CIE", "aulas": 4, "ch": 160, "area": "CI"},
        {"nome": "História", "sigla": "HIS", "aulas": 2, "ch": 80, "area": "HI"},
        {"nome": "Geografia", "sigla": "GEO", "aulas": 2, "ch": 80, "area": "GE"},
        {"nome": "Língua Inglesa", "sigla": "ING", "aulas": 2, "ch": 80, "area": "LI"},
        {"nome": "Arte", "sigla": "ART", "aulas": 1, "ch": 40, "area": "AR"},
        {"nome": "Educação Física", "sigla": "EDF", "aulas": 2, "ch": 80, "area": "EF"},
        {"nome": "Ensino Religioso", "sigla": "ER", "aulas": 1, "ch": 40, "area": "ER"},
    ]
    if rede == "ESTADUAL":
        base.append({"nome": "Tecnologia e Inovação", "sigla": "TEC", "aulas": 1, "ch": 40, "area": "CG"})
    return base


def _series_por_etapa() -> list[tuple[str, str, str]]:
    return [
        (MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL, MatrizCurricular.SerieAno.INFANTIL_BERCARIO, "Berçário"),
        (MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL, MatrizCurricular.SerieAno.INFANTIL_MATERNAL_I, "Maternal I"),
        (MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL, MatrizCurricular.SerieAno.INFANTIL_MATERNAL_II, "Maternal II"),
        (MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL, MatrizCurricular.SerieAno.INFANTIL_JARDIM_I, "Jardim I"),
        (MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL, MatrizCurricular.SerieAno.INFANTIL_JARDIM_II, "Jardim II"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_1, "1º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_2, "2º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_3, "3º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_4, "4º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_5, "5º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_6, "6º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_7, "7º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_8, "8º ano"),
        (MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS, MatrizCurricular.SerieAno.FUNDAMENTAL_9, "9º ano"),
    ]


def _nome_rede(rede: str) -> str:
    rede_key = (rede or "").strip().upper()
    return dict(MODELO_REDE_CHOICES).get(rede_key, "Rede")


def _componente_bncc_defaults(etapa_base: str, area: str) -> tuple[str, str]:
    modalidade = (
        BNCCCodigo.Modalidade.EDUCACAO_INFANTIL
        if etapa_base == MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL
        else BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL
    )
    etapa = {
        MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL: BNCCCodigo.Etapa.EDUCACAO_INFANTIL,
        MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS: BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
        MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS: BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_FINAIS,
    }.get(etapa_base, "")
    return modalidade, etapa


def _limpar_matriz(matriz: MatrizCurricular):
    MatrizComponenteRelacao.objects.filter(origem__matriz=matriz).delete()
    MatrizComponenteEquivalenciaItem.objects.filter(grupo__matriz=matriz).delete()
    MatrizComponenteEquivalenciaGrupo.objects.filter(matriz=matriz).delete()
    matriz.componentes.all().delete()


def _upsert_componentes_matriz(matriz: MatrizCurricular, componentes: list[dict[str, object]], resumo: AplicacaoModelosResumo):
    for ordem, item in enumerate(componentes, start=1):
        nome = str(item.get("nome") or "").strip()
        if not nome:
            continue
        sigla = str(item.get("sigla") or "").strip()
        area = str(item.get("area") or "").strip().upper()
        aulas = int(item.get("aulas") or 1)
        ch = int(item.get("ch") or 0)
        obrigatoria = bool(item.get("obrigatoria", True))
        ativo = bool(item.get("ativo", True))

        modalidade_bncc, etapa_bncc = _componente_bncc_defaults(matriz.etapa_base, area)

        componente, _ = ComponenteCurricular.objects.get_or_create(
            nome=nome,
            sigla=sigla,
            defaults={
                "modalidade_bncc": modalidade_bncc,
                "etapa_bncc": etapa_bncc,
                "area_codigo_bncc": area,
                "ativo": True,
            },
        )

        matriz_comp, created = MatrizComponente.objects.update_or_create(
            matriz=matriz,
            componente=componente,
            defaults={
                "ordem": ordem,
                "carga_horaria_anual": ch,
                "aulas_semanais": aulas,
                "obrigatoria": obrigatoria,
                "ativo": ativo,
            },
        )
        if created:
            resumo.componentes_criados += 1
        else:
            resumo.componentes_atualizados += 1


@transaction.atomic
def aplicar_modelo_oficial_para_unidades(
    *,
    rede: str,
    ano_referencia: int,
    unidades: Iterable,
    sobrescrever_existentes: bool = False,
) -> AplicacaoModelosResumo:
    rede_key = (rede or "").strip().upper()
    if rede_key not in dict(MODELO_REDE_CHOICES):
        raise ValueError("Modelo de rede inválido.")

    resumo = AplicacaoModelosResumo()
    for unidade in unidades:
        for etapa_base, serie_ano, serie_label in _series_por_etapa():
            matriz = (
                MatrizCurricular.objects.filter(
                    unidade=unidade,
                    etapa_base=etapa_base,
                    serie_ano=serie_ano,
                    ano_referencia=ano_referencia,
                )
                .order_by("id")
                .first()
            )
            criada = False
            if matriz is None:
                matriz = MatrizCurricular.objects.create(
                    unidade=unidade,
                    nome=f"Matriz {_nome_rede(rede_key)} {serie_label}",
                    etapa_base=etapa_base,
                    serie_ano=serie_ano,
                    ano_referencia=ano_referencia,
                    carga_horaria_anual=800,
                    dias_letivos_previstos=200,
                    ativo=True,
                )
                criada = True
                resumo.matrizes_criadas += 1
            else:
                resumo.matrizes_atualizadas += 1

            if not criada and not sobrescrever_existentes and matriz.componentes.exists():
                resumo.matrizes_ignoradas += 1
                continue

            if not criada and sobrescrever_existentes:
                _limpar_matriz(matriz)

            if etapa_base == MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL:
                componentes = _componentes_infantil()
            elif etapa_base == MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS:
                componentes = _componentes_fund_iniciais(rede_key)
            else:
                componentes = _componentes_fund_finais(rede_key)

            _upsert_componentes_matriz(matriz, componentes, resumo)

    return resumo


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return default


def _parse_bool(value: str, default: bool = True) -> bool:
    val = str(value or "").strip().lower()
    if val in {"1", "true", "sim", "yes", "y", "s"}:
        return True
    if val in {"0", "false", "nao", "não", "no", "n"}:
        return False
    return default


def importar_modelo_csv(arquivo_bytes: bytes) -> list[dict[str, object]]:
    text = arquivo_bytes.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Arquivo CSV sem cabeçalho.")

    required = {"etapa_base", "serie_ano", "componente_nome"}
    faltantes = [f for f in required if f not in set(reader.fieldnames)]
    if faltantes:
        raise ValueError("CSV inválido. Campos obrigatórios: etapa_base, serie_ano, componente_nome.")

    data: dict[tuple[str, str], list[dict[str, object]]] = {}
    nome_por_chave: dict[tuple[str, str], str] = {}

    for row in reader:
        etapa_base = str(row.get("etapa_base") or "").strip().upper()
        serie_ano = str(row.get("serie_ano") or "").strip().upper()
        componente_nome = str(row.get("componente_nome") or "").strip()
        if not etapa_base or not serie_ano or not componente_nome:
            continue

        key = (etapa_base, serie_ano)
        data.setdefault(key, []).append(
            {
                "nome": componente_nome,
                "sigla": str(row.get("componente_sigla") or "").strip(),
                "aulas": max(1, _parse_int(row.get("aulas_semanais"), 1)),
                "ch": max(0, _parse_int(row.get("carga_horaria_anual"), 0)),
                "obrigatoria": _parse_bool(row.get("obrigatoria"), True),
                "ativo": _parse_bool(row.get("ativo"), True),
                "ordem": max(1, _parse_int(row.get("ordem"), 1)),
                "area": str(row.get("area_codigo_bncc") or "").strip().upper(),
            }
        )
        matriz_nome = str(row.get("matriz_nome") or "").strip()
        if matriz_nome:
            nome_por_chave[key] = matriz_nome

    result: list[dict[str, object]] = []
    for (etapa_base, serie_ano), componentes in data.items():
        componentes = sorted(componentes, key=lambda x: int(x.get("ordem") or 1))
        result.append(
            {
                "etapa_base": etapa_base,
                "serie_ano": serie_ano,
                "nome": nome_por_chave.get((etapa_base, serie_ano), f"Matriz Importada {serie_ano}"),
                "componentes": componentes,
            }
        )
    return result


@transaction.atomic
def aplicar_modelo_importado_para_unidades(
    *,
    modelo_importado: list[dict[str, object]],
    ano_referencia: int,
    unidades: Iterable,
    sobrescrever_existentes: bool = False,
) -> AplicacaoModelosResumo:
    resumo = AplicacaoModelosResumo()

    etapa_validas = {value for value, _ in MatrizCurricular.EtapaBase.choices}
    serie_validas = {value for value, _ in MatrizCurricular.SerieAno.choices}

    for unidade in unidades:
        for item in modelo_importado:
            etapa_base = str(item.get("etapa_base") or "").strip().upper()
            serie_ano = str(item.get("serie_ano") or "").strip().upper()
            if etapa_base not in etapa_validas or serie_ano not in serie_validas:
                continue

            matriz = (
                MatrizCurricular.objects.filter(
                    unidade=unidade,
                    etapa_base=etapa_base,
                    serie_ano=serie_ano,
                    ano_referencia=ano_referencia,
                )
                .order_by("id")
                .first()
            )
            criada = False
            if matriz is None:
                matriz = MatrizCurricular.objects.create(
                    unidade=unidade,
                    nome=str(item.get("nome") or f"Matriz Importada {serie_ano}")[:180],
                    etapa_base=etapa_base,
                    serie_ano=serie_ano,
                    ano_referencia=ano_referencia,
                    carga_horaria_anual=800,
                    dias_letivos_previstos=200,
                    ativo=True,
                )
                criada = True
                resumo.matrizes_criadas += 1
            else:
                resumo.matrizes_atualizadas += 1

            if not criada and not sobrescrever_existentes and matriz.componentes.exists():
                resumo.matrizes_ignoradas += 1
                continue

            if not criada and sobrescrever_existentes:
                _limpar_matriz(matriz)

            componentes = list(item.get("componentes") or [])
            _upsert_componentes_matriz(matriz, componentes, resumo)

    return resumo
