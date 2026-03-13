from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import os
import re
import unicodedata

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.almoxarifado.models import AlmoxarifadoMovimento
from apps.core.services_auditoria import registrar_auditoria

from .models_beneficios import (
    BeneficioEdital,
    BeneficioEditalDocumento,
    BeneficioEditalInscricao,
    BeneficioEditalInscricaoDocumento,
    BeneficioEditalCriterio,
    BeneficioEntrega,
    BeneficioEntregaItem,
    BeneficioRecorrenciaCiclo,
    BeneficioRecorrenciaPlano,
    BeneficioTipo,
)


def _to_dec(value) -> Decimal:
    return Decimal(str(value or "0"))


def _movimentar_estoque_saida(*, entrega: BeneficioEntrega, item_entrega: BeneficioEntregaItem, user) -> None:
    if not item_entrega.item_estoque_id or _to_dec(item_entrega.quantidade_entregue) <= 0:
        return
    estoque_item = item_entrega.item_estoque
    qtd = _to_dec(item_entrega.quantidade_entregue)
    if _to_dec(estoque_item.saldo_atual) < qtd:
        raise ValueError(f"Saldo insuficiente para o item {estoque_item.nome}.")

    movimento = AlmoxarifadoMovimento.objects.create(
        municipio=entrega.municipio,
        item=estoque_item,
        tipo=AlmoxarifadoMovimento.Tipo.SAIDA,
        data_movimento=timezone.localdate(),
        quantidade=qtd,
        valor_unitario=estoque_item.valor_medio,
        documento=f"BEN-ENT-{entrega.pk}",
        observacao=f"Saída por entrega de benefício #{entrega.pk}",
        criado_por=user,
    )
    estoque_item.saldo_atual = max(Decimal("0"), _to_dec(estoque_item.saldo_atual) - qtd)
    estoque_item.save(update_fields=["saldo_atual", "atualizado_em"])

    registrar_auditoria(
        municipio=entrega.municipio,
        modulo="EDUCACAO",
        evento="BENEFICIO_ESTOQUE_SAIDA",
        entidade="AlmoxarifadoMovimento",
        entidade_id=movimento.pk,
        usuario=user,
        depois={
            "entrega_id": entrega.pk,
            "item_estoque_id": estoque_item.pk,
            "quantidade": str(qtd),
        },
    )


def _movimentar_estoque_estorno(*, entrega: BeneficioEntrega, item_entrega: BeneficioEntregaItem, user) -> None:
    if not item_entrega.item_estoque_id or _to_dec(item_entrega.quantidade_entregue) <= 0:
        return
    estoque_item = item_entrega.item_estoque
    qtd = _to_dec(item_entrega.quantidade_entregue)
    movimento = AlmoxarifadoMovimento.objects.create(
        municipio=entrega.municipio,
        item=estoque_item,
        tipo=AlmoxarifadoMovimento.Tipo.ENTRADA,
        data_movimento=timezone.localdate(),
        quantidade=qtd,
        valor_unitario=estoque_item.valor_medio,
        documento=f"BEN-EST-{entrega.pk}",
        observacao=f"Estorno de entrega de benefício #{entrega.pk}",
        criado_por=user,
    )
    estoque_item.saldo_atual = _to_dec(estoque_item.saldo_atual) + qtd
    estoque_item.save(update_fields=["saldo_atual", "atualizado_em"])

    registrar_auditoria(
        municipio=entrega.municipio,
        modulo="EDUCACAO",
        evento="BENEFICIO_ESTOQUE_ESTORNO",
        entidade="AlmoxarifadoMovimento",
        entidade_id=movimento.pk,
        usuario=user,
        depois={
            "entrega_id": entrega.pk,
            "item_estoque_id": estoque_item.pk,
            "quantidade": str(qtd),
        },
    )


