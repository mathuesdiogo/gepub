from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch

from apps.billing.models import AssinaturaMunicipio, PlanoMunicipal, SolicitacaoUpgrade
from apps.core.models import PortalHomeBloco, PortalMenuPublico, PortalMunicipalConfig, PortalNoticia, PortalPaginaPublica
from apps.org.services.provisioning import seed_secretaria_templates
from apps.org.models import (
    Municipio,
    Secretaria,
    SecretariaCadastroBase,
    SecretariaConfiguracao,
    Unidade,
    MunicipioModuloAtivo,
    SecretariaModuloAtivo,
    OnboardingStep,
    SecretariaProvisionamento,
    SecretariaTemplate,
)


class OrgModelsSmokeTestCase(TestCase):
    def test_str_methods(self):
        municipio = Municipio.objects.create(nome="Cidade X", uf="MA")
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Educação")
        unidade = Unidade.objects.create(secretaria=secretaria, nome="Escola 1", tipo=Unidade.Tipo.EDUCACAO)

        self.assertIn("Cidade X", str(municipio))
        self.assertEqual(str(secretaria), "Educação")
        self.assertEqual(str(unidade), "Escola 1")


class OrgOnboardingProvisioningTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="gestor_muni", password="123456")
        self.municipio = Municipio.objects.create(nome="Cidade Onboarding", uf="MA")
        profile = getattr(self.user, "profile", None)
        profile.role = "MUNICIPAL"
        profile.ativo = True
        profile.municipio = self.municipio
        profile.must_change_password = False
        profile.save(update_fields=["role", "ativo", "municipio", "must_change_password"])
        seed_secretaria_templates()
        self.client.force_login(self.user)

    def test_onboarding_primeiro_acesso_get(self):
        resp = self.client.get(reverse("org:onboarding_primeiro_acesso"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Onboarding Inicial")

    def test_onboarding_activation_creates_secretaria_and_steps(self):
        payload = {
            "action": "ativar_templates",
            "ativar_educacao": "on",
            "qtd_educacao": "1",
            "nome_educacao": "Secretaria Municipal de Educação",
            "sigla_educacao": "SEMED",
        }
        resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Secretaria.objects.filter(municipio=self.municipio, nome__icontains="Educação").exists())
        self.assertTrue(MunicipioModuloAtivo.objects.filter(municipio=self.municipio, modulo="educacao", ativo=True).exists())
        self.assertTrue(SecretariaModuloAtivo.objects.filter(secretaria__municipio=self.municipio, modulo="educacao", ativo=True).exists())
        self.assertTrue(OnboardingStep.objects.filter(municipio=self.municipio, modulo="educacao").exists())
        self.assertTrue(SecretariaProvisionamento.objects.filter(municipio=self.municipio).exists())
        self.assertTrue(PortalMunicipalConfig.objects.filter(municipio=self.municipio).exists())
        self.assertTrue(PortalNoticia.objects.filter(municipio=self.municipio, slug="bem-vindo-ao-portal").exists())
        self.assertTrue(PortalPaginaPublica.objects.filter(municipio=self.municipio, slug="a-prefeitura").exists())
        self.assertTrue(PortalMenuPublico.objects.filter(municipio=self.municipio, ativo=True).exists())
        self.assertTrue(PortalHomeBloco.objects.filter(municipio=self.municipio, ativo=True).exists())

    def test_seed_catalog_has_macro_templates(self):
        slugs = set(SecretariaTemplate.objects.filter(ativo=True).values_list("slug", flat=True))
        expected = {
            "administracao",
            "financas",
            "planejamento",
            "educacao",
            "saude",
            "obras",
            "agricultura",
            "tecnologia",
            "assistencia_social",
            "meio_ambiente",
            "transporte_mobilidade",
            "cultura_turismo_esporte",
            "desenvolvimento_economico",
            "habitacao_urbanismo",
            "servicos_publicos",
        }
        self.assertTrue(expected.issubset(slugs))

    def test_activation_creates_config_and_base_registry(self):
        payload = {
            "action": "ativar_templates",
            "ativar_agricultura": "on",
            "qtd_agricultura": "1",
            "nome_agricultura": "Secretaria de Agricultura Familiar",
            "sigla_agricultura": "SEAGRI",
        }
        resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertEqual(resp.status_code, 302)
        secretaria = Secretaria.objects.get(municipio=self.municipio, nome="Secretaria de Agricultura Familiar")

        self.assertTrue(secretaria.tipo_modelo)
        self.assertTrue(SecretariaConfiguracao.objects.filter(secretaria=secretaria, chave="numeracao_documentos").exists())
        self.assertTrue(SecretariaCadastroBase.objects.filter(secretaria=secretaria, categoria="PROGRAMA_RURAL").exists())
        self.assertTrue(SecretariaModuloAtivo.objects.filter(secretaria=secretaria, modulo="frota", ativo=True).exists())

    def test_governanca_editor_crud_basico(self):
        secretaria = Secretaria.objects.create(
            municipio=self.municipio,
            nome="Secretaria de Administração",
            sigla="SEMAD",
            tipo_modelo="administracao",
        )

        hub = self.client.get(reverse("org:secretaria_governanca_hub") + f"?municipio={self.municipio.pk}")
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Secretaria de Administração")

        create_cfg = self.client.post(
            reverse("org:secretaria_configuracao_create", args=[secretaria.pk]),
            {
                "secretaria": secretaria.pk,
                "chave": "numeracao_documentos",
                "descricao": "Padrão de numeração",
                "valor": '{"prefixo":"ADM","sequencial_anual": true}',
            },
        )
        self.assertEqual(create_cfg.status_code, 302)
        self.assertTrue(
            SecretariaConfiguracao.objects.filter(secretaria=secretaria, chave="numeracao_documentos").exists()
        )

        create_base = self.client.post(
            reverse("org:secretaria_cadastro_base_create", args=[secretaria.pk]),
            {
                "secretaria": secretaria.pk,
                "categoria": "PROCESSO_TIPO",
                "codigo": "ADMISSAO",
                "nome": "Admissão",
                "ordem": 1,
                "ativo": "on",
                "metadata": "{}",
            },
        )
        self.assertEqual(create_base.status_code, 302)
        self.assertTrue(
            SecretariaCadastroBase.objects.filter(
                secretaria=secretaria,
                categoria="PROCESSO_TIPO",
                nome="Admissão",
            ).exists()
        )

        detail = self.client.get(reverse("org:secretaria_governanca_detail", args=[secretaria.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "numeracao_documentos")
        self.assertContains(detail, "PROCESSO_TIPO")

    def test_onboarding_exibe_alerta_quando_excede_limite_secretarias(self):
        starter = PlanoMunicipal.objects.get(codigo=PlanoMunicipal.Codigo.STARTER)
        AssinaturaMunicipio.objects.create(
            municipio=self.municipio,
            plano=starter,
            status=AssinaturaMunicipio.Status.ATIVO,
            preco_base_congelado=starter.preco_base_mensal,
        )

        payload = {"action": "ativar_templates"}
        for slug in ["administracao", "financas", "planejamento", "educacao", "saude"]:
            payload[f"ativar_{slug}"] = "on"
            payload[f"qtd_{slug}"] = "1"

        resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Limite do plano atingido")

    def test_onboarding_carrinho_extras_cria_solicitacao_upgrade(self):
        starter = PlanoMunicipal.objects.get(codigo=PlanoMunicipal.Codigo.STARTER)
        assinatura = AssinaturaMunicipio.objects.create(
            municipio=self.municipio,
            plano=starter,
            status=AssinaturaMunicipio.Status.ATIVO,
            preco_base_congelado=starter.preco_base_mensal,
        )

        resp = self.client.post(
            reverse("org:onboarding_primeiro_acesso"),
            {
                "action": "solicitar_overage_secretarias",
                "qtd_excedente": "2",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            SolicitacaoUpgrade.objects.filter(
                municipio=self.municipio,
                assinatura=assinatura,
                tipo=SolicitacaoUpgrade.Tipo.SECRETARIAS,
                quantidade=2,
            ).exists()
        )

    def test_onboarding_troca_plano_cria_solicitacao_upgrade(self):
        starter = PlanoMunicipal.objects.get(codigo=PlanoMunicipal.Codigo.STARTER)
        destino = PlanoMunicipal.objects.get(codigo=PlanoMunicipal.Codigo.MUNICIPAL)
        assinatura = AssinaturaMunicipio.objects.create(
            municipio=self.municipio,
            plano=starter,
            status=AssinaturaMunicipio.Status.ATIVO,
            preco_base_congelado=starter.preco_base_mensal,
        )

        resp = self.client.post(
            reverse("org:onboarding_primeiro_acesso"),
            {
                "action": "solicitar_troca_plano",
                "plano_destino_id": str(destino.pk),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            SolicitacaoUpgrade.objects.filter(
                municipio=self.municipio,
                assinatura=assinatura,
                tipo=SolicitacaoUpgrade.Tipo.TROCA_PLANO,
                plano_destino=destino,
            ).exists()
        )

    def test_onboarding_instalacao_nao_quebra_se_validacao_limite_falhar(self):
        payload = {
            "action": "ativar_templates",
            "ativar_educacao": "on",
            "qtd_educacao": "1",
        }
        with patch(
            "apps.org.views_onboarding.verificar_limite_municipio",
            side_effect=Exception("falha de limite"),
        ):
            resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertIn(resp.status_code, {200, 302})
        self.assertTrue(
            Secretaria.objects.filter(
                municipio=self.municipio,
                nome__icontains="Educação",
            ).exists()
        )

    def test_activation_salva_tipo_modelo_com_slug_template(self):
        payload = {
            "action": "ativar_templates",
            "ativar_assistencia_social": "on",
            "qtd_assistencia_social": "1",
            "nome_assistencia_social": "Secretaria de Assistência Social",
            "sigla_assistencia_social": "SEMAS",
        }
        resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertEqual(resp.status_code, 302)
        secretaria = Secretaria.objects.get(
            municipio=self.municipio,
            nome="Secretaria de Assistência Social",
        )
        self.assertEqual(secretaria.tipo_modelo, "assistencia_social")

    def test_onboarding_ignora_selecao_de_template_ja_instalado(self):
        Secretaria.objects.create(
            municipio=self.municipio,
            nome="Secretaria de Administração",
            sigla="SEMAD",
            tipo_modelo="administracao",
        )
        Secretaria.objects.create(
            municipio=self.municipio,
            nome="Secretaria de Educação",
            sigla="SEMED",
            tipo_modelo="educacao",
        )
        Secretaria.objects.create(
            municipio=self.municipio,
            nome="Secretaria de Saúde",
            sigla="SEMUS",
            tipo_modelo="saude",
        )
        payload = {
            "action": "ativar_templates",
            "ativar_educacao": "on",
            "qtd_educacao": "1",
        }
        resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "já estão instalados")
        self.assertEqual(
            Secretaria.objects.filter(
                municipio=self.municipio,
                nome="Secretaria de Educação",
            ).count(),
            1,
        )
        self.assertFalse(SecretariaProvisionamento.objects.filter(municipio=self.municipio).exists())

    def test_onboarding_instala_secretarias_obrigatorias_mesmo_sem_selecao(self):
        payload = {
            "action": "ativar_templates",
        }
        resp = self.client.post(reverse("org:onboarding_primeiro_acesso"), payload)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Secretaria.objects.filter(municipio=self.municipio, tipo_modelo="administracao").exists()
        )
        self.assertTrue(
            Secretaria.objects.filter(municipio=self.municipio, tipo_modelo="educacao").exists()
        )
        self.assertTrue(
            Secretaria.objects.filter(municipio=self.municipio, tipo_modelo="saude").exists()
        )
