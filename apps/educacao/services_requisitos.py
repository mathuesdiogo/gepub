from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Avg

from apps.core.services_auditoria import registrar_auditoria

from .models import (
    Aluno,
    MatrizComponente,
    MatrizComponenteEquivalenciaItem,
    MatrizComponenteRelacao,
    Matricula,
    Turma,
)
from .models_diario import Aula
from .models_notas import NotaCurricular


NOTA_MINIMA_APROVACAO = Decimal("6.00")


@dataclass
class ResultadoRequisitos:
    bloqueado: bool = False
    pendencias: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    detalhes: dict[str, list[str]] = field(default_factory=dict)



def _resultado_texto_aprovado(resultado_final: str) -> bool:
    texto = (resultado_final or "").strip().lower()
    if not texto:
        return True
    if any(chave in texto for chave in ["reprov", "evad", "cancel", "retido", "tranc"]):
        return False
    if any(chave in texto for chave in ["aprov", "concl", "andamento", "progress"]):
        return True
    return True



def _componentes_aprovados_por_notas(aluno_id: int) -> tuple[set[int], bool]:
    aprovados: set[int] = set()
    evidencias = False

    rows = (
        NotaCurricular.objects.filter(matricula__aluno_id=aluno_id)
        .values("avaliacao__componente_id")
        .annotate(media=Avg("valor"))
    )
    for row in rows:
        componente_id = row.get("avaliacao__componente_id")
        media = row.get("media")
        if not componente_id:
            continue
        evidencias = True
        if media is not None and Decimal(str(media)) >= NOTA_MINIMA_APROVACAO:
            aprovados.add(int(componente_id))

    return aprovados, evidencias



def _componentes_aprovados_por_matriculas_concluidas(aluno_id: int, *, excluir_turma_id: int | None = None) -> tuple[set[int], bool]:
    aprovados: set[int] = set()

    qs = Matricula.objects.select_related("turma", "turma__matriz_curricular").filter(
        aluno_id=aluno_id,
        turma__matriz_curricular__isnull=False,
    )
    if excluir_turma_id:
        qs = qs.exclude(turma_id=excluir_turma_id)

    evidencias = qs.exists()
    matriz_ids: set[int] = set()
    for matricula in qs:
        if matricula.situacao == Matricula.Situacao.CONCLUIDO or _resultado_texto_aprovado(matricula.resultado_final):
            matriz_id = getattr(matricula.turma, "matriz_curricular_id", None)
            if matriz_id:
                matriz_ids.add(int(matriz_id))

    if not matriz_ids:
        return aprovados, evidencias

    for matriz_id, componente_id in MatrizComponente.objects.filter(
        matriz_id__in=matriz_ids,
        ativo=True,
    ).values_list("matriz_id", "componente_id"):
        if matriz_id and componente_id:
            aprovados.add(int(componente_id))

    return aprovados, evidencias



def componentes_aprovados_aluno(aluno_id: int, *, excluir_turma_id: int | None = None) -> tuple[set[int], bool]:
    aprovados_notas, evid_notas = _componentes_aprovados_por_notas(aluno_id)
    aprovados_matriculas, evid_matriculas = _componentes_aprovados_por_matriculas_concluidas(
        aluno_id,
        excluir_turma_id=excluir_turma_id,
    )
    return (aprovados_notas | aprovados_matriculas), (evid_notas or evid_matriculas)



def _build_equivalencia_map(matriz_id: int) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = {}

    def add_edge(a: int, b: int) -> None:
        if not a or not b or a == b:
            return
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)

    relacoes = MatrizComponenteRelacao.objects.filter(
        ativo=True,
        tipo=MatrizComponenteRelacao.Tipo.EQUIVALENCIA,
        origem__matriz_id=matriz_id,
        destino__matriz_id=matriz_id,
        origem__ativo=True,
        destino__ativo=True,
    ).values_list("origem__componente_id", "destino__componente_id")

    for origem_id, destino_id in relacoes:
        if origem_id and destino_id:
            add_edge(int(origem_id), int(destino_id))

    grupos = (
        MatrizComponenteEquivalenciaItem.objects.select_related("grupo")
        .filter(grupo__matriz_id=matriz_id, grupo__ativo=True, ativo=True, componente__ativo=True)
        .values_list("grupo_id", "componente__componente_id")
    )
    por_grupo: dict[int, list[int]] = {}
    for grupo_id, comp_id in grupos:
        if not grupo_id or not comp_id:
            continue
        por_grupo.setdefault(int(grupo_id), []).append(int(comp_id))

    for itens in por_grupo.values():
        uniq = sorted(set(itens))
        for idx, comp_id in enumerate(uniq):
            for outro in uniq[idx + 1 :]:
                add_edge(comp_id, outro)

    visited: set[int] = set()
    equivalencias: dict[int, set[int]] = {}

    for node in list(graph.keys()):
        if node in visited:
            continue
        stack = [node]
        componente_set: set[int] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            componente_set.add(current)
            stack.extend(graph.get(current, set()) - visited)

        for componente_id in componente_set:
            equivalencias[componente_id] = componente_set - {componente_id}

    return equivalencias



