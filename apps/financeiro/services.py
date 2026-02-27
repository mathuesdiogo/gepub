from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia

from .models import (
    DespEmpenho,
    DespLiquidacao,
    DespPagamento,
    DespPagamentoResto,
    DespRestosPagar,
    FinanceiroContaBancaria,
    FinanceiroLogEvento,
    OrcCreditoAdicional,
    OrcDotacao,
    RecConciliacaoItem,
    RecArrecadacao,
    TesExtratoImportacao,
    TesExtratoItem,
)


def _to_dec(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def registrar_log(*, municipio, evento: str, entidade: str, entidade_id: str, usuario=None, antes=None, depois=None, observacao: str = ""):
    FinanceiroLogEvento.objects.create(
        municipio=municipio,
        evento=evento,
        entidade=entidade,
        entidade_id=str(entidade_id),
        usuario=usuario,
        antes=antes or {},
        depois=depois or {},
        observacao=observacao or "",
    )


@transaction.atomic
def registrar_empenho(empenho: DespEmpenho, *, usuario=None):
    dotacao = OrcDotacao.objects.select_for_update().get(pk=empenho.dotacao_id)

    antes = {
        "valor_empenhado": str(dotacao.valor_empenhado),
        "saldo_disponivel": str(dotacao.saldo_disponivel),
    }

    dotacao.valor_empenhado = _to_dec(dotacao.valor_empenhado) + _to_dec(empenho.valor_empenhado)
    dotacao.save(update_fields=["valor_empenhado", "atualizado_em"])

    registrar_log(
        municipio=empenho.municipio,
        evento="EMPENHO_CRIADO",
        entidade="DespEmpenho",
        entidade_id=str(empenho.pk),
        usuario=usuario,
        antes=antes,
        depois={
            "valor_empenhado": str(dotacao.valor_empenhado),
            "saldo_disponivel": str(dotacao.saldo_disponivel),
            "numero": empenho.numero,
            "valor_empenho": str(empenho.valor_empenhado),
        },
    )
    registrar_auditoria(
        municipio=empenho.municipio,
        modulo="FINANCEIRO",
        evento="EMPENHO_CRIADO",
        entidade="DespEmpenho",
        entidade_id=empenho.pk,
        usuario=usuario,
        antes=antes,
        depois={
            "numero": empenho.numero,
            "valor": str(empenho.valor_empenhado),
            "status": empenho.status,
        },
    )
    publicar_evento_transparencia(
        municipio=empenho.municipio,
        modulo="FINANCEIRO",
        tipo_evento="EMPENHO_CRIADO",
        titulo=f"Empenho {empenho.numero} registrado",
        descricao=f"Fornecedor: {empenho.fornecedor_nome}",
        referencia=empenho.numero,
        valor=empenho.valor_empenhado,
        dados={
            "status": empenho.status,
            "unidade_gestora_id": empenho.unidade_gestora_id,
            "dotacao_id": empenho.dotacao_id,
        },
    )


@transaction.atomic
def registrar_credito_adicional(credito: OrcCreditoAdicional, *, usuario=None):
    dotacao = OrcDotacao.objects.select_for_update().get(pk=credito.dotacao_id)

    antes = {
        "valor_atualizado": str(dotacao.valor_atualizado),
        "saldo_disponivel": str(dotacao.saldo_disponivel),
    }

    dotacao.valor_atualizado = _to_dec(dotacao.valor_atualizado) + _to_dec(credito.valor)
    dotacao.save(update_fields=["valor_atualizado", "atualizado_em"])

    registrar_log(
        municipio=credito.municipio,
        evento="CREDITO_ADICIONAL_REGISTRADO",
        entidade="OrcCreditoAdicional",
        entidade_id=str(credito.pk),
        usuario=usuario,
        antes=antes,
        depois={
            "tipo": credito.tipo,
            "numero_ato": credito.numero_ato,
            "valor_credito": str(credito.valor),
            "valor_atualizado": str(dotacao.valor_atualizado),
            "saldo_disponivel": str(dotacao.saldo_disponivel),
        },
    )
    registrar_auditoria(
        municipio=credito.municipio,
        modulo="FINANCEIRO",
        evento="CREDITO_ADICIONAL_REGISTRADO",
        entidade="OrcCreditoAdicional",
        entidade_id=credito.pk,
        usuario=usuario,
        antes=antes,
        depois={
            "tipo": credito.tipo,
            "numero_ato": credito.numero_ato,
            "valor": str(credito.valor),
        },
    )
    publicar_evento_transparencia(
        municipio=credito.municipio,
        modulo="FINANCEIRO",
        tipo_evento="CREDITO_ADICIONAL",
        titulo=f"Crédito adicional {credito.numero_ato}",
        descricao=f"Tipo: {credito.get_tipo_display()}",
        referencia=credito.numero_ato,
        valor=credito.valor,
        dados={"dotacao_id": credito.dotacao_id},
    )


@transaction.atomic
def registrar_liquidacao(liquidacao: DespLiquidacao, *, usuario=None):
    empenho = DespEmpenho.objects.select_for_update().get(pk=liquidacao.empenho_id)
    dotacao = OrcDotacao.objects.select_for_update().get(pk=empenho.dotacao_id)

    empenho.valor_liquidado = _to_dec(empenho.valor_liquidado) + _to_dec(liquidacao.valor_liquidado)
    if empenho.valor_liquidado > 0:
        empenho.status = DespEmpenho.Status.LIQUIDADO
    empenho.save(update_fields=["valor_liquidado", "status", "atualizado_em"])

    dotacao.valor_liquidado = _to_dec(dotacao.valor_liquidado) + _to_dec(liquidacao.valor_liquidado)
    dotacao.save(update_fields=["valor_liquidado", "atualizado_em"])

    registrar_log(
        municipio=empenho.municipio,
        evento="LIQUIDACAO_REGISTRADA",
        entidade="DespLiquidacao",
        entidade_id=str(liquidacao.pk),
        usuario=usuario,
        depois={
            "empenho": empenho.numero,
            "valor_liquidacao": str(liquidacao.valor_liquidado),
            "valor_liquidado_empenho": str(empenho.valor_liquidado),
        },
    )
    registrar_auditoria(
        municipio=empenho.municipio,
        modulo="FINANCEIRO",
        evento="LIQUIDACAO_REGISTRADA",
        entidade="DespLiquidacao",
        entidade_id=liquidacao.pk,
        usuario=usuario,
        depois={
            "empenho": empenho.numero,
            "valor_liquidacao": str(liquidacao.valor_liquidado),
        },
    )
    publicar_evento_transparencia(
        municipio=empenho.municipio,
        modulo="FINANCEIRO",
        tipo_evento="LIQUIDACAO",
        titulo=f"Liquidação {liquidacao.numero} registrada",
        descricao=f"Empenho: {empenho.numero}",
        referencia=liquidacao.numero,
        valor=liquidacao.valor_liquidado,
        dados={"empenho": empenho.numero},
    )


@transaction.atomic
def registrar_pagamento(pagamento: DespPagamento, *, usuario=None):
    liquidacao = DespLiquidacao.objects.select_for_update().get(pk=pagamento.liquidacao_id)
    empenho = DespEmpenho.objects.select_for_update().get(pk=liquidacao.empenho_id)
    dotacao = OrcDotacao.objects.select_for_update().get(pk=empenho.dotacao_id)

    conta = None
    if pagamento.conta_bancaria_id:
        conta = FinanceiroContaBancaria.objects.select_for_update().get(pk=pagamento.conta_bancaria_id)

    empenho.valor_pago = _to_dec(empenho.valor_pago) + _to_dec(pagamento.valor_pago)
    if empenho.valor_pago >= empenho.valor_liquidado and empenho.valor_pago > 0:
        empenho.status = DespEmpenho.Status.PAGO
    empenho.save(update_fields=["valor_pago", "status", "atualizado_em"])

    dotacao.valor_pago = _to_dec(dotacao.valor_pago) + _to_dec(pagamento.valor_pago)
    dotacao.save(update_fields=["valor_pago", "atualizado_em"])

    if conta is not None and pagamento.status == DespPagamento.Status.PAGO:
        conta.saldo_atual = _to_dec(conta.saldo_atual) - _to_dec(pagamento.valor_pago)
        conta.save(update_fields=["saldo_atual", "atualizado_em"])

    registrar_log(
        municipio=empenho.municipio,
        evento="PAGAMENTO_REGISTRADO",
        entidade="DespPagamento",
        entidade_id=str(pagamento.pk),
        usuario=usuario,
        depois={
            "empenho": empenho.numero,
            "valor_pagamento": str(pagamento.valor_pago),
            "valor_pago_empenho": str(empenho.valor_pago),
            "conta": str(conta.pk) if conta else "",
        },
    )
    registrar_auditoria(
        municipio=empenho.municipio,
        modulo="FINANCEIRO",
        evento="PAGAMENTO_REGISTRADO",
        entidade="DespPagamento",
        entidade_id=pagamento.pk,
        usuario=usuario,
        depois={
            "empenho": empenho.numero,
            "valor_pagamento": str(pagamento.valor_pago),
            "status": pagamento.status,
        },
    )
    publicar_evento_transparencia(
        municipio=empenho.municipio,
        modulo="FINANCEIRO",
        tipo_evento="PAGAMENTO",
        titulo=f"Pagamento registrado para empenho {empenho.numero}",
        descricao=f"Ordem: {pagamento.ordem_pagamento or '-'}",
        referencia=pagamento.ordem_pagamento or str(pagamento.pk),
        valor=pagamento.valor_pago,
        dados={"status": pagamento.status},
    )


def registrar_resto_pagar(resto: DespRestosPagar, *, usuario=None):
    registrar_log(
        municipio=resto.municipio,
        evento="RESTO_PAGAR_INSCRITO",
        entidade="DespRestosPagar",
        entidade_id=str(resto.pk),
        usuario=usuario,
        depois={
            "empenho": resto.empenho.numero,
            "numero_inscricao": resto.numero_inscricao,
            "tipo": resto.tipo,
            "valor_inscrito": str(resto.valor_inscrito),
        },
    )
    registrar_auditoria(
        municipio=resto.municipio,
        modulo="FINANCEIRO",
        evento="RESTO_PAGAR_INSCRITO",
        entidade="DespRestosPagar",
        entidade_id=resto.pk,
        usuario=usuario,
        depois={
            "numero_inscricao": resto.numero_inscricao,
            "valor_inscrito": str(resto.valor_inscrito),
        },
    )
    publicar_evento_transparencia(
        municipio=resto.municipio,
        modulo="FINANCEIRO",
        tipo_evento="RESTOS_PAGAR_INSCRICAO",
        titulo=f"Resto a pagar inscrito {resto.numero_inscricao}",
        referencia=resto.numero_inscricao,
        valor=resto.valor_inscrito,
        dados={"empenho": resto.empenho.numero, "tipo": resto.tipo},
    )


@transaction.atomic
def registrar_pagamento_resto(pagamento: DespPagamentoResto, *, usuario=None):
    resto = DespRestosPagar.objects.select_for_update().get(pk=pagamento.resto_id)
    conta = None
    if pagamento.conta_bancaria_id:
        conta = FinanceiroContaBancaria.objects.select_for_update().get(pk=pagamento.conta_bancaria_id)

    if pagamento.status == DespPagamentoResto.Status.ESTORNADO:
        registrar_log(
            municipio=resto.municipio,
            evento="RESTO_PAGAR_PAGAMENTO_ESTORNADO",
            entidade="DespPagamentoResto",
            entidade_id=str(pagamento.pk),
            usuario=usuario,
            depois={
                "numero_inscricao": resto.numero_inscricao,
                "valor_estorno": str(pagamento.valor),
            },
        )
        registrar_auditoria(
            municipio=resto.municipio,
            modulo="FINANCEIRO",
            evento="RESTO_PAGAR_PAGAMENTO_ESTORNADO",
            entidade="DespPagamentoResto",
            entidade_id=pagamento.pk,
            usuario=usuario,
            depois={"numero_inscricao": resto.numero_inscricao, "valor_estorno": str(pagamento.valor)},
        )
        return

    if _to_dec(pagamento.valor) > _to_dec(resto.saldo_a_pagar):
        raise ValueError("Valor do pagamento de RP excede o saldo disponível.")

    resto.valor_pago = _to_dec(resto.valor_pago) + _to_dec(pagamento.valor)
    if resto.valor_pago <= 0:
        resto.status = DespRestosPagar.Status.INSCRITO
    elif resto.valor_pago < resto.valor_inscrito:
        resto.status = DespRestosPagar.Status.PARCIAL
    else:
        resto.status = DespRestosPagar.Status.PAGO
    resto.save(update_fields=["valor_pago", "status", "atualizado_em"])

    if conta is not None and pagamento.status == DespPagamentoResto.Status.PAGO:
        conta.saldo_atual = _to_dec(conta.saldo_atual) - _to_dec(pagamento.valor)
        conta.save(update_fields=["saldo_atual", "atualizado_em"])

    registrar_log(
        municipio=resto.municipio,
        evento="RESTO_PAGAR_PAGAMENTO_REGISTRADO",
        entidade="DespPagamentoResto",
        entidade_id=str(pagamento.pk),
        usuario=usuario,
        depois={
            "numero_inscricao": resto.numero_inscricao,
            "valor_pagamento": str(pagamento.valor),
            "valor_pago_resto": str(resto.valor_pago),
            "status_resto": resto.status,
            "conta": str(conta.pk) if conta else "",
        },
    )
    registrar_auditoria(
        municipio=resto.municipio,
        modulo="FINANCEIRO",
        evento="RESTO_PAGAR_PAGAMENTO_REGISTRADO",
        entidade="DespPagamentoResto",
        entidade_id=pagamento.pk,
        usuario=usuario,
        depois={
            "numero_inscricao": resto.numero_inscricao,
            "valor_pagamento": str(pagamento.valor),
            "status_resto": resto.status,
        },
    )
    publicar_evento_transparencia(
        municipio=resto.municipio,
        modulo="FINANCEIRO",
        tipo_evento="RESTOS_PAGAR_PAGAMENTO",
        titulo=f"Pagamento de resto a pagar {resto.numero_inscricao}",
        referencia=pagamento.ordem_pagamento or str(pagamento.pk),
        valor=pagamento.valor,
        dados={"status": pagamento.status, "resto_status": resto.status},
    )


@transaction.atomic
def registrar_arrecadacao(arrecadacao: RecArrecadacao, *, usuario=None):
    conta = None
    if arrecadacao.conta_bancaria_id:
        conta = FinanceiroContaBancaria.objects.select_for_update().get(pk=arrecadacao.conta_bancaria_id)

    if conta is not None:
        conta.saldo_atual = _to_dec(conta.saldo_atual) + _to_dec(arrecadacao.valor)
        conta.save(update_fields=["saldo_atual", "atualizado_em"])

    registrar_log(
        municipio=arrecadacao.municipio,
        evento="ARRECADACAO_REGISTRADA",
        entidade="RecArrecadacao",
        entidade_id=str(arrecadacao.pk),
        usuario=usuario,
        depois={
            "rubrica": arrecadacao.rubrica_codigo,
            "valor": str(arrecadacao.valor),
            "conta": str(conta.pk) if conta else "",
        },
    )
    registrar_auditoria(
        municipio=arrecadacao.municipio,
        modulo="FINANCEIRO",
        evento="ARRECADACAO_REGISTRADA",
        entidade="RecArrecadacao",
        entidade_id=arrecadacao.pk,
        usuario=usuario,
        depois={
            "rubrica": arrecadacao.rubrica_codigo,
            "valor": str(arrecadacao.valor),
        },
    )
    publicar_evento_transparencia(
        municipio=arrecadacao.municipio,
        modulo="FINANCEIRO",
        tipo_evento="ARRECADACAO",
        titulo=f"Receita arrecadada {arrecadacao.rubrica_codigo}",
        descricao=arrecadacao.rubrica_nome,
        referencia=arrecadacao.documento or str(arrecadacao.pk),
        valor=arrecadacao.valor,
        dados={"origem": arrecadacao.origem},
    )


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except Exception:
        return None


def _parse_date(value: Any):
    if value is None:
        return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass
    text = str(value).strip()
    if not text:
        return None

    text = text[:19]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8 and ("T" in text or len(digits) > 8):
        text = digits[:8]

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


def _decode_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch.isalnum())


