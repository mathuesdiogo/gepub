from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Profile
from apps.org.models import Municipio, Secretaria

from .models import PlanoMunicipal
from .services import MetricaLimite, get_assinatura_ativa, simular_plano, verificar_limite_municipio


class BillingServicesTests(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Teste", uf="MA")

    def test_get_assinatura_ativa_cria_default_starter(self):
        assinatura = get_assinatura_ativa(self.municipio)
        self.assertIsNotNone(assinatura)
        self.assertEqual(assinatura.plano.codigo, PlanoMunicipal.Codigo.STARTER)

    def test_verificar_limite_secretarias_excedido(self):
        assinatura = get_assinatura_ativa(self.municipio)
        self.assertIsNotNone(assinatura)

        for i in range(4):
            Secretaria.objects.create(municipio=self.municipio, nome=f"Secretaria {i+1}", sigla=f"S{i+1}")

        resultado = verificar_limite_municipio(self.municipio, MetricaLimite.SECRETARIAS, incremento=1)
        self.assertFalse(resultado.permitido)
        self.assertEqual(resultado.excedente, 1)

    def test_verificar_limite_usuarios_excedido(self):
        assinatura = get_assinatura_ativa(self.municipio)
        self.assertIsNotNone(assinatura)

        User = get_user_model()
        for i in range(60):
            user = User.objects.create_user(username=f"u{i}", password="123456")
            profile = user.profile
            profile.role = Profile.Role.LEITURA
            profile.municipio = self.municipio
            profile.ativo = True
            profile.bloqueado = False
            profile.save()

        resultado = verificar_limite_municipio(self.municipio, MetricaLimite.USUARIOS, incremento=1)
        self.assertFalse(resultado.permitido)
        self.assertEqual(resultado.excedente, 1)

    def test_simulador_recomenda_municipal(self):
        resultado = simular_plano(secretarias=7, usuarios=120, alunos=4500, atendimentos=25000)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.plano.codigo, PlanoMunicipal.Codigo.MUNICIPAL)
        self.assertGreaterEqual(resultado.total_mensal, resultado.preco_base)
