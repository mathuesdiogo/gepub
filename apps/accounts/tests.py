from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Profile, UserManagementAudit
from apps.accounts import security as login_security
from apps.core.security import decrypt_cpf
from apps.org.models import Municipio, Secretaria, Unidade, Setor


User = get_user_model()


class ProfileCPFSecurityTestCase(TestCase):
    @patch.dict(
        "os.environ",
        {
            "DJANGO_CPF_HASH_KEY": "hash-key-tests",
            "DJANGO_CPF_ENCRYPTION_KEY": "enc-key-tests",
        },
        clear=False,
    )
    def test_profile_save_masks_and_protects_cpf(self):
        user = User.objects.create_user(username="acc_test", password="123")
        profile = user.profile
        profile.role = "LEITURA"
        profile.ativo = True
        profile.cpf = "123.456.789-01"
        profile.save()
        profile.refresh_from_db()

        self.assertEqual(profile.cpf, "***.***.***-01")
        self.assertEqual(profile.cpf_last4, "8901")
        self.assertTrue(profile.cpf_hash)
        self.assertTrue(profile.cpf_enc)
        self.assertEqual(profile.cpf_digits, "12345678901")
        self.assertEqual(decrypt_cpf(profile.cpf_enc), "12345678901")


class UsersListViewTestCase(TestCase):
    def test_usuarios_list_access_for_manager_role(self):
        user = User.objects.create_user(username="gestor_test", password="123")
        profile = user.profile
        profile.role = "UNIDADE"
        profile.ativo = True
        profile.must_change_password = False
        profile.save(update_fields=["role", "ativo", "must_change_password"])

        self.client.force_login(user)
        response = self.client.get(reverse("accounts:usuarios_list"))
        self.assertEqual(response.status_code, 200)

    def test_usuarios_list_filters_blocked_status(self):
        municipio = Municipio.objects.create(nome="Teste Muni", uf="MA")
        secretaria = Secretaria.objects.create(nome="Edu", municipio=municipio)
        unidade = Unidade.objects.create(nome="Unidade 1", secretaria=secretaria)
        setor = Setor.objects.create(nome="Setor 1", unidade=unidade)

        manager = User.objects.create_user(username="gestor2", password="123")
        manager_profile = manager.profile
        manager_profile.role = "MUNICIPAL"
        manager_profile.municipio = municipio
        manager_profile.ativo = True
        manager_profile.must_change_password = False
        manager_profile.save()

        target = User.objects.create_user(username="target_user", password="123")
        target_profile = target.profile
        target_profile.role = "LEITURA"
        target_profile.municipio = municipio
        target_profile.secretaria = secretaria
        target_profile.unidade = unidade
        target_profile.setor = setor
        target_profile.ativo = True
        target_profile.bloqueado = True
        target_profile.save()
        target.is_active = False
        target.save(update_fields=["is_active"])

        self.client.force_login(manager)
        response = self.client.get(reverse("accounts:usuarios_list"), {"status": "BLOQUEADO"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "target_user")

    def test_toggle_bloqueio_creates_audit(self):
        municipio = Municipio.objects.create(nome="Teste Muni B", uf="MA")
        manager = User.objects.create_user(username="gestor3", password="123")
        manager_profile = manager.profile
        manager_profile.role = "MUNICIPAL"
        manager_profile.municipio = municipio
        manager_profile.ativo = True
        manager_profile.must_change_password = False
        manager_profile.save()

        target = User.objects.create_user(username="target_b", password="123")
        target_profile = target.profile
        target_profile.role = "LEITURA"
        target_profile.municipio = municipio
        target_profile.ativo = True
        target_profile.bloqueado = False
        target_profile.save()

        self.client.force_login(manager)
        response = self.client.post(reverse("accounts:usuario_toggle_bloqueio", args=[target.id]))
        self.assertEqual(response.status_code, 302)

        target_profile.refresh_from_db()
        self.assertTrue(target_profile.bloqueado)
        self.assertTrue(
            UserManagementAudit.objects.filter(
                target=target,
                action=UserManagementAudit.Action.BLOCK,
            ).exists()
        )


class LoginSecurityViewTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="login_security", password="Senha@123")
        self.profile = self.user.profile
        self.profile.codigo_acesso = "login.security-2026"
        self.profile.ativo = True
        self.profile.bloqueado = False
        self.profile.must_change_password = False
        self.profile.save(update_fields=["codigo_acesso", "ativo", "bloqueado", "must_change_password"])

    def tearDown(self):
        cache.clear()

    def test_login_invalid_code_and_invalid_password_share_generic_message(self):
        response_code = self.client.post(
            reverse("accounts:login"),
            {"codigo_acesso": "invalido", "password": "Senha@123"},
        )
        self.assertEqual(response_code.status_code, 200)
        self.assertContains(response_code, "Credenciais inválidas. Verifique código e senha.")

        response_password = self.client.post(
            reverse("accounts:login"),
            {"codigo_acesso": self.profile.codigo_acesso, "password": "senha-errada"},
        )
        self.assertEqual(response_password.status_code, 200)
        self.assertContains(response_password, "Credenciais inválidas. Verifique código e senha.")

    @patch.object(login_security, "MAX_ATTEMPTS_PER_CODE", 2)
    @patch.object(login_security, "MAX_ATTEMPTS_PER_IP", 2)
    def test_login_is_locked_after_failed_attempts(self):
        payload = {"codigo_acesso": self.profile.codigo_acesso, "password": "senha-errada"}
        self.client.post(reverse("accounts:login"), payload)
        self.client.post(reverse("accounts:login"), payload)
        response = self.client.post(reverse("accounts:login"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Muitas tentativas. Aguarde alguns minutos e tente novamente.")
