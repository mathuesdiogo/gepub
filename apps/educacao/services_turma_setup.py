from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from itertools import cycle

from django.db import transaction
from django.utils import timezone

from .models import (
    MatrizComponente,
    MatrizComponenteEquivalenciaGrupo,
    MatrizComponenteEquivalenciaItem,
    MatrizComponenteRelacao,
    MatrizCurricular,
    Turma,
)
from .models_diario import DiarioTurma
from .models_horarios import AulaHorario, GradeHorario
from .models_notas import BNCCCodigo, ComponenteCurricular


TURNOS_PADRAO: dict[str, list[tuple[time, time]]] = {
    "MANHA": [
        (time(7, 30), time(8, 20)),
        (time(8, 20), time(9, 10)),
        (time(9, 20), time(10, 10)),
        (time(10, 10), time(11, 0)),
        (time(11, 0), time(11, 50)),
    ],
    "TARDE": [
        (time(13, 30), time(14, 20)),
        (time(14, 20), time(15, 10)),
        (time(15, 20), time(16, 10)),
        (time(16, 10), time(17, 0)),
        (time(17, 0), time(17, 50)),
    ],
    "NOITE": [
        (time(18, 30), time(19, 20)),
        (time(19, 20), time(20, 10)),
        (time(20, 20), time(21, 10)),
        (time(21, 10), time(22, 0)),
    ],
}


@dataclass
class ResultadoDiarios:
    total_professores: int
    criados: int


@dataclass
class ResultadoHorario:
    criado: int
    ignorado: bool
    fonte: str


@dataclass
class ResultadoTurmaSetup:
    diarios: ResultadoDiarios
    horario: ResultadoHorario


def _dias_uteis() -> list[str]:
    preferidos = [
        AulaHorario.Dia.SEG,
        AulaHorario.Dia.TER,
        AulaHorario.Dia.QUA,
        AulaHorario.Dia.QUI,
        AulaHorario.Dia.SEX,
    ]
    validos = {value for value, _ in AulaHorario.Dia.choices}
    dias = [dia for dia in preferidos if dia in validos]
    if dias:
        return dias
    return [value for value, _ in AulaHorario.Dia.choices][:5]


def construir_pool_disciplinas_turma(turma: Turma, *, blocos_total: int) -> tuple[list[str], str]:
    matriz = getattr(turma, "matriz_curricular", None)
    if matriz is not None:
        componentes = list(
            matriz.componentes.select_related("componente")
            .filter(ativo=True)
            .order_by("ordem", "componente__nome")
        )
        pool: list[str] = []
        for item in componentes:
            nome = (getattr(getattr(item, "componente", None), "nome", "") or "").strip()
            if not nome:
                continue
            repeticoes = int(item.aulas_semanais or 0)
            repeticoes = repeticoes if repeticoes > 0 else 1
            repeticoes = min(repeticoes, 10)
            pool.extend([nome] * repeticoes)
        if pool:
            return pool, "matriz curricular"

    curso_extra = getattr(turma, "curso", None)
    if curso_extra is not None:
        disciplinas = list(curso_extra.disciplinas.filter(ativo=True).order_by("ordem", "nome"))
        pool = [((item.nome or "").strip()) for item in disciplinas if (item.nome or "").strip()]
        if pool:
            return pool, "atividade extracurricular"

    fallback = [f"Aula {idx}" for idx in range(1, max(1, blocos_total) + 1)]
    return fallback, "grade padrão genérica"


def sincronizar_diarios_turma(turma: Turma, *, ano_letivo: int | None = None) -> ResultadoDiarios:
    ano_ref = int(ano_letivo or turma.ano_letivo or timezone.localdate().year)
    professores = list(turma.professores.filter(is_active=True).order_by("first_name", "last_name", "username"))
    criados = 0
    for professor in professores:
        _, created = DiarioTurma.objects.get_or_create(
            turma=turma,
            professor=professor,
            ano_letivo=ano_ref,
        )
        if created:
            criados += 1
    return ResultadoDiarios(total_professores=len(professores), criados=criados)


