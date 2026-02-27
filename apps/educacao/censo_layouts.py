from __future__ import annotations

from typing import Callable

from django.db.models import Q


RuleFn = Callable[[dict], int]

DATASET_CHOICES = (
    ("matriculas", "Matrículas"),
    ("alunos", "Alunos"),
    ("turmas", "Turmas"),
    ("escolas", "Escolas"),
    ("docentes", "Docentes"),
)
DATASET_KEYS = {k for k, _ in DATASET_CHOICES}

SUPPORTED_LAYOUTS = (2026, 2027)
DEFAULT_LAYOUT = SUPPORTED_LAYOUTS[-1]


def resolve_layout(requested: int, fallback: int) -> int:
    if requested in SUPPORTED_LAYOUTS:
        return requested
    if fallback in SUPPORTED_LAYOUTS:
        return fallback
    return DEFAULT_LAYOUT


def resolve_dataset(dataset: str) -> str:
    return dataset if dataset in DATASET_KEYS else "matriculas"


def _rows_matriculas_nome(ctx):
    return ctx["matriculas_qs"].filter(Q(aluno__nome__isnull=True) | Q(aluno__nome="")).count()


def _rows_matriculas_cpf(ctx):
    return ctx["matriculas_qs"].filter(Q(aluno__cpf_last4__isnull=True) | Q(aluno__cpf_last4="")).count()


def _rows_matriculas_turma(ctx):
    return ctx["matriculas_qs"].filter(Q(turma__nome__isnull=True) | Q(turma__nome="")).count()


def _rows_matriculas_inep(ctx):
    return ctx["matriculas_qs"].filter(Q(turma__unidade__codigo_inep__isnull=True) | Q(turma__unidade__codigo_inep="")).count()


def _rows_matriculas_data(ctx):
    return ctx["matriculas_qs"].filter(data_matricula__isnull=True).count()


def _rows_aluno_nome(ctx):
    return ctx["alunos_qs"].filter(Q(nome__isnull=True) | Q(nome="")).count()


def _rows_aluno_cpf(ctx):
    return ctx["alunos_qs"].filter(Q(cpf_last4__isnull=True) | Q(cpf_last4="")).count()


def _rows_aluno_nasc(ctx):
    return ctx["alunos_qs"].filter(data_nascimento__isnull=True).count()


def _rows_aluno_mae(ctx):
    return ctx["alunos_qs"].filter(Q(nome_mae__isnull=True) | Q(nome_mae="")).count()


def _rows_turma_nome(ctx):
    return ctx["turmas_qs"].filter(Q(nome__isnull=True) | Q(nome="")).count()


def _rows_turma_turno(ctx):
    return ctx["turmas_qs"].filter(Q(turno__isnull=True) | Q(turno="")).count()


def _rows_turma_inep(ctx):
    return ctx["turmas_qs"].filter(Q(unidade__codigo_inep__isnull=True) | Q(unidade__codigo_inep="")).count()


def _rows_turma_modalidade(ctx):
    return ctx["turmas_qs"].filter(Q(modalidade__isnull=True) | Q(modalidade="")).count()


def _rows_turma_etapa(ctx):
    return ctx["turmas_qs"].filter(Q(etapa__isnull=True) | Q(etapa="")).count()


def _rows_escola_nome(ctx):
    return ctx["unidades_qs"].filter(Q(nome__isnull=True) | Q(nome="")).count()


def _rows_escola_inep(ctx):
    return ctx["unidades_qs"].filter(Q(codigo_inep__isnull=True) | Q(codigo_inep="")).count()


def _rows_escola_secretaria(ctx):
    return ctx["unidades_qs"].filter(secretaria__isnull=True).count()


def _rows_docente_usuario(ctx):
    return ctx["docentes_qs"].filter(Q(username__isnull=True) | Q(username="")).count()


def _rows_docente_email(ctx):
    return ctx["docentes_qs"].filter(Q(email__isnull=True) | Q(email="")).count()


LAYOUT_RULES: dict[int, dict[str, list[tuple[str, RuleFn]]]] = {
    2026: {
        "matriculas": [
            ("Aluno sem nome", _rows_matriculas_nome),
            ("Aluno sem CPF", _rows_matriculas_cpf),
            ("Matrícula sem turma", _rows_matriculas_turma),
            ("Unidade da matrícula sem INEP", _rows_matriculas_inep),
            ("Matrícula sem data", _rows_matriculas_data),
        ],
        "alunos": [
            ("Aluno sem nome", _rows_aluno_nome),
            ("Aluno sem CPF", _rows_aluno_cpf),
            ("Aluno sem data de nascimento", _rows_aluno_nasc),
        ],
        "turmas": [
            ("Turma sem nome", _rows_turma_nome),
            ("Turma sem turno", _rows_turma_turno),
            ("Turma sem modalidade", _rows_turma_modalidade),
            ("Turma sem etapa", _rows_turma_etapa),
            ("Turma com unidade sem INEP", _rows_turma_inep),
        ],
        "escolas": [
            ("Escola sem nome", _rows_escola_nome),
            ("Escola sem código INEP", _rows_escola_inep),
        ],
        "docentes": [
            ("Docente sem usuário", _rows_docente_usuario),
        ],
    },
    2027: {
        "matriculas": [
            ("Aluno sem nome", _rows_matriculas_nome),
            ("Aluno sem CPF", _rows_matriculas_cpf),
            ("Matrícula sem turma", _rows_matriculas_turma),
            ("Unidade da matrícula sem INEP", _rows_matriculas_inep),
            ("Matrícula sem data", _rows_matriculas_data),
        ],
        "alunos": [
            ("Aluno sem nome", _rows_aluno_nome),
            ("Aluno sem CPF", _rows_aluno_cpf),
            ("Aluno sem data de nascimento", _rows_aluno_nasc),
            ("Aluno sem nome da mãe", _rows_aluno_mae),
        ],
        "turmas": [
            ("Turma sem nome", _rows_turma_nome),
            ("Turma sem turno", _rows_turma_turno),
            ("Turma sem modalidade", _rows_turma_modalidade),
            ("Turma sem etapa", _rows_turma_etapa),
            ("Turma com unidade sem INEP", _rows_turma_inep),
        ],
        "escolas": [
            ("Escola sem nome", _rows_escola_nome),
            ("Escola sem código INEP", _rows_escola_inep),
            ("Escola sem secretaria vinculada", _rows_escola_secretaria),
        ],
        "docentes": [
            ("Docente sem usuário", _rows_docente_usuario),
            ("Docente sem e-mail", _rows_docente_email),
        ],
    },
}


def build_layout_validation_rows(layout: int, dataset: str, *, ctx: dict) -> list[dict]:
    rules = LAYOUT_RULES.get(layout, {}).get(dataset, [])
    rows = []
    for label, fn in rules:
        pending = int(fn(ctx))
        rows.append(
            {
                "cells": [
                    {"text": label},
                    {"text": str(pending)},
                    {"text": "OK" if pending == 0 else "Pendente"},
                ]
            }
        )
    return rows