def _period_start_by_periodicidade(periodicidade: str, today: date) -> date | None:
    if periodicidade == BeneficioTipo.Periodicidade.UNICA:
        return date(1900, 1, 1)
    if periodicidade == BeneficioTipo.Periodicidade.ANUAL:
        return date(today.year, 1, 1)
    if periodicidade == BeneficioTipo.Periodicidade.MENSAL:
        return date(today.year, today.month, 1)
    if periodicidade == BeneficioTipo.Periodicidade.BIMESTRAL:
        start_month = today.month if today.month % 2 == 1 else today.month - 1
        return date(today.year, start_month, 1)
    return None


def validar_duplicidade_entrega(*, entrega: BeneficioEntrega) -> tuple[bool, str]:
    beneficio = entrega.beneficio
    if beneficio.permite_segunda_via or entrega.segunda_via:
        return True, ""

    dt = timezone.localtime(entrega.data_hora).date()
    start = _period_start_by_periodicidade(beneficio.periodicidade, dt)
    qs = BeneficioEntrega.objects.filter(
        municipio=entrega.municipio,
        aluno=entrega.aluno,
        beneficio=beneficio,
        status=BeneficioEntrega.Status.ENTREGUE,
    ).exclude(pk=entrega.pk)

    if start:
        qs = qs.filter(data_hora__date__gte=start)
    if qs.exists():
        return False, "Entrega duplicada para o período configurado no benefício."
    return True, ""


@transaction.atomic
def confirmar_entrega(*, entrega: BeneficioEntrega, user) -> BeneficioEntrega:
    if entrega.status == BeneficioEntrega.Status.ESTORNADO:
        raise ValueError("Entrega estornada não pode ser confirmada.")

    ok, msg = validar_duplicidade_entrega(entrega=entrega)
    if not ok:
        raise ValueError(msg)

    beneficio = entrega.beneficio
    if beneficio.exige_assinatura and not entrega.assinatura_confirmada:
        raise ValueError("Este benefício exige assinatura para confirmação.")
    if beneficio.exige_foto and not entrega.foto_entrega:
        raise ValueError("Este benefício exige foto da entrega.")
    if beneficio.exige_justificativa and not (entrega.justificativa or "").strip():
        raise ValueError("Este benefício exige justificativa.")

    itens = list(entrega.itens.select_related("item_estoque"))
    if not itens:
        raise ValueError("A entrega não possui itens para confirmação.")

    for item in itens:
        if item.pendente or _to_dec(item.quantidade_entregue) <= 0:
            continue
        _movimentar_estoque_saida(entrega=entrega, item_entrega=item, user=user)

    entrega.status = BeneficioEntrega.Status.ENTREGUE
    entrega.responsavel_entrega = user
    entrega.data_hora = timezone.now()
    entrega.save(update_fields=["status", "responsavel_entrega", "data_hora", "atualizado_em"])

    if entrega.campanha_id:
        entrega.campanha.alunos.filter(aluno=entrega.aluno).update(status="ENTREGUE")
    if entrega.ciclo_recorrencia_id:
        entrega.ciclo_recorrencia.status = BeneficioRecorrenciaCiclo.Status.ENTREGUE
        entrega.ciclo_recorrencia.entrega = entrega
        entrega.ciclo_recorrencia.responsavel_confirmacao = user
        entrega.ciclo_recorrencia.save(
            update_fields=["status", "entrega", "responsavel_confirmacao", "atualizado_em"]
        )

    registrar_auditoria(
        municipio=entrega.municipio,
        modulo="EDUCACAO",
        evento="BENEFICIO_ENTREGA_CONFIRMADA",
        entidade="BeneficioEntrega",
        entidade_id=entrega.pk,
        usuario=user,
        depois={"status": entrega.status, "aluno_id": entrega.aluno_id, "beneficio_id": entrega.beneficio_id},
    )
    return entrega