def gerar_grade_horario_padrao_turma(
    turma: Turma,
    *,
    overwrite: bool = False,
    preencher_professor: bool = True,
) -> ResultadoHorario:
    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    if grade.aulas.exists() and not overwrite:
        return ResultadoHorario(criado=0, ignorado=True, fonte="já configurado")

    if overwrite:
        grade.aulas.all().delete()

    turno = str(getattr(turma, "turno", "") or "MANHA").upper()
    blocos = TURNOS_PADRAO.get(turno, TURNOS_PADRAO["MANHA"])
    disciplinas_pool, fonte = construir_pool_disciplinas_turma(turma, blocos_total=len(blocos))
    disciplinas_cycle = cycle(disciplinas_pool)

    professores = []
    professor_cycle = None
    if preencher_professor:
        professores = list(turma.professores.filter(is_active=True).order_by("first_name", "last_name", "username"))
        if professores:
            professor_cycle = cycle(professores)

    created = 0
    for dia in _dias_uteis():
        for inicio, fim in blocos:
            AulaHorario.objects.create(
                grade=grade,
                dia=dia,
                inicio=inicio,
                fim=fim,
                disciplina=next(disciplinas_cycle),
                professor=next(professor_cycle) if professor_cycle else None,
                sala="",
            )
            created += 1

    return ResultadoHorario(criado=created, ignorado=False, fonte=fonte)


def inicializar_turma_fluxo_anual(
    turma: Turma,
    *,
    overwrite_horario: bool = False,
    gerar_horario: bool = True,
) -> ResultadoTurmaSetup:
    diarios = sincronizar_diarios_turma(turma)
    if gerar_horario:
        horario = gerar_grade_horario_padrao_turma(turma, overwrite=overwrite_horario, preencher_professor=True)
    else:
        horario = ResultadoHorario(criado=0, ignorado=True, fonte="desativado")
    return ResultadoTurmaSetup(diarios=diarios, horario=horario)


