from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Profile
from apps.org.models import Municipio, MunicipioModuloAtivo
from apps.ouvidoria.models import OuvidoriaCadastro, OuvidoriaResposta


User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=["testserver", ".gepub.com.br", "localhost", "127.0.0.1", "app.gepub.com.br"],
    GEPUB_PUBLIC_ROOT_DOMAIN="gepub.com.br",
    GEPUB_APP_HOSTS=["app.gepub.com.br", "127.0.0.1", "localhost"],
    GEPUB_APP_CANONICAL_HOST="app.gepub.com.br",
)
class OuvidoriaPortalFlowTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(
            nome="Cidade Fluxo Ouvidoria",
            uf="MA",
            slug_site="cidade-fluxo-ouvidoria",
            ativo=True,
        )
        MunicipioModuloAtivo.objects.create(municipio=self.municipio, modulo="ouvidoria", ativo=True)

        self.user = User.objects.create_user(
            username="gestor_ouvidoria",
            password="Senha@123456",
            first_name="Gestor",
            last_name="Ouvidoria",
        )
        profile, _ = Profile.objects.get_or_create(user=self.user, defaults={"ativo": True})
        profile.role = "MUNICIPAL"
        profile.ativo = True
        profile.bloqueado = False
        profile.must_change_password = False
        profile.municipio = self.municipio
        profile.save()

    def test_public_open_admin_reply_and_public_tracking(self):
        tenant_host = f"{self.municipio.slug_site}.gepub.com.br"

        # 1) Cidadão abre chamado no portal público do município.
        response_public_create = self.client.post(
            reverse("core:portal_ouvidoria_public"),
            {
                "tipo": "ESIC",
                "assunto": "Solicitação de teste",
                "descricao": "Abrindo chamado pelo portal público.",
                "solicitante_nome": "Cidadão Teste",
                "solicitante_email": "cidadao@teste.local",
                "solicitante_telefone": "99999-0000",
                "prioridade": "MEDIA",
            },
            HTTP_HOST=tenant_host,
        )
        self.assertEqual(response_public_create.status_code, 302)
        self.assertIn("protocolo=", response_public_create["Location"])

        protocolo = response_public_create["Location"].split("protocolo=", 1)[1]
        chamado = OuvidoriaCadastro.objects.filter(municipio=self.municipio, protocolo=protocolo).first()
        self.assertIsNotNone(chamado)
        self.assertEqual(chamado.status, OuvidoriaCadastro.Status.ABERTO)

        # 2) Prefeitura responde no módulo administrativo.
        self.client.force_login(self.user)
        response_admin_reply = self.client.post(
            reverse("ouvidoria:resposta_create") + f"?municipio={self.municipio.pk}",
            {
                "chamado": chamado.pk,
                "resposta": "Resposta oficial da prefeitura.",
                "publico": "on",
            },
            HTTP_HOST="app.gepub.com.br",
        )
        self.assertEqual(response_admin_reply.status_code, 302)

        chamado.refresh_from_db()
        self.assertEqual(chamado.status, OuvidoriaCadastro.Status.RESPONDIDO)
        self.assertTrue(
            OuvidoriaResposta.objects.filter(chamado=chamado, resposta__icontains="Resposta oficial da prefeitura").exists()
        )

        # 3) Cidadão consulta protocolo e enxerga a resposta pública.
        response_public_track = self.client.get(
            reverse("core:portal_ouvidoria_public"),
            {"protocolo": protocolo},
            HTTP_HOST=tenant_host,
        )
        self.assertEqual(response_public_track.status_code, 200)
        self.assertContains(response_public_track, protocolo)
        self.assertContains(response_public_track, "Resposta oficial da prefeitura.")