def _parse_csv_items(text: str) -> list[dict]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    sample = "\n".join(lines[:20])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except Exception:
        delimiter = ";"
        if "," in sample and sample.count(",") > sample.count(";"):
            delimiter = ","

    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    if not reader.fieldnames:
        return []

    norm_headers = {_normalize_key(h): h for h in reader.fieldnames if h}

    def get_col(*aliases):
        for alias in aliases:
            col = norm_headers.get(_normalize_key(alias))
            if col:
                return col
        return None

    date_col = get_col("data", "date", "datamovimento", "dtmov", "dtpost")
    value_col = get_col("valor", "amount", "trnamt", "valormovimento")
    type_col = get_col("tipo", "natureza", "dc", "creditodebito", "trntype")
    doc_col = get_col("documento", "doc", "numero", "checknum", "fitid")
    desc_col = get_col("historico", "descricao", "memo", "detalhe", "name")
    balance_col = get_col("saldo", "balance", "saldoinformado")

    if not date_col or not value_col:
        raise ValueError("CSV sem colunas obrigatórias (data e valor).")

    parsed: list[dict] = []
    for row in reader:
        data_movimento = _parse_date(row.get(date_col))
        valor = _parse_decimal(row.get(value_col))
        if not data_movimento or valor is None:
            continue

        tipo_val = (row.get(type_col) or "").strip().upper() if type_col else ""
        if tipo_val in {"D", "DEBITO", "DÉBITO", "DEBIT", "PAGAMENTO"} and valor > 0:
            valor = -valor
        if tipo_val in {"C", "CREDITO", "CRÉDITO", "CREDIT", "RECEITA"} and valor < 0:
            valor = abs(valor)

        parsed.append(
            {
                "data_movimento": data_movimento,
                "valor": valor,
                "documento": (row.get(doc_col) or "").strip() if doc_col else "",
                "historico": (row.get(desc_col) or "").strip() if desc_col else "",
                "identificador_externo": "",
                "saldo_informado": _parse_decimal(row.get(balance_col)) if balance_col else None,
            }
        )

    return parsed


