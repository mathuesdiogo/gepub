from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.text import slugify

from apps.core.services_auditoria import registrar_auditoria

from ..models import Chart, Dashboard, Dataset, DatasetColumn, DatasetVersion
from .ingest import ingest_dataset_bytes


def _resolve_actor(*, actor_id: int | None = None, actor=None):
    if actor is not None:
        return actor
    if not actor_id:
        return None
    User = get_user_model()
    return User.objects.filter(pk=actor_id).first()


def ensure_default_dashboard(dataset: Dataset, user, schema: list[dict]) -> Dashboard:
    dashboard = dataset.dashboards.order_by("id").first()
    if dashboard:
        return dashboard

    dashboard = Dashboard.objects.create(
        dataset=dataset,
        nome="Painel padrão",
        descricao="Dashboard automático gerado na ingestão.",
        tema="institucional",
        criado_por=user,
        layout_json={
            "grid": [
                {"id": "kpis", "x": 0, "y": 0, "w": 12, "h": 2},
                {"id": "line", "x": 0, "y": 2, "w": 8, "h": 4},
                {"id": "ranking", "x": 8, "y": 2, "w": 4, "h": 4},
                {"id": "table", "x": 0, "y": 6, "w": 12, "h": 5},
            ]
        },
    )

    value_col = next((c.get("name") for c in schema if c.get("type") == "NUMERO"), "")
    date_col = next((c.get("name") for c in schema if c.get("type") == "DATA"), "")

    Chart.objects.bulk_create(
        [
            Chart(
                dashboard=dashboard,
                tipo=Chart.Tipo.KPI,
                titulo="KPIs",
                ordem=1,
                config_json={"metric": value_col},
            ),
            Chart(
                dashboard=dashboard,
                tipo=Chart.Tipo.LINHA,
                titulo="Série temporal",
                ordem=2,
                config_json={"x": date_col, "y": value_col},
            ),
            Chart(
                dashboard=dashboard,
                tipo=Chart.Tipo.BARRA,
                titulo="Ranking",
                ordem=3,
                config_json={"y": value_col},
            ),
            Chart(
                dashboard=dashboard,
                tipo=Chart.Tipo.TABELA,
                titulo="Tabela filtrada",
                ordem=4,
                config_json={},
            ),
        ]
    )

    return dashboard


def process_dataset_version(
    version_id: int,
    *,
    google_sheet_url: str = "",
    actor_id: int | None = None,
    actor=None,
) -> DatasetVersion:
    version = (
        DatasetVersion.objects.select_related("dataset", "dataset__municipio")
        .filter(pk=version_id)
        .first()
    )
    if not version:
        raise ValueError("Versão do dataset não encontrada para processamento.")

    dataset = version.dataset
    actor_user = _resolve_actor(actor_id=actor_id, actor=actor) or version.criado_por

    version.status = DatasetVersion.Status.PROCESSANDO
    version.logs = "Processamento iniciado."
    version.save(update_fields=["status", "logs"])

    raw_bytes = b""
    if version.arquivo_original:
        with version.arquivo_original.open("rb") as fobj:
            raw_bytes = fobj.read()

    try:
        ingestion = ingest_dataset_bytes(
            raw_bytes,
            dataset.fonte,
            filename=(version.arquivo_original.name if version.arquivo_original else ""),
            google_sheet_url=google_sheet_url,
        )

        treated_name = f"{slugify(dataset.nome or 'dataset')}_v{version.numero}.csv"
        version.arquivo_tratado.save(treated_name, ContentFile(ingestion["processed_csv_bytes"]), save=False)
        version.schema_json = {"columns": ingestion["schema"]}
        version.profile_json = ingestion["profile"]
        version.preview_json = ingestion["preview_rows"]
        version.status = DatasetVersion.Status.CONCLUIDO
        version.logs = "\n".join(ingestion.get("warnings") or []) or "Processamento concluído."
        version.processado_em = timezone.now()
        version.save()

        DatasetColumn.objects.filter(versao=version).delete()
        DatasetColumn.objects.bulk_create(
            [
                DatasetColumn(
                    versao=version,
                    nome=col.get("name", ""),
                    tipo=col.get("type") or DatasetColumn.Tipo.TEXTO,
                    papel=col.get("role") or DatasetColumn.Papel.DIMENSAO,
                    sensivel=bool(col.get("sensitive")),
                    ordem=idx,
                    amostra=(col.get("sample") or "")[:140],
                )
                for idx, col in enumerate(ingestion.get("schema") or [], start=1)
            ]
        )

        ensure_default_dashboard(dataset, actor_user, ingestion.get("schema") or [])

        has_sensitive = any(bool(col.get("sensitive")) for col in (ingestion.get("schema") or []))
        if dataset.visibilidade == Dataset.Visibilidade.PUBLICO and has_sensitive:
            dataset.status = Dataset.Status.RASCUNHO
        else:
            dataset.status = Dataset.Status.VALIDADO

        if actor_user:
            dataset.atualizado_por = actor_user
            dataset.save(update_fields=["status", "atualizado_por", "atualizado_em"])
        else:
            dataset.save(update_fields=["status", "atualizado_em"])

        registrar_auditoria(
            municipio=dataset.municipio,
            modulo="PAINEIS",
            evento="DATASET_INGESTAO_OK",
            entidade="DatasetVersion",
            entidade_id=version.pk,
            usuario=actor_user,
            depois={
                "dataset": dataset.nome,
                "versao": version.numero,
                "linhas": ingestion.get("profile", {}).get("row_count", 0),
                "colunas": ingestion.get("profile", {}).get("column_count", 0),
                "status": dataset.status,
            },
        )

    except Exception as exc:
        version.status = DatasetVersion.Status.ERRO
        version.logs = str(exc)
        version.processado_em = timezone.now()
        version.save(update_fields=["status", "logs", "processado_em"])

        registrar_auditoria(
            municipio=dataset.municipio,
            modulo="PAINEIS",
            evento="DATASET_INGESTAO_ERRO",
            entidade="DatasetVersion",
            entidade_id=version.pk,
            usuario=actor_user,
            depois={"erro": str(exc)[:400]},
        )

    return version
