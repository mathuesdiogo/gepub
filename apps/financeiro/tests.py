from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Profile
from apps.core.models import AuditoriaEvento, TransparenciaEventoPublico
from apps.org.models import Municipio
from apps.financeiro.models import (
    DespEmpenho,
    DespLiquidacao,
    DespPagamento,
    DespRestosPagar,
    FinanceiroContaBancaria,
    FinanceiroExercicio,
    FinanceiroLogEvento,
    FinanceiroUnidadeGestora,
    OrcCreditoAdicional,
    OrcDotacao,
    OrcFonteRecurso,
    RecArrecadacao,
    RecConciliacaoItem,
    TesExtratoImportacao,
)
from apps.financeiro.services import registrar_empenho, registrar_liquidacao, registrar_pagamento


User = get_user_model()


class FinanceiroAccessTestCase(TestCase):
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

    def test_municipal_can_access_financeiro_index(self):
        municipio = Municipio.objects.create(nome="Cidade Teste", uf="MA", ativo=True)
        user = self._make_user("fin_muni", "MUNICIPAL", municipio=municipio)

        self.client.force_login(user)
        response = self.client.get(reverse("financeiro:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financeiro Público")

    def test_professor_cannot_access_financeiro_index(self):
        municipio = Municipio.objects.create(nome="Cidade Bloq", uf="MA", ativo=True)
        user = self._make_user("fin_prof", "PROFESSOR", municipio=municipio)

        self.client.force_login(user)
        response = self.client.get(reverse("financeiro:index"))

        self.assertEqual(response.status_code, 403)


class FinanceiroFase2FlowTestCase(TestCase):
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
        self.municipio = Municipio.objects.create(nome="Cidade Fase2", uf="MA", ativo=True)
        self.user = self._make_user("fase2_muni", "MUNICIPAL", municipio=self.municipio)

        self.exercicio_origem = FinanceiroExercicio.objects.create(municipio=self.municipio, ano=2025)
        self.exercicio_inscricao = FinanceiroExercicio.objects.create(municipio=self.municipio, ano=2026)
        self.ug = FinanceiroUnidadeGestora.objects.create(municipio=self.municipio, codigo="1001", nome="UG Central")
        self.fonte = OrcFonteRecurso.objects.create(municipio=self.municipio, codigo="15000000", nome="Recursos Ordinários")
        self.dotacao = OrcDotacao.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio_origem,
            unidade_gestora=self.ug,
            programa_codigo="10",
            programa_nome="Programa Base",
            acao_codigo="2001",
            acao_nome="Ação Base",
            elemento_despesa="339039",
            fonte=self.fonte,
            valor_inicial=Decimal("1000.00"),
            valor_atualizado=Decimal("1000.00"),
        )
        self.conta = FinanceiroContaBancaria.objects.create(
            municipio=self.municipio,
            unidade_gestora=self.ug,
            banco_codigo="001",
            banco_nome="Banco do Brasil",
            agencia="0001",
            conta="12345-6",
            saldo_atual=Decimal("1000.00"),
        )
        self.empenho = DespEmpenho.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio_origem,
            unidade_gestora=self.ug,
            dotacao=self.dotacao,
            numero="EMP-2025-0001",
            fornecedor_nome="Fornecedor Exemplo",
            tipo=DespEmpenho.Tipo.ORDINARIO,
            valor_empenhado=Decimal("500.00"),
            criado_por=self.user,
        )
        registrar_empenho(self.empenho, usuario=self.user)
        self.liquidacao = DespLiquidacao.objects.create(
            empenho=self.empenho,
            numero="LIQ-0001",
            valor_liquidado=Decimal("400.00"),
            criado_por=self.user,
        )
        registrar_liquidacao(self.liquidacao, usuario=self.user)

    def test_credito_adicional_create_updates_dotacao(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("financeiro:credito_create") + f"?municipio={self.municipio.pk}",
            data={
                "exercicio": self.exercicio_origem.pk,
                "dotacao": self.dotacao.pk,
                "tipo": "SUPLEMENTAR",
                "numero_ato": "DEC-10/2025",
                "data_ato": "2025-06-01",
                "valor": "200.00",
                "origem_recurso": "Superávit financeiro",
                "descricao": "Reforço de dotação",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.dotacao.refresh_from_db()

        self.assertEqual(self.dotacao.valor_atualizado, Decimal("1200.00"))
        self.assertTrue(OrcCreditoAdicional.objects.filter(numero_ato="DEC-10/2025").exists())
        self.assertTrue(FinanceiroLogEvento.objects.filter(evento="CREDITO_ADICIONAL_REGISTRADO").exists())
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=self.municipio,
                modulo="FINANCEIRO",
                evento="CREDITO_ADICIONAL_REGISTRADO",
            ).exists()
        )
        self.assertTrue(
            TransparenciaEventoPublico.objects.filter(
                municipio=self.municipio,
                modulo=TransparenciaEventoPublico.Modulo.FINANCEIRO,
                tipo_evento="CREDITO_ADICIONAL",
            ).exists()
        )

    def test_resto_pagar_payment_flow_updates_status_and_account_balance(self):
        self.client.force_login(self.user)
        response_resto = self.client.post(
            reverse("financeiro:resto_create") + f"?municipio={self.municipio.pk}",
            data={
                "exercicio_inscricao": self.exercicio_inscricao.pk,
                "empenho": self.empenho.pk,
                "tipo": DespRestosPagar.Tipo.PROCESSADO,
                "numero_inscricao": "RP-2026-0001",
                "data_inscricao": "2026-01-05",
                "valor_inscrito": "300.00",
                "observacao": "Inscrição de saldo liquidado.",
            },
        )
        self.assertEqual(response_resto.status_code, 302)

        resto = DespRestosPagar.objects.get(numero_inscricao="RP-2026-0001")
        self.assertEqual(resto.status, DespRestosPagar.Status.INSCRITO)

        response_pagto_1 = self.client.post(
            reverse("financeiro:resto_pagamento_create", args=[resto.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "conta_bancaria": self.conta.pk,
                "ordem_pagamento": "OP-0001",
                "data_pagamento": "2026-01-12",
                "valor": "120.00",
                "status": "PAGO",
            },
        )
        self.assertEqual(response_pagto_1.status_code, 302)
        resto.refresh_from_db()
        self.conta.refresh_from_db()

        self.assertEqual(resto.valor_pago, Decimal("120.00"))
        self.assertEqual(resto.status, DespRestosPagar.Status.PARCIAL)
        self.assertEqual(self.conta.saldo_atual, Decimal("880.00"))

        response_pagto_2 = self.client.post(
            reverse("financeiro:resto_pagamento_create", args=[resto.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "conta_bancaria": self.conta.pk,
                "ordem_pagamento": "OP-0002",
                "data_pagamento": "2026-01-25",
                "valor": "180.00",
                "status": "PAGO",
            },
        )
        self.assertEqual(response_pagto_2.status_code, 302)
        resto.refresh_from_db()
        self.conta.refresh_from_db()

        self.assertEqual(resto.valor_pago, Decimal("300.00"))
        self.assertEqual(resto.status, DespRestosPagar.Status.PAGO)
        self.assertEqual(resto.saldo_a_pagar, Decimal("0.00"))
        self.assertEqual(self.conta.saldo_atual, Decimal("700.00"))

        self.assertTrue(FinanceiroLogEvento.objects.filter(evento="RESTO_PAGAR_INSCRITO").exists())
        self.assertEqual(FinanceiroLogEvento.objects.filter(evento="RESTO_PAGAR_PAGAMENTO_REGISTRADO").count(), 2)
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=self.municipio,
                modulo="FINANCEIRO",
                evento="RESTO_PAGAR_INSCRITO",
            ).exists()
        )
        self.assertEqual(
            TransparenciaEventoPublico.objects.filter(
                municipio=self.municipio,
                modulo=TransparenciaEventoPublico.Modulo.FINANCEIRO,
                tipo_evento="RESTOS_PAGAR_PAGAMENTO",
            ).count(),
            2,
        )