def _ofx_tag(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>([^<\r\n]+)", block, flags=re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).strip()


def _parse_ofx_items(text: str) -> list[dict]:
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, flags=re.IGNORECASE | re.DOTALL)
    if not blocks:
        rough = text.split("<STMTTRN>")
        blocks = rough[1:] if len(rough) > 1 else []

    parsed: list[dict] = []
    for block in blocks:
        dt_raw = _ofx_tag(block, "DTPOSTED")
        amt_raw = _ofx_tag(block, "TRNAMT")
        trn_type = _ofx_tag(block, "TRNTYPE").upper()
        fitid = _ofx_tag(block, "FITID")
        memo = _ofx_tag(block, "MEMO")
        name = _ofx_tag(block, "NAME")
        checknum = _ofx_tag(block, "CHECKNUM")

        data_movimento = _parse_date(dt_raw)
        valor = _parse_decimal(amt_raw)
        if not data_movimento or valor is None:
            continue

        if trn_type in {"DEBIT", "PAYMENT"} and valor > 0:
            valor = -valor
        if trn_type in {"CREDIT", "DEP"} and valor < 0:
            valor = abs(valor)

        parsed.append(
            {
                "data_movimento": data_movimento,
                "valor": valor,
                "documento": checknum or fitid,
                "historico": memo or name or trn_type,
                "identificador_externo": fitid,
                "saldo_informado": None,
            }
        )
    return parsed