@transaction.atomic
def estornar_entrega(*, entrega: BeneficioEntrega, user, motivo: str) -> BeneficioEntrega:
    if entrega.status != BeneficioEntrega.Status.ENTREGUE:
        raise ValueError("Somente entregas confirmadas podem ser estornadas.")
    if not (motivo or "").strip():
        raise ValueError("Informe o motivo do estorno.")

    for item in entrega.itens.select_related("item_estoque"):
        if item.pendente or _to_dec(item.quantidade_entregue) <= 0:
            continue
        _movimentar_estoque_estorno(entrega=entrega, item_entrega=item, user=user)

    entrega.status = BeneficioEntrega.Status.ESTORNADO
    entrega.estornado_em = timezone.now()
    entrega.estornado_por = user
    entrega.justificativa = f"{(entrega.justificativa or '').strip()}\nEstorno: {motivo}".strip()
    entrega.save(update_fields=["status", "estornado_em", "estornado_por", "justificativa", "atualizado_em"])

    if entrega.campanha_id:
        entrega.campanha.alunos.filter(aluno=entrega.aluno).update(status="PENDENTE")
    if entrega.ciclo_recorrencia_id:
        entrega.ciclo_recorrencia.status = BeneficioRecorrenciaCiclo.Status.ATRASADA
        entrega.ciclo_recorrencia.motivo = f"Estornada: {motivo}"
        entrega.ciclo_recorrencia.save(update_fields=["status", "motivo", "atualizado_em"])

    registrar_auditoria(
        municipio=entrega.municipio,
        modulo="EDUCACAO",
        evento="BENEFICIO_ENTREGA_ESTORNADA",
        entidade="BeneficioEntrega",
        entidade_id=entrega.pk,
        usuario=user,
        depois={"status": entrega.status, "motivo": motivo[:280]},
    )
    return entrega


def gerar_ciclos_recorrencia(*, plano: BeneficioRecorrenciaPlano, force: bool = False) -> int:
    if plano.status != BeneficioRecorrenciaPlano.Status.ATIVA and not force:
        return 0

    if plano.ciclos.exists() and not force:
        return 0

    if force:
        plano.ciclos.all().delete()

    freq = plano.frequencia
    data_cursor = plano.data_inicio
    max_ciclos = plano.numero_ciclos or 12
    created = 0

    for idx in range(1, max_ciclos + 1):
        if plano.data_fim and data_cursor > plano.data_fim:
            break
        BeneficioRecorrenciaCiclo.objects.create(
            plano=plano,
            numero=idx,
            data_prevista=data_cursor,
            status=BeneficioRecorrenciaCiclo.Status.PREVISTA,
        )
        created += 1
        if freq == BeneficioRecorrenciaPlano.Frequencia.SEMANAL:
            data_cursor = data_cursor + timedelta(days=7)
        elif freq == BeneficioRecorrenciaPlano.Frequencia.QUINZENAL:
            data_cursor = data_cursor + timedelta(days=15)
        elif freq == BeneficioRecorrenciaPlano.Frequencia.INTERVALO_DIAS:
            data_cursor = data_cursor + timedelta(days=max(1, int(plano.intervalo_dias or 30)))
        else:
            data_cursor = data_cursor + timedelta(days=30)
    return created


def _norm_text(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).lower().strip()


def _slug_token(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _norm_text(value))
    return slug.strip("_") or "criterio"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y", "on"}


def _coerce_scalar(value):
    if isinstance(value, (int, float, Decimal, bool)):
        return value
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    if low in {"true", "false", "sim", "nao", "não"}:
        return _as_bool(low in {"true", "sim"})
    try:
        return Decimal(raw.replace(",", "."))
    except Exception:
        return raw


def _resolve_ctx_path(ctx: dict, path: str):
    cur = ctx
    for part in str(path or "").split("."):
        part = part.strip()
        if not part:
            continue
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur.get(part)
    return cur


def _compare_rule(left, op: str, right) -> bool:
    if op == "contains":
        return _norm_text(right) in _norm_text(left)
    if op == "in":
        values = [x.strip() for x in str(right or "").split(",") if x.strip()]
        left_norm = _norm_text(left)
        return any(_norm_text(v) == left_norm for v in values)

    left_c = _coerce_scalar(left)
    right_c = _coerce_scalar(right)
    if op == "==":
        return str(left_c).lower() == str(right_c).lower()
    if op == "!=":
        return str(left_c).lower() != str(right_c).lower()
    if op in {">", ">=", "<", "<="}:
        try:
            ldec = Decimal(str(left_c))
            rdec = Decimal(str(right_c))
        except Exception:
            return False
        if op == ">":
            return ldec > rdec
        if op == ">=":
            return ldec >= rdec
        if op == "<":
            return ldec < rdec
        return ldec <= rdec
    return False