def _satisfaz_requisito(componente_requerido_id: int, componentes_aprovados: set[int], equivalencia_map: dict[int, set[int]]) -> bool:
    if componente_requerido_id in componentes_aprovados:
        return True
    equivalentes = equivalencia_map.get(componente_requerido_id, set())
    return bool(equivalentes.intersection(componentes_aprovados))



def avaliar_requisitos_matricula(*, aluno: Aluno, turma: Turma) -> ResultadoRequisitos:
    resultado = ResultadoRequisitos()
    matriz_id = getattr(turma, "matriz_curricular_id", None)
    if not matriz_id:
        return resultado

    pre_relacoes = list(
        MatrizComponenteRelacao.objects.select_related("origem", "origem__componente")
        .filter(
            ativo=True,
            tipo=MatrizComponenteRelacao.Tipo.PRE_REQUISITO,
            origem__matriz_id=matriz_id,
            destino__matriz_id=matriz_id,
            origem__ativo=True,
            destino__ativo=True,
        )
    )
    if not pre_relacoes:
        return resultado

    componentes_aprovados, possui_historico = componentes_aprovados_aluno(
        aluno.id,
        excluir_turma_id=getattr(turma, "id", None),
    )
    if not possui_historico:
        resultado.avisos.append(
            "Não há histórico acadêmico componentizado suficiente para validar todos os pré-requisitos desta matrícula."
        )
        return resultado

    equivalencia_map = _build_equivalencia_map(int(matriz_id))
    faltantes_ids: set[int] = set()
    for rel in pre_relacoes:
        requerido_id = int(rel.origem.componente_id)
        if not _satisfaz_requisito(requerido_id, componentes_aprovados, equivalencia_map):
            faltantes_ids.add(requerido_id)

    if not faltantes_ids:
        return resultado

    nomes = dict(
        MatrizComponente.objects.filter(matriz_id=matriz_id, componente_id__in=faltantes_ids)
        .values_list("componente_id", "componente__nome")
    )
    faltantes_nomes = sorted({nomes.get(comp_id, f"Componente #{comp_id}") for comp_id in faltantes_ids})

    resultado.bloqueado = True
    resultado.pendencias.append(
        "Pré-requisitos pendentes para matrícula: " + ", ".join(faltantes_nomes[:6])
    )
    if len(faltantes_nomes) > 6:
        resultado.pendencias.append(f"... e mais {len(faltantes_nomes) - 6} componente(s).")
    resultado.detalhes["pre_requisitos_pendentes"] = faltantes_nomes
    return resultado