def _parse_extrato_payload(*, formato: str, raw_bytes: bytes) -> list[dict]:
    text = _decode_bytes(raw_bytes)
    if formato == TesExtratoImportacao.Formato.CSV:
        return _parse_csv_items(text)
    if formato == TesExtratoImportacao.Formato.OFX:
        return _parse_ofx_items(text)
    raise ValueError("Formato de importação inválido.")


@transaction.atomic
def importar_extrato_bancario(
    *,
    municipio,
    exercicio,
    conta_bancaria,
    formato: str,
    arquivo_nome: str,
    raw_bytes: bytes,
    usuario=None,
    observacao: str = "",
) -> TesExtratoImportacao:
    items = _parse_extrato_payload(formato=formato, raw_bytes=raw_bytes)
    if not items:
        raise ValueError("Não foi possível identificar lançamentos no arquivo informado.")

    importacao = TesExtratoImportacao.objects.create(
        municipio=municipio,
        exercicio=exercicio,
        conta_bancaria=conta_bancaria,
        formato=formato,
        arquivo_nome=arquivo_nome[:255],
        observacao=observacao or "",
        criado_por=usuario,
        status=TesExtratoImportacao.Status.PROCESSADA,
    )

    to_create = []
    credits = Decimal("0.00")
    debits = Decimal("0.00")
    dates = []
    for item in items:
        valor = _to_dec(item["valor"])
        if valor > 0:
            credits += valor
        elif valor < 0:
            debits += abs(valor)
        dates.append(item["data_movimento"])
        to_create.append(
            TesExtratoItem(
                importacao=importacao,
                municipio=municipio,
                conta_bancaria=conta_bancaria,
                data_movimento=item["data_movimento"],
                documento=item.get("documento", "")[:80],
                historico=item.get("historico", "")[:255],
                identificador_externo=item.get("identificador_externo", "")[:120],
                valor=valor,
                saldo_informado=item.get("saldo_informado"),
            )
        )

    TesExtratoItem.objects.bulk_create(to_create, batch_size=500)

    importacao.total_itens = len(to_create)
    importacao.total_creditos = credits
    importacao.total_debitos = debits
    importacao.periodo_inicio = min(dates) if dates else None
    importacao.periodo_fim = max(dates) if dates else None
    importacao.save(
        update_fields=[
            "total_itens",
            "total_creditos",
            "total_debitos",
            "periodo_inicio",
            "periodo_fim",
            "atualizado_em",
        ]
    )

    registrar_log(
        municipio=municipio,
        evento="EXTRATO_IMPORTADO",
        entidade="TesExtratoImportacao",
        entidade_id=str(importacao.pk),
        usuario=usuario,
        depois={
            "formato": formato,
            "arquivo": importacao.arquivo_nome,
            "total_itens": str(importacao.total_itens),
            "total_creditos": str(importacao.total_creditos),
            "total_debitos": str(importacao.total_debitos),
        },
    )

    return importacao


