from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import Profile
from apps.core.middleware import RBACMiddleware
from apps.core.models import (
    PortalBanner,
    PortalHomeBloco,
    PortalMenuPublico,
    PortalMunicipalConfig,
    PortalPaginaPublica,
    PortalNoticia,
    TransparenciaEventoPublico,
)
from apps.core.rbac import can
from apps.core.services_portal_seed import ensure_portal_seed_for_municipio
from apps.core.views_codes import _resolve_code_to_url, get_code_routes
from apps.org.models import Municipio, MunicipioModuloAtivo, Secretaria, SecretariaModuloAtivo


User = get_user_model()


class RBACTestCase(TestCase):
    def _make_user(self, username: str, role: str):
        user = User.objects.create_user(username=username, password="x")
        profile = getattr(user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=user, role=role, ativo=True)
        else:
            profile.role = role
            profile.ativo = True
        profile.must_change_password = False
        profile.save(update_fields=["role", "ativo", "must_change_password"])
        return user

    def test_can_saude_depends_on_role(self):
        professor = self._make_user("prof_t", "PROFESSOR")
        nee = self._make_user("nee_t", "NEE")
        self.assertFalse(can(professor, "saude"))
        self.assertTrue(can(nee, "saude"))

    def test_rbac_middleware_blocks_saude_for_professor(self):
        factory = RequestFactory()
        request = factory.get("/saude/")
        request.user = self._make_user("prof_mw", "PROFESSOR")
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_rbac_middleware_blocks_financeiro_for_professor(self):
        factory = RequestFactory()
        request = factory.get("/financeiro/")
        request.user = self._make_user("prof_fin_mw", "PROFESSOR")
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_rbac_middleware_blocks_processos_for_professor(self):
        factory = RequestFactory()
        request = factory.get("/processos/")
        request.user = self._make_user("prof_proc_mw", "PROFESSOR")
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_rbac_middleware_redirects_anonymous(self):
        factory = RequestFactory()
        request = factory.get("/educacao/")
        request.user = AnonymousUser()
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 302)

    def test_rbac_middleware_allows_static_paths(self):
        factory = RequestFactory()
        request = factory.get("/static/css/components/forms.css")
        request.user = AnonymousUser()
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_rbac_middleware_allows_public_institucional_page(self):
        factory = RequestFactory()
        request = factory.get("/institucional/")
        request.user = AnonymousUser()
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_rbac_middleware_allows_public_root(self):
        factory = RequestFactory()
        request = factory.get("/")
        request.user = AnonymousUser()
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_rbac_middleware_allows_public_documentacao_page(self):
        factory = RequestFactory()
        request = factory.get("/documentacao/")
        request.user = AnonymousUser()
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_rbac_middleware_allows_public_transparencia_page(self):
        factory = RequestFactory()
        request = factory.get("/transparencia/")
        request.user = AnonymousUser()
        middleware = RBACMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 200)


