from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import UsuarioCreateForm
from apps.accounts.models import AccessPreviewLog, PasswordHistory, Profile, UserManagementAudit
from apps.accounts import security as login_security
from apps.core.security import decrypt_cpf
from apps.org.models import Municipio, MunicipioOnboardingWizard, Secretaria, Unidade, Setor


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
        MunicipioOnboardingWizard.objects.update_or_create(
            user=manager,
            defaults={"municipio": municipio, "current_step": 9, "total_steps": 9, "completed_at": timezone.now()},
        )

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
        MunicipioOnboardingWizard.objects.update_or_create(
            user=manager,
            defaults={"municipio": municipio, "current_step": 9, "total_steps": 9, "completed_at": timezone.now()},
        )

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


class UsuarioCreateFormScopeTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin_form_scope",
            email="admin.form.scope@example.com",
            password="123456",
        )
        self.municipio_a = Municipio.objects.create(nome="Cidade A", uf="MA")
        self.municipio_b = Municipio.objects.create(nome="Cidade B", uf="MA")
        self.secretaria_a1 = Secretaria.objects.create(nome="Edu A", municipio=self.municipio_a, ativo=True)
        self.secretaria_b1 = Secretaria.objects.create(nome="Edu B", municipio=self.municipio_b, ativo=True)

    def test_secretaria_queryset_filtra_por_municipio_selecionado(self):
        form = UsuarioCreateForm(
            user=self.admin,
            data={"municipio": str(self.municipio_a.id)},
        )
        secretarias_ids = set(form.fields["secretaria"].queryset.values_list("id", flat=True))
        self.assertEqual(secretarias_ids, {self.secretaria_a1.id})

    def test_clean_rejeita_secretaria_de_outro_municipio(self):
        form = UsuarioCreateForm(
            user=self.admin,
            data={
                "first_name": "Teste",
                "last_name": "Usuário",
                "email": "teste@example.com",
                "cpf": "123.456.789-01",
                "role": "LEITURA",
                "municipio": str(self.municipio_a.id),
                "secretaria": str(self.secretaria_b1.id),
                "unidade": "",
                "setor": "",
                "turmas": [],
                "ativo": "on",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("secretaria", form.errors)


@patch.dict(
    "os.environ",
    {
        "DJANGO_CPF_HASH_KEY": "hash-key-tests",
        "DJANGO_CPF_ENCRYPTION_KEY": "enc-key-tests",
    },
    clear=False,
)
class UsuarioSenhaCpfFlowTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin_password_policy",
            email="admin.password.policy@example.com",
            password="123456",
        )
        admin_profile = self.admin.profile
        admin_profile.role = "ADMIN"
        admin_profile.must_change_password = False
        admin_profile.ativo = True
        admin_profile.bloqueado = False
        admin_profile.save(update_fields=["role", "must_change_password", "ativo", "bloqueado"])

    def test_usuario_create_sets_initial_password_as_cpf_digits(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:usuario_create"),
            {
                "first_name": "TesteCpf",
                "last_name": "Usuario",
                "email": "",
                "cpf": "123.456.789-01",
                "role": "LEITURA",
                "municipio": "",
                "secretaria": "",
                "unidade": "",
                "setor": "",
                "ativo": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        profile = Profile.objects.select_related("user").filter(user__first_name="TesteCpf").latest("id")
        self.assertTrue(profile.user.check_password("12345678901"))
        self.assertTrue(profile.must_change_password)

    def test_usuario_reset_senha_sets_password_as_cpf_digits(self):
        target = User.objects.create_user(
            username="target_reset_cpf",
            first_name="Reset",
            last_name="Cpf",
            password="SenhaAntiga@123",
        )
        profile = target.profile
        profile.cpf = "987.654.321-00"
        profile.must_change_password = False
        profile.save()

        self.client.force_login(self.admin)
        response = self.client.post(reverse("accounts:usuario_reset_senha", args=[target.id]))
        self.assertEqual(response.status_code, 302)

        target.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(target.check_password("98765432100"))
        self.assertTrue(profile.must_change_password)
        self.assertTrue(
            UserManagementAudit.objects.filter(
                target=target,
                action=UserManagementAudit.Action.RESET_PASSWORD,
            ).exists()
        )

    def test_usuario_reset_senha_requires_valid_cpf(self):
        target = User.objects.create_user(
            username="target_reset_sem_cpf",
            first_name="Reset",
            last_name="SemCpf",
            password="SenhaOriginal@123",
        )
        profile = target.profile
        profile.cpf = ""
        profile.must_change_password = False
        profile.save()

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:usuario_reset_senha", args=[target.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "usuário sem CPF válido")

        target.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(target.check_password("SenhaOriginal@123"))
        self.assertFalse(profile.must_change_password)


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

    @patch("apps.accounts.views.send_mail")
    def test_login_with_mfa_redirects_to_second_factor(self, _send_mail):
        self.profile.mfa_enabled = True
        self.profile.save(update_fields=["mfa_enabled"])

        response = self.client.post(
            reverse("accounts:login"),
            {"codigo_acesso": self.profile.codigo_acesso, "password": "Senha@123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login_mfa"), response.url)


class AccessPreviewAdminFlowTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin_preview",
            email="admin.preview@example.com",
            password="123456",
        )
        admin_profile = self.admin.profile
        admin_profile.role = "ADMIN"
        admin_profile.must_change_password = False
        admin_profile.ativo = True
        admin_profile.bloqueado = False
        admin_profile.save(update_fields=["role", "must_change_password", "ativo", "bloqueado"])

        self.target_user = User.objects.create_user(
            username="target_preview",
            password="123456",
            first_name="Target",
            last_name="Preview",
        )
        target_profile = self.target_user.profile
        target_profile.role = "EDU_COORD"
        target_profile.must_change_password = False
        target_profile.ativo = True
        target_profile.bloqueado = False
        target_profile.save(update_fields=["role", "must_change_password", "ativo", "bloqueado"])

    def test_access_matrix_page_is_available_for_platform_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:acessos_matriz"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mapa institucional de acessos")

    def test_preview_start_and_stop_create_audit_logs(self):
        self.client.force_login(self.admin)

        response_start = self.client.post(
            reverse("accounts:acessos_simular"),
            {
                "mode": "profile",
                "role": "EDU_COORD",
                "target_user": "",
                "municipio": "",
                "secretaria": "",
                "unidade": "",
                "setor": "",
                "local_estrutural": "",
                "next": reverse("core:dashboard"),
            },
        )
        self.assertEqual(response_start.status_code, 302)
        session = self.client.session
        self.assertIn("gepub_access_preview", session)
        self.assertTrue(
            AccessPreviewLog.objects.filter(
                actor=self.admin,
                action=AccessPreviewLog.Action.START,
            ).exists()
        )

        response_stop = self.client.get(reverse("accounts:acessos_simular_encerrar"))
        self.assertEqual(response_stop.status_code, 302)
        session = self.client.session
        self.assertNotIn("gepub_access_preview", session)
        self.assertTrue(
            AccessPreviewLog.objects.filter(
                actor=self.admin,
                action=AccessPreviewLog.Action.STOP,
            ).exists()
        )

    def test_non_platform_admin_cannot_start_preview(self):
        municipio = Municipio.objects.create(nome="Cidade Preview", uf="MA")
        gestor = User.objects.create_user(username="gestor_municipal", password="123456")
        gestor_profile = gestor.profile
        gestor_profile.role = "MUNICIPAL"
        gestor_profile.municipio = municipio
        gestor_profile.must_change_password = False
        gestor_profile.ativo = True
        gestor_profile.save(update_fields=["role", "municipio", "must_change_password", "ativo"])
        MunicipioOnboardingWizard.objects.update_or_create(
            user=gestor,
            defaults={"municipio": municipio, "current_step": 9, "total_steps": 9, "completed_at": timezone.now()},
        )

        self.client.force_login(gestor)
        response = self.client.get(reverse("accounts:acessos_simular"))
        self.assertEqual(response.status_code, 403)


class MunicipalPasswordRedirectFlowTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Muni Loop", uf="MA")
        self.user = User.objects.create_user(username="muni_loop_user", password="Senha@123")
        self.profile = self.user.profile
        self.profile.role = "MUNICIPAL"
        self.profile.ativo = True
        self.profile.municipio = self.municipio
        self.profile.must_change_password = True
        self.profile.save(update_fields=["role", "ativo", "municipio", "must_change_password"])
        self.client.force_login(self.user)

    def test_completed_onboarding_redirects_to_alterar_senha(self):
        MunicipioOnboardingWizard.objects.update_or_create(
            user=self.user,
            defaults={
                "municipio": self.municipio,
                "current_step": 9,
                "total_steps": 9,
                "completed_at": timezone.now(),
            },
        )

        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:alterar_senha"))

    def test_pending_onboarding_redirects_to_onboarding_step_1(self):
        MunicipioOnboardingWizard.objects.update_or_create(
            user=self.user,
            defaults={
                "municipio": self.municipio,
                "current_step": 1,
                "total_steps": 9,
                "completed_at": None,
            },
        )

        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("org:onboarding_wizard_step", kwargs={"step": 1}))

    def test_completed_onboarding_allows_opening_step_1_when_password_expired(self):
        MunicipioOnboardingWizard.objects.update_or_create(
            user=self.user,
            defaults={
                "municipio": self.municipio,
                "current_step": 9,
                "total_steps": 9,
                "completed_at": timezone.now(),
            },
        )

        response = self.client.get(reverse("org:onboarding_wizard_step", kwargs={"step": 1}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nova senha")


class PasswordHistoryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="senha_hist", password="Senha@123")
        self.profile = self.user.profile
        self.profile.must_change_password = False
        self.profile.save(update_fields=["must_change_password"])
        PasswordHistory.objects.create(user=self.user, password_hash=self.user.password)

    def test_alterar_senha_blocks_recent_password_reuse(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:alterar_senha"),
            {"password1": "Senha@123", "password2": "Senha@123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "já foi utilizada recentemente")