def _referencias_ja_conciliadas(municipio):
    return {
        "receitas": set(
            RecConciliacaoItem.objects.filter(municipio=municipio, receita_id__isnull=False).values_list("receita_id", flat=True)
        ),
        "pagamentos": set(
            RecConciliacaoItem.objects.filter(municipio=municipio, desp_pagamento_id__isnull=False).values_list("desp_pagamento_id", flat=True)
        ),
        "pagamentos_rp": set(
            RecConciliacaoItem.objects.filter(municipio=municipio, desp_pagamento_resto_id__isnull=False).values_list("desp_pagamento_resto_id", flat=True)
        ),
    }


def _conciliar_item(*, item: TesExtratoItem, tipo: str, usuario=None, receita=None, pagamento=None, pagamento_rp=None, observacao: str = ""):
    conc = RecConciliacaoItem.objects.create(
        municipio=item.municipio,
        extrato_item=item,
        referencia_tipo=tipo,
        receita=receita,
        desp_pagamento=pagamento,
        desp_pagamento_resto=pagamento_rp,
        observacao=observacao or "",
        conciliado_por=usuario,
    )
    registrar_log(
        municipio=item.municipio,
        evento="EXTRATO_ITEM_CONCILIADO",
        entidade="RecConciliacaoItem",
        entidade_id=str(conc.pk),
        usuario=usuario,
        depois={
            "extrato_item_id": str(item.pk),
            "referencia_tipo": tipo,
            "receita_id": str(receita.pk) if receita else "",
            "pagamento_id": str(pagamento.pk) if pagamento else "",
            "pagamento_rp_id": str(pagamento_rp.pk) if pagamento_rp else "",
        },
    )
    return conc