def _componentes_base_matriz(matriz: MatrizCurricular) -> list[dict[str, object]]:
    if matriz.etapa_base == MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL:
        return [
            {"nome": "O eu, o outro e o nós", "sigla": "EON", "aulas": 5, "ch": 200},
            {"nome": "Corpo, gestos e movimentos", "sigla": "CGM", "aulas": 5, "ch": 200},
            {"nome": "Traços, sons, cores e formas", "sigla": "TSCF", "aulas": 5, "ch": 200},
            {"nome": "Escuta, fala, pensamento e imaginação", "sigla": "EFPI", "aulas": 5, "ch": 200},
            {"nome": "Espaços, tempos, quantidades, relações e transformações", "sigla": "ETQRT", "aulas": 5, "ch": 200},
        ]

    base_fundamental = [
        {"nome": "Língua Portuguesa", "sigla": "LP", "aulas": 7, "ch": 280, "area": "LP"},
        {"nome": "Matemática", "sigla": "MAT", "aulas": 6, "ch": 240, "area": "MA"},
        {"nome": "Ciências", "sigla": "CIE", "aulas": 3, "ch": 120, "area": "CI"},
        {"nome": "História", "sigla": "HIS", "aulas": 2, "ch": 80, "area": "HI"},
        {"nome": "Geografia", "sigla": "GEO", "aulas": 2, "ch": 80, "area": "GE"},
        {"nome": "Arte", "sigla": "ART", "aulas": 1, "ch": 40, "area": "AR"},
        {"nome": "Educação Física", "sigla": "EDF", "aulas": 2, "ch": 80, "area": "EF"},
        {"nome": "Ensino Religioso", "sigla": "ER", "aulas": 1, "ch": 40, "area": "ER"},
    ]

    if matriz.etapa_base == MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS:
        base_fundamental = [
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

    return base_fundamental


def preencher_componentes_base_matriz(
    matriz: MatrizCurricular,
    *,
    limpar_existentes: bool = False,
) -> tuple[int, int]:
    modalidade_bncc = (
        BNCCCodigo.Modalidade.EDUCACAO_INFANTIL
        if matriz.etapa_base == MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL
        else BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL
    )
    etapa_bncc = {
        MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL: BNCCCodigo.Etapa.EDUCACAO_INFANTIL,
        MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS: BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
        MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS: BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_FINAIS,
    }.get(matriz.etapa_base, "")

    base = _componentes_base_matriz(matriz)
    created = 0
    skipped = 0

    with transaction.atomic():
        if limpar_existentes:
            MatrizComponenteRelacao.objects.filter(origem__matriz=matriz).delete()
            MatrizComponenteEquivalenciaItem.objects.filter(grupo__matriz=matriz).delete()
            MatrizComponenteEquivalenciaGrupo.objects.filter(matriz=matriz).delete()
            matriz.componentes.all().delete()

        used_orders = set(matriz.componentes.values_list("ordem", flat=True))
        next_order = max(used_orders) + 1 if used_orders else 1

        for item in base:
            componente, _ = ComponenteCurricular.objects.get_or_create(
                nome=item["nome"],
                sigla=item["sigla"],
                defaults={
                    "modalidade_bncc": modalidade_bncc,
                    "etapa_bncc": etapa_bncc,
                    "area_codigo_bncc": item.get("area", ""),
                    "ativo": True,
                },
            )

            if componente.modalidade_bncc != modalidade_bncc or componente.etapa_bncc != etapa_bncc:
                componente.modalidade_bncc = modalidade_bncc
                componente.etapa_bncc = etapa_bncc
                if item.get("area") and not componente.area_codigo_bncc:
                    componente.area_codigo_bncc = str(item.get("area") or "")
                componente.save(update_fields=["modalidade_bncc", "etapa_bncc", "area_codigo_bncc"])

            matriz_item, was_created = MatrizComponente.objects.get_or_create(
                matriz=matriz,
                componente=componente,
                defaults={
                    "ordem": next_order,
                    "carga_horaria_anual": int(item["ch"]),
                    "aulas_semanais": int(item["aulas"]),
                    "obrigatoria": True,
                    "ativo": True,
                },
            )
            if was_created:
                created += 1
                used_orders.add(next_order)
                next_order += 1
            else:
                skipped += 1
                update_fields = []
                if (matriz_item.carga_horaria_anual or 0) == 0:
                    matriz_item.carga_horaria_anual = int(item["ch"])
                    update_fields.append("carga_horaria_anual")
                if (matriz_item.aulas_semanais or 0) == 0:
                    matriz_item.aulas_semanais = int(item["aulas"])
                    update_fields.append("aulas_semanais")
                if update_fields:
                    matriz_item.save(update_fields=update_fields)

    return created, skipped


def clonar_matriz_para_ano(matriz: MatrizCurricular, *, ano_destino: int) -> MatrizCurricular:
    ano_destino = int(ano_destino)
    if ano_destino <= 0:
        raise ValueError("Ano de destino inválido.")

    if MatrizCurricular.objects.filter(
        unidade=matriz.unidade,
        etapa_base=matriz.etapa_base,
        serie_ano=matriz.serie_ano,
        ano_referencia=ano_destino,
        nome=matriz.nome,
    ).exists():
        raise ValueError("Já existe matriz com mesmo nome/série para o ano informado.")

    with transaction.atomic():
        nova = MatrizCurricular.objects.create(
            unidade=matriz.unidade,
            nome=matriz.nome,
            etapa_base=matriz.etapa_base,
            serie_ano=matriz.serie_ano,
            ano_referencia=ano_destino,
            carga_horaria_anual=matriz.carga_horaria_anual,
            dias_letivos_previstos=matriz.dias_letivos_previstos,
            ativo=matriz.ativo,
            observacao=matriz.observacao,
        )

        map_componentes: dict[int, MatrizComponente] = {}
        for item in matriz.componentes.select_related("componente").order_by("ordem", "id"):
            novo_item = MatrizComponente.objects.create(
                matriz=nova,
                componente=item.componente,
                ordem=item.ordem,
                carga_horaria_anual=item.carga_horaria_anual,
                aulas_semanais=item.aulas_semanais,
                obrigatoria=item.obrigatoria,
                ativo=item.ativo,
                observacao=item.observacao,
            )
            map_componentes[item.id] = novo_item

        for rel in MatrizComponenteRelacao.objects.filter(origem__matriz=matriz, destino__matriz=matriz):
            origem_nova = map_componentes.get(rel.origem_id)
            destino_nova = map_componentes.get(rel.destino_id)
            if not origem_nova or not destino_nova:
                continue
            MatrizComponenteRelacao.objects.create(
                origem=origem_nova,
                destino=destino_nova,
                tipo=rel.tipo,
                ativo=rel.ativo,
                observacao=rel.observacao,
            )

        map_grupos: dict[int, MatrizComponenteEquivalenciaGrupo] = {}
        for grupo in MatrizComponenteEquivalenciaGrupo.objects.filter(matriz=matriz).order_by("id"):
            novo_grupo = MatrizComponenteEquivalenciaGrupo.objects.create(
                matriz=nova,
                nome=grupo.nome,
                minimo_componentes=grupo.minimo_componentes,
                ativo=grupo.ativo,
                observacao=grupo.observacao,
            )
            map_grupos[grupo.id] = novo_grupo

        itens = MatrizComponenteEquivalenciaItem.objects.select_related("componente", "grupo").filter(
            grupo__matriz=matriz
        )
        for item in itens:
            novo_grupo = map_grupos.get(item.grupo_id)
            novo_comp = map_componentes.get(item.componente_id)
            if not novo_grupo or not novo_comp:
                continue
            MatrizComponenteEquivalenciaItem.objects.create(
                grupo=novo_grupo,
                componente=novo_comp,
                ordem=item.ordem,
                ativo=item.ativo,
            )

    return nova
