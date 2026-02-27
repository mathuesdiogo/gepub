from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Profile
from apps.core.models import AuditoriaEvento, TransparenciaEventoPublico
from apps.financeiro.models import FinanceiroExercicio, FinanceiroUnidadeGestora, OrcDotacao, OrcFonteRecurso
from apps.org.models import Municipio
from .models import RequisicaoCompra


User = get_user_model()


class ComprasIntegracaoFinanceiroTestCase(TestCase):
    def _make_user(self, username: str, role: str, municipio=None):
        user = User.objects.create_user(username=username, password="x")
        profile = getattr(user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=user, role=role, ativo=True)
        else:
            profile.role = role
            profile.ativo = True
        profile.must_change_password = False
        profile.municipio = municipio
        profile.save(update_fields=["role", "ativo", "must_change_password", "municipio"])
        return user

    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Compras", uf="MA", ativo=True)
        self.user = self._make_user("compras_muni", "MUNICIPAL", municipio=self.municipio)

        self.exercicio = FinanceiroExercicio.objects.create(municipio=self.municipio, ano=2026)
        self.ug = FinanceiroUnidadeGestora.objects.create(municipio=self.municipio, codigo="0101", nome="UG Compras")
        self.fonte = OrcFonteRecurso.objects.create(municipio=self.municipio, codigo="15000000", nome="Ordinario")
        self.dotacao = OrcDotacao.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio,
            unidade_gestora=self.ug,
            programa_codigo="10",
            programa_nome="Gestao",
            acao_codigo="1001",
            acao_nome="Manutencao",
            elemento_despesa="339030",
            fonte=self.fonte,
            valor_inicial=Decimal("5000.00"),
            valor_atualizado=Decimal("5000.00"),
        )

    def test_requisicao_gera_empenho(self):
        self.client.force_login(self.user)

        response_create = self.client.post(
            reverse("compras:requisicao_create") + f"?municipio={self.municipio.pk}",
            data={
                "numero": "REQ-2026-0001",
                "objeto": "Aquisição de materiais de expediente",
                "justificativa": "Teste de integração",
                "valor_estimado": "1200.00",
                "status": "APROVADA",
                "fornecedor_nome": "Fornecedor Teste",
                "fornecedor_documento": "00.000.000/0001-00",
                "dotacao": self.dotacao.pk,
            },
        )
        self.assertEqual(response_create.status_code, 302)

        req = RequisicaoCompra.objects.get(numero="REQ-2026-0001")
        response_empenho = self.client.get(
            reverse("compras:gerar_empenho", args=[req.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_empenho.status_code, 302)

        req.refresh_from_db()
        self.dotacao.refresh_from_db()

        self.assertIsNotNone(req.empenho_id)
        self.assertEqual(req.status, RequisicaoCompra.Status.HOMOLOGADA)
        self.assertEqual(self.dotacao.valor_empenhado, Decimal("1200.00"))
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=self.municipio,
                modulo="COMPRAS",
                evento="REQUISICAO_CRIADA",
            ).exists()
        )
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=self.municipio,
                modulo="COMPRAS",
                evento="REQUISICAO_HOMOLOGADA_COM_EMPENHO",
            ).exists()
        )
        self.assertTrue(
            TransparenciaEventoPublico.objects.filter(
                municipio=self.municipio,
                modulo=TransparenciaEventoPublico.Modulo.COMPRAS,
                tipo_evento="REQUISICAO_HOMOLOGADA",
            ).exists()
        )