@transaction.atomic
def executar_conciliacao_automatica(importacao: TesExtratoImportacao, *, usuario=None) -> dict:
    pendentes = list(
        TesExtratoItem.objects.filter(importacao=importacao).filter(conciliacao__isnull=True).order_by("data_movimento", "id")
    )
    if not pendentes:
        return {"processados": 0, "conciliados": 0, "receitas": 0, "pagamentos": 0, "pagamentos_rp": 0}

    usados = _referencias_ja_conciliadas(importacao.municipio)
    counts = {"processados": len(pendentes), "conciliados": 0, "receitas": 0, "pagamentos": 0, "pagamentos_rp": 0}

    for item in pendentes:
        if item.valor == 0:
            continue

        if item.valor > 0:
            receita = (
                RecArrecadacao.objects.filter(
                    municipio=importacao.municipio,
                    conta_bancaria=importacao.conta_bancaria,
                    data_arrecadacao=item.data_movimento,
                    valor=item.valor,
                )
                .exclude(id__in=usados["receitas"])
                .order_by("id")
                .first()
            )
            if receita:
                _conciliar_item(
                    item=item,
                    tipo=RecConciliacaoItem.ReferenciaTipo.RECEITA,
                    usuario=usuario,
                    receita=receita,
                    observacao="Conciliação automática por valor+data+conta.",
                )
                usados["receitas"].add(receita.pk)
                counts["conciliados"] += 1
                counts["receitas"] += 1
            continue

        valor_saida = abs(item.valor)
        pagamento = (
            DespPagamento.objects.filter(
                liquidacao__empenho__municipio=importacao.municipio,
                conta_bancaria=importacao.conta_bancaria,
                status=DespPagamento.Status.PAGO,
                data_pagamento=item.data_movimento,
                valor_pago=valor_saida,
            )
            .exclude(id__in=usados["pagamentos"])
            .order_by("id")
            .first()
        )
        if pagamento:
            _conciliar_item(
                item=item,
                tipo=RecConciliacaoItem.ReferenciaTipo.PAGAMENTO,
                usuario=usuario,
                pagamento=pagamento,
                observacao="Conciliação automática por valor+data+conta.",
            )
            usados["pagamentos"].add(pagamento.pk)
            counts["conciliados"] += 1
            counts["pagamentos"] += 1
            continue

        pagamento_rp = (
            DespPagamentoResto.objects.filter(
                resto__municipio=importacao.municipio,
                conta_bancaria=importacao.conta_bancaria,
                status=DespPagamentoResto.Status.PAGO,
                data_pagamento=item.data_movimento,
                valor=valor_saida,
            )
            .exclude(id__in=usados["pagamentos_rp"])
            .order_by("id")
            .first()
        )
        if pagamento_rp:
            _conciliar_item(
                item=item,
                tipo=RecConciliacaoItem.ReferenciaTipo.PAGAMENTO_RP,
                usuario=usuario,
                pagamento_rp=pagamento_rp,
                observacao="Conciliação automática por valor+data+conta.",
            )
            usados["pagamentos_rp"].add(pagamento_rp.pk)
            counts["conciliados"] += 1
            counts["pagamentos_rp"] += 1

    registrar_log(
        municipio=importacao.municipio,
        evento="EXTRATO_CONCILIACAO_AUTO",
        entidade="TesExtratoImportacao",
        entidade_id=str(importacao.pk),
        usuario=usuario,
        depois={k: str(v) for k, v in counts.items()},
    )
    return counts


@transaction.atomic
def marcar_item_como_ajuste(item: TesExtratoItem, *, usuario=None, observacao: str = "") -> RecConciliacaoItem:
    if hasattr(item, "conciliacao"):
        return item.conciliacao
    return _conciliar_item(
        item=item,
        tipo=RecConciliacaoItem.ReferenciaTipo.AJUSTE,
        usuario=usuario,
        observacao=observacao or "Ajuste manual da tesouraria.",
    )


@transaction.atomic
def desfazer_conciliacao(item: TesExtratoItem, *, usuario=None):
    conciliacao = getattr(item, "conciliacao", None)
    if not conciliacao:
        return

    conc_id = conciliacao.pk
    conciliacao.delete()
    registrar_log(
        municipio=item.municipio,
        evento="EXTRATO_CONCILIACAO_DESFEITA",
        entidade="RecConciliacaoItem",
        entidade_id=str(conc_id),
        usuario=usuario,
        depois={"extrato_item_id": str(item.pk)},
    )