def _eval_rule(rule: str, ctx: dict) -> bool | None:
    raw = (rule or "").strip()
    if not raw:
        return None
    m = re.match(r"^([\w\.\-]+)\s*(==|!=|>=|<=|>|<|contains|in)\s*(.+)$", raw, flags=re.IGNORECASE)
    if not m:
        return None
    left_path, op, right_raw = m.group(1), m.group(2).lower(), m.group(3).strip()
    left = _resolve_ctx_path(ctx, left_path)
    if left is None:
        return False
    return _compare_rule(left, op, right_raw)


def _build_snapshot_aluno(*, aluno, edital: BeneficioEdital) -> dict:
    from apps.educacao.models import CarteiraEstudantil, Matricula, AlunoDocumento

    matricula = (
        Matricula.objects.select_related("turma", "turma__unidade", "turma__unidade__secretaria")
        .filter(aluno=aluno)
        .order_by("-id")
        .first()
    )
    turma = getattr(matricula, "turma", None)
    unidade = getattr(turma, "unidade", None)
    secretaria = getattr(unidade, "secretaria", None)

    doc_qs = AlunoDocumento.objects.filter(aluno=aluno, ativo=True, arquivo__isnull=False)
    has_carteira = CarteiraEstudantil.objects.filter(aluno=aluno, ativa=True).exists()
    has_decl_vinculo = doc_qs.filter(tipo=AlunoDocumento.Tipo.DECLARACAO, titulo__icontains="vinculo").exists()

    saude_data = {
        "possui_cadastro": False,
        "programa": "",
        "cartao_sus": "",
        "vulnerabilidades": "",
    }
    try:
        from apps.saude.models import PacienteSaude

        paciente = (
            PacienteSaude.objects.select_related("programa")
            .filter(aluno=aluno, ativo=True)
            .order_by("-id")
            .first()
        )
        if paciente:
            saude_data = {
                "possui_cadastro": True,
                "programa": getattr(paciente.programa, "nome", "") or "",
                "cartao_sus": paciente.cartao_sus or "",
                "vulnerabilidades": paciente.vulnerabilidades or "",
            }
    except Exception:
        pass

    return {
        "area_edital": edital.area,
        "aluno": {
            "id": aluno.pk,
            "nome": aluno.nome or "",
            "cpf": aluno.cpf or "",
            "nis": aluno.nis or "",
            "ativo": bool(aluno.ativo),
            "nome_mae": aluno.nome_mae or "",
            "telefone": aluno.telefone or "",
            "data_nascimento": aluno.data_nascimento.isoformat() if aluno.data_nascimento else "",
        },
        "matricula": {
            "situacao": getattr(matricula, "situacao", "") or "",
            "turma": getattr(turma, "nome", "") or "",
            "ano_letivo": getattr(turma, "ano_letivo", None),
            "turno": getattr(turma, "turno", "") or "",
            "unidade": getattr(unidade, "nome", "") or "",
            "secretaria": getattr(secretaria, "nome", "") or "",
        },
        "documentos": {
            "total": doc_qs.count(),
            "carteira_estudantil": bool(has_carteira),
            "declaracao_vinculo": bool(has_decl_vinculo),
        },
        "saude": saude_data,
    }


