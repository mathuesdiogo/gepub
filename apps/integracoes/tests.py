from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Profile
from apps.core.models import AuditoriaEvento, TransparenciaEventoPublico
from apps.org.models import Municipio
from .models import ConectorIntegracao


User = get_user_model()


class IntegracoesTestCase(TestCase):
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

    def test_create_conector(self):
        municipio = Municipio.objects.create(nome="Cidade Integracao", uf="MA", ativo=True)
        user = self._make_user("integ_muni", "MUNICIPAL", municipio=municipio)
        self.client.force_login(user)

        response = self.client.post(
            reverse("integracoes:conector_create") + f"?municipio={municipio.pk}",
            data={
                "nome": "SICONFI Export",
                "dominio": "SICONFI",
                "tipo": "ARQUIVO",
                "endpoint": "",
                "credenciais": "{}",
                "configuracao": "{}",
                "ativo": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ConectorIntegracao.objects.filter(nome="SICONFI Export", municipio=municipio).exists())
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=municipio,
                modulo="INTEGRACOES",
                evento="CONECTOR_CRIADO",
            ).exists()
        )
        self.assertTrue(
            TransparenciaEventoPublico.objects.filter(
                municipio=municipio,
                modulo=TransparenciaEventoPublico.Modulo.INTEGRACOES,
                tipo_evento="CONECTOR_CRIADO",
                publico=False,
            ).exists()
        )