class GoCodeTestCase(TestCase):
    def _make_user(self, username: str, role: str):
        user = User.objects.create_user(username=username, password="x")
        profile = getattr(user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=user, role=role, ativo=True)
        else:
            profile.role = role
            profile.ativo = True
            profile.save(update_fields=["role", "ativo"])
        return user

    def _code_for_url_name(self, url_name: str) -> str:
        for code, entry in get_code_routes().items():
            if entry.get("url_name") == url_name:
                return code
        self.fail(f"Codigo nao encontrado para rota: {url_name}")

    def test_resolve_code_with_permission(self):
        user = self._make_user("prof_code", "PROFESSOR")
        code = self._code_for_url_name("educacao:aluno_list")
        self.assertEqual(_resolve_code_to_url(user, code), reverse("educacao:aluno_list"))

    def test_resolve_code_without_permission_returns_none(self):
        user = self._make_user("prof_code_denied", "PROFESSOR")
        code = self._code_for_url_name("org:municipio_list")
        self.assertIsNone(_resolve_code_to_url(user, code))

    def test_go_code_redirects_to_dashboard_on_invalid(self):
        user = self._make_user("prof_go", "PROFESSOR")
        user.profile.must_change_password = False
        user.profile.save(update_fields=["must_change_password"])
        self.client.force_login(user)

        response = self.client.get(reverse("core:go_code"), {"c": "99999"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:dashboard"))

    def test_auto_code_routes_include_saude_relatorio(self):
        routes = get_code_routes()
        self.assertTrue(any(e.get("url_name") == "saude:relatorio_mensal" for e in routes.values()))

    def test_code_ranges_follow_namespace_bands(self):
        code_org = int(self._code_for_url_name("org:municipio_list"))
        code_saude = int(self._code_for_url_name("saude:index"))
        code_educacao = int(self._code_for_url_name("educacao:index"))

        self.assertTrue(100 <= code_org <= 199)
        self.assertTrue(200 <= code_saude <= 299)
        self.assertTrue(300 <= code_educacao <= 399)


class PublicHomeRedirectTestCase(TestCase):
    def test_public_home_redirects_authenticated_user_to_dashboard(self):
        user = User.objects.create_user(username="home_auth", password="x")
        profile = getattr(user, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(user)

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:dashboard"))

    def test_public_documentacao_is_accessible_anonymously(self):
        response = self.client.get(reverse("core:documentacao_public"))
        self.assertEqual(response.status_code, 200)

    def test_public_transparencia_is_accessible_anonymously(self):
        response = self.client.get(reverse("core:transparencia_public"))
        self.assertEqual(response.status_code, 200)


class InstitutionalEditorAccessTestCase(TestCase):
    def _make_user(self, username: str, role: str):
        user = User.objects.create_user(username=username, password="x")
        profile = getattr(user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=user, role=role, ativo=True)
        else:
            profile.role = role
            profile.ativo = True
        profile.must_change_password = False
        profile.save(update_fields=["role", "ativo", "must_change_password"])
        return user

    def test_admin_can_access_institutional_editor(self):
        admin_user = self._make_user("inst_admin", "ADMIN")
        self.client.force_login(admin_user)
        response = self.client.get(reverse("core:institutional_admin"))
        self.assertEqual(response.status_code, 200)

    def test_non_admin_forbidden_institutional_editor(self):
        municipal_user = self._make_user("inst_municipal", "MUNICIPAL")
        self.client.force_login(municipal_user)
        response = self.client.get(reverse("core:institutional_admin"))
        self.assertEqual(response.status_code, 403)

    def test_preview_mode_allows_admin(self):
        admin_user = self._make_user("inst_preview_admin", "ADMIN")
        self.client.force_login(admin_user)
        response = self.client.get(reverse("core:institucional_public") + "?preview=1")
        self.assertEqual(response.status_code, 200)

    def test_preview_mode_redirects_non_admin(self):
        municipal_user = self._make_user("inst_preview_muni", "MUNICIPAL")
        self.client.force_login(municipal_user)
        response = self.client.get(reverse("core:institucional_public") + "?preview=1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:dashboard"))


class TransparenciaPublicViewTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Transparente", uf="MA", ativo=True)
        TransparenciaEventoPublico.objects.create(
            municipio=self.municipio,
            modulo=TransparenciaEventoPublico.Modulo.FINANCEIRO,
            tipo_evento="PAGAMENTO",
            titulo="Pagamento OP-1",
            referencia="OP-1",
            valor="150.00",
            publico=True,
        )
        TransparenciaEventoPublico.objects.create(
            municipio=self.municipio,
            modulo=TransparenciaEventoPublico.Modulo.INTEGRACOES,
            tipo_evento="EXECUCAO_INTEGRACAO",
            titulo="Execucao interna",
            referencia="INT-1",
            publico=False,
        )

    def test_list_shows_only_public_events(self):
        response = self.client.get(reverse("core:transparencia_public"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pagamento OP-1")
        self.assertNotContains(response, "Execucao interna")

    def test_filter_by_module(self):
        response = self.client.get(reverse("core:transparencia_public"), {"modulo": "FINANCEIRO"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pagamento OP-1")


class MunicipalAdministrativeAccessTestCase(TestCase):
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

    def test_municipal_has_access_to_financial_and_admin_modules(self):
        municipio = Municipio.objects.create(nome="Cidade Acesso", uf="MA", ativo=True)
        user = self._make_user("municipal_acesso", "MUNICIPAL", municipio=municipio)
        self.client.force_login(user)

        urls = [
            reverse("financeiro:index"),
            reverse("processos:list"),
            reverse("compras:requisicao_list"),
            reverse("compras:licitacao_list"),
            reverse("contratos:list"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, msg=f"Falhou acesso municipal em {url}")

    def test_professor_does_not_access_financial_and_admin_modules(self):
        municipio = Municipio.objects.create(nome="Cidade Bloqueio", uf="MA", ativo=True)
        user = self._make_user("prof_bloqueio", "PROFESSOR", municipio=municipio)
        self.client.force_login(user)

        urls = [
            reverse("financeiro:index"),
            reverse("processos:list"),
            reverse("compras:requisicao_list"),
            reverse("compras:licitacao_list"),
            reverse("contratos:list"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, msg=f"Professor não deveria acessar {url}")

    def test_municipal_with_module_catalog_blocks_non_activated_modules(self):
        municipio = Municipio.objects.create(nome="Cidade Catálogo", uf="MA", ativo=True)
        user = self._make_user("municipal_catalogo", "MUNICIPAL", municipio=municipio)
        self.client.force_login(user)

        MunicipioModuloAtivo.objects.create(municipio=municipio, modulo="financeiro", ativo=True)

        response_fin = self.client.get(reverse("financeiro:index"))
        self.assertEqual(response_fin.status_code, 200)

        response_proc = self.client.get(reverse("processos:list"))
        self.assertEqual(response_proc.status_code, 403)

    def test_portal_hides_non_activated_modules_when_catalog_exists(self):
        municipio = Municipio.objects.create(nome="Cidade Portal Catálogo", uf="MA", ativo=True)
        user = self._make_user("municipal_portal_catalogo", "MUNICIPAL", municipio=municipio)
        self.client.force_login(user)

        MunicipioModuloAtivo.objects.create(municipio=municipio, modulo="financeiro", ativo=True)

        response = self.client.get(reverse("portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financeiro")
        self.assertNotContains(response, "Processos")

    def test_secretaria_scope_shows_only_its_activated_modules_in_portal(self):
        municipio = Municipio.objects.create(nome="Cidade Secretaria", uf="MA", ativo=True)
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Secretaria de Saúde", tipo_modelo="saude", ativo=True)
        user = self._make_user("secretaria_modulos", "SECRETARIA", municipio=municipio)

        profile = user.profile
        profile.secretaria = secretaria
        profile.save(update_fields=["secretaria"])
        self.client.force_login(user)

        SecretariaModuloAtivo.objects.create(secretaria=secretaria, modulo="saude", ativo=True)
        SecretariaModuloAtivo.objects.create(secretaria=secretaria, modulo="integracoes", ativo=True)

        response = self.client.get(reverse("portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saúde")
        self.assertContains(response, "Integracoes")
        self.assertNotContains(response, "Financeiro")
        self.assertNotContains(response, "Compras")

    def test_secretaria_without_scope_does_not_inherit_municipal_catalog(self):
        municipio = Municipio.objects.create(nome="Cidade Perfil Incompleto", uf="MA", ativo=True)
        user = self._make_user("secretaria_sem_vinculo", "SECRETARIA", municipio=municipio)
        self.client.force_login(user)

        MunicipioModuloAtivo.objects.create(municipio=municipio, modulo="financeiro", ativo=True)
        MunicipioModuloAtivo.objects.create(municipio=municipio, modulo="processos", ativo=True)

        response = self.client.get(reverse("portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sem módulos disponíveis")
        self.assertNotContains(response, "Financeiro")
        self.assertNotContains(response, "Processos")


@override_settings(
    GEPUB_PUBLIC_ROOT_DOMAIN="gepub.com.br",
    GEPUB_APP_HOSTS=["app.gepub.com.br", "127.0.0.1", "localhost"],
    GEPUB_APP_CANONICAL_HOST="app.gepub.com.br",
    ALLOWED_HOSTS=[".gepub.com.br", "testserver", "localhost", "127.0.0.1"],
)
class PublicTenantHostRoutingTestCase(TestCase):
    def setUp(self):
        self.muni_a = Municipio.objects.create(nome="Governador Archer", uf="MA", slug_site="governador-archer")
        self.muni_b = Municipio.objects.create(nome="Cidade B", uf="MA", slug_site="cidade-b")
        TransparenciaEventoPublico.objects.create(
            municipio=self.muni_a,
            modulo=TransparenciaEventoPublico.Modulo.FINANCEIRO,
            tipo_evento="PAGAMENTO",
            titulo="Evento A",
            publico=True,
        )
        TransparenciaEventoPublico.objects.create(
            municipio=self.muni_b,
            modulo=TransparenciaEventoPublico.Modulo.FINANCEIRO,
            tipo_evento="PAGAMENTO",
            titulo="Evento B",
            publico=True,
        )

    def test_root_on_tenant_host_renders_municipal_public_portal(self):
        response = self.client.get("/", HTTP_HOST="governador-archer.gepub.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Governador Archer")
        self.assertContains(response, "Portal Público Municipal")

    def test_transparencia_on_tenant_host_is_scoped_to_municipio(self):
        response = self.client.get(reverse("core:transparencia_public"), HTTP_HOST="governador-archer.gepub.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evento A")
        self.assertNotContains(response, "Evento B")

    def test_accounts_login_on_tenant_host_redirects_to_app_host(self):
        response = self.client.get(reverse("accounts:login"), HTTP_HOST="governador-archer.gepub.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertIn("app.gepub.com.br/accounts/login/", response["Location"])

    def test_unknown_tenant_slug_returns_404_on_public_home(self):
        response = self.client.get("/", HTTP_HOST="inexistente.gepub.com.br")
        self.assertEqual(response.status_code, 404)


class PortalSeedServiceTestCase(TestCase):
    def test_seed_creates_defaults_and_is_idempotent(self):
        municipio = Municipio.objects.create(
            nome="Cidade Portal Seed",
            uf="MA",
            endereco_prefeitura="Rua Central, 100",
            telefone_prefeitura="(99) 99999-9999",
            email_prefeitura="contato@cidade.gov.br",
        )

        first = ensure_portal_seed_for_municipio(municipio)
        self.assertTrue(first.config_created)
        self.assertGreaterEqual(first.banners_created, 3)
        self.assertGreaterEqual(first.noticias_created, 4)
        self.assertGreaterEqual(first.paginas_created, 3)
        self.assertGreaterEqual(first.menus_created, 6)
        self.assertGreaterEqual(first.blocos_created, 4)

        self.assertTrue(PortalMunicipalConfig.objects.filter(municipio=municipio).exists())
        self.assertGreaterEqual(PortalBanner.objects.filter(municipio=municipio).count(), 3)
        self.assertGreaterEqual(PortalNoticia.objects.filter(municipio=municipio).count(), 4)
        self.assertGreaterEqual(PortalPaginaPublica.objects.filter(municipio=municipio).count(), 3)
        self.assertGreaterEqual(PortalMenuPublico.objects.filter(municipio=municipio).count(), 6)
        self.assertGreaterEqual(PortalHomeBloco.objects.filter(municipio=municipio).count(), 4)

        banners_count = PortalBanner.objects.filter(municipio=municipio).count()
        noticias_count = PortalNoticia.objects.filter(municipio=municipio).count()
        paginas_count = PortalPaginaPublica.objects.filter(municipio=municipio).count()
        menus_count = PortalMenuPublico.objects.filter(municipio=municipio).count()
        blocos_count = PortalHomeBloco.objects.filter(municipio=municipio).count()

        second = ensure_portal_seed_for_municipio(municipio)
        self.assertFalse(second.config_created)
        self.assertEqual(second.banners_created, 0)
        self.assertEqual(second.noticias_created, 0)
        self.assertEqual(second.paginas_created, 0)
        self.assertEqual(second.menus_created, 0)
        self.assertEqual(second.blocos_created, 0)
        self.assertEqual(PortalBanner.objects.filter(municipio=municipio).count(), banners_count)
        self.assertEqual(PortalNoticia.objects.filter(municipio=municipio).count(), noticias_count)
        self.assertEqual(PortalPaginaPublica.objects.filter(municipio=municipio).count(), paginas_count)
        self.assertEqual(PortalMenuPublico.objects.filter(municipio=municipio).count(), menus_count)
        self.assertEqual(PortalHomeBloco.objects.filter(municipio=municipio).count(), blocos_count)
