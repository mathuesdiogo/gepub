from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Profile
from apps.core.models import AuditoriaEvento, TransparenciaEventoPublico
from apps.org.models import Municipio
from .models import ProcessoAdministrativo


User = get_user_model()


class ProcessosFlowTestCase(TestCase):
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

    def test_create_processo(self):
        municipio = Municipio.objects.create(nome="Cidade Proc", uf="MA", ativo=True)
        user = self._make_user("proc_muni", "MUNICIPAL", municipio=municipio)
        self.client.force_login(user)

        response = self.client.post(
            reverse("processos:create") + f"?municipio={municipio.pk}",
            data={
                "numero": "PROC-2026-0001",
                "tipo": "Compras",
                "assunto": "Aquisicao de material",
                "solicitante_nome": "Setor Administrativo",
                "descricao": "Processo de teste",
                "status": "ABERTO",
                "data_abertura": "2026-02-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProcessoAdministrativo.objects.filter(numero="PROC-2026-0001", municipio=municipio).exists())
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                municipio=municipio,
                modulo="PROCESSOS",
                evento="PROCESSO_CRIADO",
            ).exists()
        )
        self.assertTrue(
            TransparenciaEventoPublico.objects.filter(
                municipio=municipio,
                modulo=TransparenciaEventoPublico.Modulo.PROCESSOS,
                tipo_evento="PROCESSO_CRIADO",
            ).exists()
        )
