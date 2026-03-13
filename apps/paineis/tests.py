from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .services.dashboard import build_dashboard_payload
from .services.ingest import ingest_dataset_bytes
from .models import Dataset, DatasetVersion
from apps.org.models import Municipio


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


class DatasetPublishChecklistTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="paineis_admin",
            email="paineis_admin@example.com",
            password="Senha@123",
        )
        profile = self.user.profile
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        self.municipio = Municipio.objects.create(nome="Municipio BI", uf="MA", ativo=True)
        self.dataset = Dataset.objects.create(
            municipio=self.municipio,
            nome="Dataset teste",
            categoria="Teste",
            fonte=Dataset.Fonte.CSV,
            visibilidade=Dataset.Visibilidade.INTERNO,
            status=Dataset.Status.RASCUNHO,
            criado_por=self.user,
            atualizado_por=self.user,
        )
        self.version = DatasetVersion.objects.create(
            dataset=self.dataset,
            numero=1,
            fonte=Dataset.Fonte.CSV,
            status=DatasetVersion.Status.CONCLUIDO,
            schema_json={"columns": [{"name": "valor", "sensitive": False}]},
            profile_json={"row_count": 1, "column_count": 1},
            preview_json=[{"valor": "10"}],
            criado_por=self.user,
        )

    def test_publish_requires_checklist(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("paineis:dataset_publish", args=[self.dataset.pk]), {})
        self.assertEqual(response.status_code, 302)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, Dataset.Status.RASCUNHO)

    def test_publish_with_checklist_marks_dataset_as_publicado(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("paineis:dataset_publish", args=[self.dataset.pk]),
            {
                "check_quality": "1",
                "check_lgpd": "1",
                "check_publication_rules": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, Dataset.Status.PUBLICADO)
