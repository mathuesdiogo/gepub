from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Profile
from apps.core.models import AuditoriaEvento, TransparenciaEventoPublico
from apps.financeiro.models import DespEmpenho, FinanceiroExercicio, FinanceiroUnidadeGestora, OrcDotacao, OrcFonteRecurso
from apps.financeiro.services import registrar_empenho
from apps.org.models import Municipio
from .models import ContratoAdministrativo, MedicaoContrato


User = get_user_model()


class ContratosLiquidacaoTestCase(TestCase):
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
        self.municipio = Municipio.objects.create(nome="Cidade Contratos", uf="MA", ativo=True)
        self.user = self._make_user("contratos_muni", "MUNICIPAL", municipio=self.municipio)

        self.exercicio = FinanceiroExercicio.objects.create(municipio=self.municipio, ano=2026)
        self.ug = FinanceiroUnidadeGestora.objects.create(municipio=self.municipio, codigo="0201", nome="UG Contratos")
        self.fonte = OrcFonteRecurso.objects.create(municipio=self.municipio, codigo="15000000", nome="Ordinario")
        self.dotacao = OrcDotacao.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio,
            unidade_gestora=self.ug,
            programa_codigo="20",
            programa_nome="Infra",
            acao_codigo="2001",
            acao_nome="Obras",
            elemento_despesa="339039",
            fonte=self.fonte,
            valor_inicial=Decimal("9000.00"),
            valor_atualizado=Decimal("9000.00"),
        )
        self.empenho = DespEmpenho.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio,
            unidade_gestora=self.ug,
            dotacao=self.dotacao,
            numero="EMP-CONTR-0001",
            fornecedor_nome="Fornecedor Contrato",
            tipo=DespEmpenho.Tipo.ORDINARIO,
            valor_empenhado=Decimal("3000.00"),
            criado_por=self.user,
        )
        registrar_empenho(self.empenho, usuario=self.user)

        self.contrato = ContratoAdministrativo.objects.create(
            municipio=self.municipio,
            numero="CT-2026-001",
            objeto="Contrato de servicos",
            fornecedor_nome="Fornecedor Contrato",
            valor_total=Decimal("3000.00"),
            vigencia_fim="2026-12-31",
            empenho=self.empenho,
            criado_por=self.user,
        )

    def test_medicao_atestada_gera_liquidacao(self):
        self.client.force_login(self.user)
        medicao = MedicaoContrato.objects.create(
            contrato=self.contrato,
            numero="MED-001",
            competencia="2026-02",
            valor_medido=Decimal("1000.00"),
            criado_por=self.user,
        )

        response_atestar = self.client.get(
            reverse("contratos:medicao_atestar", args=[medicao.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_atestar.status_code, 302)

        response_liquidar = self.client.get(
            reverse("contratos:medicao_liquidar", args=[medicao.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_liquidar.status_code, 302)

        medicao.refresh_from_db()
        self.empenho.refresh_from_db()

        self.assertEqual(medicao.status, MedicaoContrato.Status.LIQUIDADA)
        self.assertIsNotNone(medicao.liquidacao_id)
        self.assertEqual(self.empenho.valor_liquidado, Decimal("1000.00"))
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=self.municipio,
                modulo="CONTRATOS",
                evento="MEDICAO_ATESTADA",
            ).exists()
        )
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=self.municipio,
                modulo="CONTRATOS",
                evento="MEDICAO_LIQUIDADA",
            ).exists()
        )
        self.assertTrue(
            TransparenciaEventoPublico.objects.filter(
                municipio=self.municipio,
                modulo=TransparenciaEventoPublico.Modulo.CONTRATOS,
                tipo_evento="MEDICAO_LIQUIDADA",
            ).exists()
        )