class FinanceiroConciliacaoTestCase(TestCase):
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
        self.municipio = Municipio.objects.create(nome="Cidade Tesouraria", uf="MA", ativo=True)
        self.user = self._make_user("tesouraria_muni", "MUNICIPAL", municipio=self.municipio)
        self.exercicio = FinanceiroExercicio.objects.create(municipio=self.municipio, ano=2026)
        self.ug = FinanceiroUnidadeGestora.objects.create(municipio=self.municipio, codigo="2001", nome="UG Tesouraria")
        self.fonte = OrcFonteRecurso.objects.create(municipio=self.municipio, codigo="15000000", nome="Ordinários")
        self.dotacao = OrcDotacao.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio,
            unidade_gestora=self.ug,
            programa_codigo="20",
            programa_nome="Gestão Administrativa",
            acao_codigo="2101",
            acao_nome="Manutenção",
            elemento_despesa="339039",
            fonte=self.fonte,
            valor_inicial=Decimal("5000.00"),
            valor_atualizado=Decimal("5000.00"),
        )
        self.conta = FinanceiroContaBancaria.objects.create(
            municipio=self.municipio,
            unidade_gestora=self.ug,
            banco_codigo="001",
            banco_nome="Banco do Brasil",
            agencia="1234",
            conta="65432-1",
            saldo_atual=Decimal("10000.00"),
        )

        self.receita = RecArrecadacao.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio,
            unidade_gestora=self.ug,
            conta_bancaria=self.conta,
            data_arrecadacao="2026-01-10",
            rubrica_codigo="11125000",
            rubrica_nome="ISS",
            valor=Decimal("250.00"),
            criado_por=self.user,
        )

        self.empenho = DespEmpenho.objects.create(
            municipio=self.municipio,
            exercicio=self.exercicio,
            unidade_gestora=self.ug,
            dotacao=self.dotacao,
            numero="EMP-2026-0500",
            fornecedor_nome="Fornecedor Auto",
            tipo=DespEmpenho.Tipo.ORDINARIO,
            valor_empenhado=Decimal("200.00"),
            criado_por=self.user,
        )
        registrar_empenho(self.empenho, usuario=self.user)
        self.liquidacao = DespLiquidacao.objects.create(
            empenho=self.empenho,
            numero="LIQ-2026-0500",
            data_liquidacao="2026-01-10",
            valor_liquidado=Decimal("100.00"),
            criado_por=self.user,
        )
        registrar_liquidacao(self.liquidacao, usuario=self.user)
        self.pagamento = DespPagamento.objects.create(
            liquidacao=self.liquidacao,
            conta_bancaria=self.conta,
            ordem_pagamento="OP-2026-0500",
            data_pagamento="2026-01-10",
            valor_pago=Decimal("100.00"),
            status=DespPagamento.Status.PAGO,
            criado_por=self.user,
        )
        registrar_pagamento(self.pagamento, usuario=self.user)

    def _upload_csv(self, content: str):
        arquivo = SimpleUploadedFile("extrato.csv", content.encode("utf-8"), content_type="text/csv")
        return self.client.post(
            reverse("financeiro:extrato_create") + f"?municipio={self.municipio.pk}",
            data={
                "exercicio": self.exercicio.pk,
                "conta_bancaria": self.conta.pk,
                "formato": "CSV",
                "arquivo": arquivo,
                "observacao": "Teste automatizado",
            },
        )

    def test_import_csv_and_auto_conciliation(self):
        self.client.force_login(self.user)
        csv_content = "\n".join(
            [
                "data;descricao;valor;tipo;documento",
                "10/01/2026;Arrecadacao ISS;250.00;C;REC-001",
                "10/01/2026;Pagamento fornecedor;100.00;D;OP-2026-0500",
            ]
        )

        response_import = self._upload_csv(csv_content)
        self.assertEqual(response_import.status_code, 302)

        importacao = TesExtratoImportacao.objects.latest("id")
        self.assertEqual(importacao.total_itens, 2)

        response_auto = self.client.get(
            reverse("financeiro:extrato_auto", args=[importacao.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_auto.status_code, 302)

        conciliacoes = RecConciliacaoItem.objects.filter(municipio=self.municipio, extrato_item__importacao=importacao)
        self.assertEqual(conciliacoes.count(), 2)
        self.assertTrue(conciliacoes.filter(referencia_tipo=RecConciliacaoItem.ReferenciaTipo.RECEITA).exists())
        self.assertTrue(conciliacoes.filter(referencia_tipo=RecConciliacaoItem.ReferenciaTipo.PAGAMENTO).exists())

    def test_manual_adjust_and_undo(self):
        self.client.force_login(self.user)
        csv_content = "\n".join(
            [
                "data;descricao;valor;tipo;documento",
                "11/01/2026;Lancamento sem vinculo;15.00;C;AJ-001",
            ]
        )
        response_import = self._upload_csv(csv_content)
        self.assertEqual(response_import.status_code, 302)

        importacao = TesExtratoImportacao.objects.latest("id")
        item = importacao.itens.first()
        self.assertIsNotNone(item)

        response_ajuste = self.client.post(
            reverse("financeiro:extrato_ajuste", args=[item.pk]) + f"?municipio={self.municipio.pk}",
            data={"observacao": "Ajuste manual para fechamento"},
        )
        self.assertEqual(response_ajuste.status_code, 302)
        self.assertTrue(RecConciliacaoItem.objects.filter(extrato_item=item, referencia_tipo="AJUSTE").exists())

        response_desfazer = self.client.get(
            reverse("financeiro:extrato_desfazer", args=[item.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_desfazer.status_code, 302)
        self.assertFalse(RecConciliacaoItem.objects.filter(extrato_item=item).exists())