def _match_aluno_documento(*, aluno, requisito_nome: str):
    from apps.educacao.models import AlunoDocumento

    docs = (
        AlunoDocumento.objects.filter(aluno=aluno, ativo=True, arquivo__isnull=False)
        .exclude(arquivo="")
        .order_by("-criado_em", "-id")
    )
    if not docs.exists():
        return None
    nome_n = _norm_text(requisito_nome)

    def _contains_any(text: str, terms: list[str]) -> bool:
        return any(t in text for t in terms)

    if _contains_any(nome_n, ["carteira", "estudantil"]):
        found = docs.filter(titulo__icontains="carteira estudantil").first()
        if found:
            return found
    if _contains_any(nome_n, ["vinculo", "matricula", "declara"]):
        found = docs.filter(tipo=AlunoDocumento.Tipo.DECLARACAO).first()
        if found:
            return found
    if "cpf" in nome_n:
        found = docs.filter(tipo=AlunoDocumento.Tipo.CPF).first()
        if found:
            return found
    if "rg" in nome_n:
        found = docs.filter(tipo=AlunoDocumento.Tipo.RG).first()
        if found:
            return found
    if _contains_any(nome_n, ["residencia", "endereco", "comprovante"]):
        found = docs.filter(tipo=AlunoDocumento.Tipo.COMPROVANTE_RESIDENCIA).first()
        if found:
            return found
    if "laudo" in nome_n:
        found = docs.filter(tipo=AlunoDocumento.Tipo.LAUDO).first()
        if found:
            return found

    terms = [t for t in re.split(r"\W+", nome_n) if len(t) >= 4]
    for doc in docs:
        title_n = _norm_text(doc.titulo)
        if not terms:
            return doc
        score = sum(1 for term in terms if term in title_n)
        if score >= max(1, len(terms) // 2):
            return doc
    return docs.first()


def _match_saude_anexo(*, aluno, requisito_nome: str):
    try:
        from apps.saude.models import AnexoAtendimentoSaude
    except Exception:
        return None
    anexos = (
        AnexoAtendimentoSaude.objects.filter(atendimento__aluno=aluno)
        .exclude(arquivo="")
        .order_by("-criado_em", "-id")
    )
    if not anexos.exists():
        return None
    nome_n = _norm_text(requisito_nome)
    terms = [t for t in re.split(r"\W+", nome_n) if len(t) >= 4]
    if not terms:
        return anexos.first()
    for anexo in anexos:
        title_n = _norm_text(anexo.titulo)
        if any(term in title_n for term in terms):
            return anexo
    return anexos.first()


def _clone_field_file(field_file):
    if not field_file:
        return None
    try:
        field_file.open("rb")
        data = field_file.read()
    finally:
        try:
            field_file.close()
        except Exception:
            pass
    base = os.path.basename(getattr(field_file, "name", "") or "") or f"arquivo_{timezone.now().timestamp()}.bin"
    return ContentFile(data, name=base)


def _save_inscricao_documento(
    *,
    inscricao: BeneficioEditalInscricao,
    requisito: BeneficioEditalDocumento | None,
    descricao: str,
    arquivo_file,
    aprovado=None,
    observacao: str = "",
) -> BeneficioEditalInscricaoDocumento | None:
    if not arquivo_file:
        return None
    obj = BeneficioEditalInscricaoDocumento.objects.create(
        inscricao=inscricao,
        requisito=requisito,
        descricao=(descricao or "")[:160],
        aprovado=aprovado,
        observacao=(observacao or "")[:2000],
    )
    file_name = getattr(arquivo_file, "name", "") or f"doc_inscricao_{inscricao.pk}.bin"
    obj.arquivo.save(os.path.basename(file_name), arquivo_file, save=False)
    obj.save()
    return obj


@transaction.atomic
def registrar_inscricao_com_criterios(
    *,
    edital: BeneficioEdital,
    aluno,
    escola,
    turma,
    justificativa: str,
    usar_documentos_cadastro: bool,
    respostas_criterios: dict[int, dict],
    uploads_documentos: dict[int, object],
    uploads_criterios: dict[int, object],
    user,
) -> tuple[BeneficioEditalInscricao, dict]:
    snapshot = _build_snapshot_aluno(aluno=aluno, edital=edital)
    ctx = dict(snapshot)
    criterios = list(edital.criterios.filter(ativo=True).order_by("ordem", "id"))
    docs_req = list(edital.documentos.order_by("ordem", "id"))

    pontuacao_total = Decimal("0")
    eliminatorios_ok = True
    pendencias_documentos: list[str] = []
    criterios_resultado: list[dict] = []
    req_resultado: list[dict] = []

    for criterio in criterios:
        resp = respostas_criterios.get(criterio.pk, {})
        marcado = _as_bool(resp.get("marcado"))
        valor = str(resp.get("valor") or "").strip()
        fonte = _norm_text(criterio.fonte_dado or "declaracao")
        regra = (criterio.regra or "").strip()
        token = _slug_token(criterio.nome)

        local_ctx = dict(ctx)
        local_ctx["resposta"] = {"valor": valor, "marcado": marcado}
        rule_result = _eval_rule(regra, local_ctx)
        if fonte in {"cadastro", "sistema", "auto", "saude", "educacao"}:
            atendeu = bool(rule_result) if rule_result is not None else False
        else:
            atendeu = bool(rule_result) if rule_result is not None else marcado

        criterio_doc_file = uploads_criterios.get(criterio.pk)
        criterio_doc_origem = "upload" if criterio_doc_file else ""
        if not criterio_doc_file and criterio.exige_comprovacao and usar_documentos_cadastro:
            doc_cadastro = _match_aluno_documento(aluno=aluno, requisito_nome=criterio.nome)
            if doc_cadastro and doc_cadastro.arquivo:
                criterio_doc_file = _clone_field_file(doc_cadastro.arquivo)
                criterio_doc_origem = "cadastro_educacao"
            else:
                anexo_saude = _match_saude_anexo(aluno=aluno, requisito_nome=criterio.nome)
                if anexo_saude and anexo_saude.arquivo:
                    criterio_doc_file = _clone_field_file(anexo_saude.arquivo)
                    criterio_doc_origem = "cadastro_saude"
        if criterio.exige_comprovacao and not criterio_doc_file:
            atendeu = False
            pendencias_documentos.append(f"Comprovação do critério: {criterio.nome}")

        pontuado = Decimal("0")
        if criterio.tipo == BeneficioEditalCriterio.Tipo.PONTUACAO and atendeu:
            pontuado = Decimal(str(criterio.peso or 0))
            pontuacao_total += pontuado
        if criterio.tipo == BeneficioEditalCriterio.Tipo.ELIMINATORIO and not atendeu:
            eliminatorios_ok = False

        if criterio_doc_file:
            uploads_criterios[criterio.pk] = criterio_doc_file

        criterios_resultado.append(
            {
                "id": criterio.pk,
                "token": token,
                "nome": criterio.nome,
                "fonte_dado": criterio.fonte_dado or "",
                "tipo": criterio.tipo,
                "marcado": marcado,
                "valor": valor,
                "regra": regra,
                "atendeu": bool(atendeu),
                "peso": int(criterio.peso or 0),
                "pontuado": float(pontuado),
                "exige_comprovacao": bool(criterio.exige_comprovacao),
                "comprovacao_origem": criterio_doc_origem,
            }
        )

    for req in docs_req:
        doc_file = uploads_documentos.get(req.pk)
        origem = "upload" if doc_file else ""
        if not doc_file and usar_documentos_cadastro:
            doc_cadastro = _match_aluno_documento(aluno=aluno, requisito_nome=req.nome)
            if doc_cadastro and doc_cadastro.arquivo:
                doc_file = _clone_field_file(doc_cadastro.arquivo)
                origem = "cadastro_educacao"
            else:
                anexo_saude = _match_saude_anexo(aluno=aluno, requisito_nome=req.nome)
                if anexo_saude and anexo_saude.arquivo:
                    doc_file = _clone_field_file(anexo_saude.arquivo)
                    origem = "cadastro_saude"
        if req.obrigatorio and not doc_file:
            pendencias_documentos.append(f"Documento obrigatório: {req.nome}")
        req_resultado.append(
            {
                "id": req.pk,
                "nome": req.nome,
                "obrigatorio": bool(req.obrigatorio),
                "enviado": bool(doc_file),
                "origem": origem,
            }
        )
        if doc_file:
            uploads_documentos[req.pk] = doc_file

    if not eliminatorios_ok:
        status = BeneficioEditalInscricao.Status.INAPTO
    elif pendencias_documentos:
        status = BeneficioEditalInscricao.Status.DOC_PENDENTE
    elif pontuacao_total > 0:
        status = BeneficioEditalInscricao.Status.APTO
    else:
        status = BeneficioEditalInscricao.Status.ENVIADA

    dados_json = {
        "snapshot": snapshot,
        "avaliacao": {
            "pontuacao_total": float(pontuacao_total),
            "eliminatorios_ok": bool(eliminatorios_ok),
            "pendencias_documentos": pendencias_documentos,
            "status_calculado": status,
            "calculado_em": timezone.now().isoformat(),
        },
        "criterios": criterios_resultado,
        "requisitos": req_resultado,
    }

    inscricao, _created = BeneficioEditalInscricao.objects.update_or_create(
        edital=edital,
        aluno=aluno,
        defaults={
            "escola": escola,
            "turma": turma,
            "dados_json": dados_json,
            "status": status,
            "pontuacao": pontuacao_total,
            "justificativa": (justificativa or "").strip(),
            "atualizado_por": user,
            "criado_por": user,
        },
    )

    inscricao.documentos.all().delete()

    for req in docs_req:
        doc_file = uploads_documentos.get(req.pk)
        if not doc_file:
            continue
        _save_inscricao_documento(
            inscricao=inscricao,
            requisito=req,
            descricao=req.nome,
            arquivo_file=doc_file,
            aprovado=None,
            observacao="Anexo incluído automaticamente na inscrição.",
        )

    for criterio in criterios:
        if not criterio.exige_comprovacao:
            continue
        doc_file = uploads_criterios.get(criterio.pk)
        if not doc_file:
            continue
        _save_inscricao_documento(
            inscricao=inscricao,
            requisito=None,
            descricao=f"Comprovação de critério: {criterio.nome}",
            arquivo_file=doc_file,
            aprovado=None,
            observacao="Comprovação vinculada ao critério do edital.",
        )

    registrar_auditoria(
        municipio=edital.municipio,
        modulo="EDUCACAO",
        evento="BENEFICIO_EDITAL_INSCRICAO_PROCESSADA",
        entidade="BeneficioEditalInscricao",
        entidade_id=inscricao.pk,
        usuario=user,
        depois={
            "edital_id": edital.pk,
            "aluno_id": aluno.pk,
            "status": status,
            "pontuacao": str(pontuacao_total),
            "pendencias_documentos": pendencias_documentos,
        },
    )

    return inscricao, {
        "pontuacao_total": pontuacao_total,
        "status": status,
        "pendencias_documentos": pendencias_documentos,
        "eliminatorios_ok": eliminatorios_ok,
    }


@transaction.atomic
def recalcular_inscricao_por_criterios(*, inscricao: BeneficioEditalInscricao, user=None) -> dict:
    edital = inscricao.edital
    aluno = inscricao.aluno
    snapshot = _build_snapshot_aluno(aluno=aluno, edital=edital)
    ctx = dict(snapshot)
    criterios = list(edital.criterios.filter(ativo=True).order_by("ordem", "id"))
    docs_req = list(edital.documentos.order_by("ordem", "id"))

    dados_json = inscricao.dados_json or {}
    anteriores = dados_json.get("criterios") or []
    by_id = {}
    by_token = {}
    for item in anteriores:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        token = item.get("token")
        if cid is not None:
            by_id[str(cid)] = item
        if token:
            by_token[str(token)] = item

    pontuacao_total = Decimal("0")
    eliminatorios_ok = True
    pendencias_documentos: list[str] = []
    criterios_resultado: list[dict] = []
    req_resultado: list[dict] = []

    for criterio in criterios:
        token = _slug_token(criterio.nome)
        anterior = by_id.get(str(criterio.pk)) or by_token.get(token) or {}
        marcado = _as_bool(anterior.get("marcado"))
        valor = str(anterior.get("valor") or "").strip()
        fonte = _norm_text(criterio.fonte_dado or "declaracao")
        regra = (criterio.regra or "").strip()

        local_ctx = dict(ctx)
        local_ctx["resposta"] = {"valor": valor, "marcado": marcado}
        rule_result = _eval_rule(regra, local_ctx)
        if fonte in {"cadastro", "sistema", "auto", "saude", "educacao"}:
            atendeu = bool(rule_result) if rule_result is not None else False
        else:
            atendeu = bool(rule_result) if rule_result is not None else marcado

        criterio_doc_qs = inscricao.documentos.filter(requisito__isnull=True, descricao__icontains=criterio.nome[:60])
        criterio_doc_origem = "inscricao" if criterio_doc_qs.exists() else ""
        if criterio.exige_comprovacao and not criterio_doc_qs.exists():
            atendeu = False
            pendencias_documentos.append(f"Comprovação do critério: {criterio.nome}")

        pontuado = Decimal("0")
        if criterio.tipo == BeneficioEditalCriterio.Tipo.PONTUACAO and atendeu:
            pontuado = Decimal(str(criterio.peso or 0))
            pontuacao_total += pontuado
        if criterio.tipo == BeneficioEditalCriterio.Tipo.ELIMINATORIO and not atendeu:
            eliminatorios_ok = False

        criterios_resultado.append(
            {
                "id": criterio.pk,
                "token": token,
                "nome": criterio.nome,
                "fonte_dado": criterio.fonte_dado or "",
                "tipo": criterio.tipo,
                "marcado": marcado,
                "valor": valor,
                "regra": regra,
                "atendeu": bool(atendeu),
                "peso": int(criterio.peso or 0),
                "pontuado": float(pontuado),
                "exige_comprovacao": bool(criterio.exige_comprovacao),
                "comprovacao_origem": criterio_doc_origem,
            }
        )

    for req in docs_req:
        enviado = inscricao.documentos.filter(requisito=req).exists()
        if req.obrigatorio and not enviado:
            pendencias_documentos.append(f"Documento obrigatório: {req.nome}")
        req_resultado.append(
            {
                "id": req.pk,
                "nome": req.nome,
                "obrigatorio": bool(req.obrigatorio),
                "enviado": bool(enviado),
                "origem": "inscricao" if enviado else "",
            }
        )

    if not eliminatorios_ok:
        status = BeneficioEditalInscricao.Status.INAPTO
    elif pendencias_documentos:
        status = BeneficioEditalInscricao.Status.DOC_PENDENTE
    elif pontuacao_total > 0:
        status = BeneficioEditalInscricao.Status.APTO
    else:
        status = BeneficioEditalInscricao.Status.ENVIADA

    dados_json["snapshot"] = snapshot
    dados_json["avaliacao"] = {
        "pontuacao_total": float(pontuacao_total),
        "eliminatorios_ok": bool(eliminatorios_ok),
        "pendencias_documentos": pendencias_documentos,
        "status_calculado": status,
        "calculado_em": timezone.now().isoformat(),
    }
    dados_json["criterios"] = criterios_resultado
    dados_json["requisitos"] = req_resultado

    inscricao.pontuacao = pontuacao_total
    inscricao.status = status
    inscricao.dados_json = dados_json
    if user is not None:
        inscricao.atualizado_por = user
    inscricao.save(update_fields=["pontuacao", "status", "dados_json", "atualizado_por", "atualizado_em"])

    registrar_auditoria(
        municipio=edital.municipio,
        modulo="EDUCACAO",
        evento="BENEFICIO_EDITAL_INSCRICAO_REPROCESSADA",
        entidade="BeneficioEditalInscricao",
        entidade_id=inscricao.pk,
        usuario=user,
        depois={
            "status": status,
            "pontuacao": str(pontuacao_total),
            "pendencias_documentos": pendencias_documentos,
        },
    )

    return {
        "pontuacao_total": pontuacao_total,
        "status": status,
        "pendencias_documentos": pendencias_documentos,
        "eliminatorios_ok": eliminatorios_ok,
    }
