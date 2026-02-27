from django.test import SimpleTestCase

from .services.dashboard import build_dashboard_payload
from .services.ingest import ingest_dataset_bytes


class IngestDatasetTests(SimpleTestCase):
    def test_ingest_csv_builds_schema_profile(self):
        raw = "data;secretaria;valor\n2026-01-01;Saude;1200\n2026-01-02;Educacao;900\n".encode("utf-8")
        result = ingest_dataset_bytes(raw, "CSV", filename="demo.csv")

        self.assertEqual(result["profile"]["row_count"], 2)
        self.assertEqual(result["profile"]["column_count"], 3)

        schema = {item["name"]: item for item in result["schema"]}
        self.assertEqual(schema["data"]["type"], "DATA")
        self.assertEqual(schema["valor"]["type"], "NUMERO")
        self.assertEqual(schema["valor"]["role"], "MEDIDA")

    def test_dashboard_payload_with_filters(self):
        rows = [
            {"data": "2026-01-01", "secretaria": "Saude", "categoria": "A", "valor": "10"},
            {"data": "2026-01-02", "secretaria": "Saude", "categoria": "A", "valor": "20"},
            {"data": "2026-01-02", "secretaria": "Educacao", "categoria": "B", "valor": "5"},
        ]
        schema = [
            {"name": "data", "type": "DATA"},
            {"name": "secretaria", "type": "TEXTO"},
            {"name": "categoria", "type": "TEXTO"},
            {"name": "valor", "type": "NUMERO"},
        ]

        payload = build_dashboard_payload(
            rows,
            schema,
            {
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "secretaria": "Saude",
                "unidade": "",
                "categoria": "",
            },
        )

        self.assertEqual(payload["kpis"]["linhas_filtradas"], 2)
        self.assertEqual(payload["line"]["labels"], ["2026-01"])
        self.assertEqual(payload["line"]["values"], [30.0])