def avaliar_requisitos_lancamento_componente(
    *,
    turma: Turma,
    componente_id: int,
    aula_id: int | None = None,
) -> ResultadoRequisitos:
    resultado = ResultadoRequisitos()

    matriz_id = getattr(turma, "matriz_curricular_id", None)
    if not matriz_id:
        return resultado

    destino = (
        MatrizComponente.objects.select_related("componente")
        .filter(matriz_id=matriz_id, componente_id=componente_id, ativo=True)
        .first()
    )
    if not destino:
        return resultado

    pre_relacoes = list(
        MatrizComponenteRelacao.objects.select_related("origem", "origem__componente")
        .filter(
            ativo=True,
            tipo=MatrizComponenteRelacao.Tipo.PRE_REQUISITO,
            origem__matriz_id=matriz_id,
            destino_id=destino.id,
            origem__ativo=True,
        )
    )
    co_relacoes = list(
        MatrizComponenteRelacao.objects.select_related("origem", "origem__componente")
        .filter(
            ativo=True,
            tipo=MatrizComponenteRelacao.Tipo.CO_REQUISITO,
            origem__matriz_id=matriz_id,
            destino_id=destino.id,
            origem__ativo=True,
        )
    )

    if not pre_relacoes and not co_relacoes:
        return resultado

    matriculas_ativas = list(
        Matricula.objects.select_related("aluno")
        .filter(turma=turma, situacao=Matricula.Situacao.ATIVA)
    )
    if not matriculas_ativas:
        return resultado

    equivalencia_map = _build_equivalencia_map(int(matriz_id))

    faltantes_por_aluno: dict[int, list[str]] = {}
    for matricula in matriculas_ativas:
        aprovados, possui_historico = componentes_aprovados_aluno(
            matricula.aluno_id,
            excluir_turma_id=getattr(turma, "id", None),
        )
        if not possui_historico:
            continue

        faltantes_aluno: list[str] = []
        for rel in pre_relacoes:
            requerido_id = int(rel.origem.componente_id)
            if _satisfaz_requisito(requerido_id, aprovados, equivalencia_map):
                continue
            faltantes_aluno.append(rel.origem.componente.nome)

        if faltantes_aluno:
            faltantes_por_aluno[matricula.aluno_id] = sorted(set(faltantes_aluno))

    if faltantes_por_aluno:
        nomes_alunos = dict(Aluno.objects.filter(id__in=faltantes_por_aluno.keys()).values_list("id", "nome"))
        detalhes = []
        for aluno_id, faltantes in faltantes_por_aluno.items():
            detalhes.append(f"{nomes_alunos.get(aluno_id, f'Aluno #{aluno_id}')}: {', '.join(faltantes[:3])}")
        resultado.bloqueado = True
        resultado.pendencias.append(
            "Lançamento bloqueado por pré-requisito pendente em alunos da turma."
        )
        resultado.pendencias.extend(detalhes[:6])
        if len(detalhes) > 6:
            resultado.pendencias.append(f"... e mais {len(detalhes) - 6} aluno(s).")
        resultado.detalhes["alunos_pendentes_pre_requisito"] = detalhes

    if co_relacoes:
        co_componentes_ids = {int(rel.origem.componente_id) for rel in co_relacoes if rel.origem_id}
        aulas_co_qs = Aula.objects.filter(diario__turma=turma, componente_id__in=co_componentes_ids)
        if aula_id:
            aulas_co_qs = aulas_co_qs.exclude(pk=aula_id)
        componentes_com_lancamento = set(aulas_co_qs.values_list("componente_id", flat=True))
        faltantes_co = co_componentes_ids - componentes_com_lancamento
        if faltantes_co:
            nomes_co = dict(
                MatrizComponente.objects.filter(matriz_id=matriz_id, componente_id__in=faltantes_co).values_list(
                    "componente_id", "componente__nome"
                )
            )
            faltantes_nomes = sorted({nomes_co.get(cid, f"Componente #{cid}") for cid in faltantes_co})

            aulas_atual_qs = Aula.objects.filter(diario__turma=turma, componente_id=componente_id)
            if aula_id:
                aulas_atual_qs = aulas_atual_qs.exclude(pk=aula_id)

            if aulas_atual_qs.exists():
                resultado.bloqueado = True
                resultado.pendencias.append(
                    "Co-requisito pendente sem lançamento correspondente: " + ", ".join(faltantes_nomes[:4])
                )
            else:
                resultado.avisos.append(
                    "Co-requisito pendente para lançamento conjunto: " + ", ".join(faltantes_nomes[:4])
                )

    return resultado


def _resolve_municipio_from_turma(turma: Turma):
    unidade = getattr(turma, "unidade", None)
    secretaria = getattr(unidade, "secretaria", None)
    return getattr(secretaria, "municipio", None)


def registrar_override_requisitos_matricula(
    *,
    usuario,
    aluno: Aluno,
    turma: Turma,
    justificativa: str,
    pendencias: list[str] | None = None,
    origem: str = "MATRICULA",
):
    municipio = _resolve_municipio_from_turma(turma)
    if municipio is None:
        return None
    return registrar_auditoria(
        municipio=municipio,
        modulo="EDUCACAO",
        evento="OVERRIDE_REQUISITOS_MATRICULA",
        entidade="MATRICULA",
        entidade_id=f"{aluno.id}:{turma.id}",
        usuario=usuario,
        antes={
            "bloqueios": list(pendencias or []),
            "aluno_id": aluno.id,
            "turma_id": turma.id,
        },
        depois={
            "override": True,
            "origem": origem,
            "justificativa": (justificativa or "").strip(),
        },
        observacao=(f"Override matrícula ({origem}): {(justificativa or '').strip()}"[:200]),
    )


def registrar_override_requisitos_lancamento(
    *,
    usuario,
    turma: Turma,
    componente_id: int,
    aula_id: int | None,
    justificativa: str,
    pendencias: list[str] | None = None,
    origem: str = "AULA_FORM",
):
    municipio = _resolve_municipio_from_turma(turma)
    if municipio is None:
        return None
    return registrar_auditoria(
        municipio=municipio,
        modulo="EDUCACAO",
        evento="OVERRIDE_REQUISITOS_LANCAMENTO",
        entidade="AULA",
        entidade_id=str(aula_id or f"turma:{turma.id}:comp:{componente_id}"),
        usuario=usuario,
        antes={
            "bloqueios": list(pendencias or []),
            "turma_id": turma.id,
            "componente_id": int(componente_id),
        },
        depois={
            "override": True,
            "origem": origem,
            "justificativa": (justificativa or "").strip(),
        },
        observacao=(f"Override lançamento ({origem}): {(justificativa or '').strip()}"[:200]),
    )
