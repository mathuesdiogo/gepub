from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.educacao.models import Aluno, Matricula, Turma
from apps.nee.forms import ApoioMatriculaForm
from apps.nee.models import AcompanhamentoNEE, AlunoNecessidade, PlanoClinicoNEE, TipoNecessidade
from apps.org.models import Municipio, Secretaria, Unidade


class NeeFormsTestCase(TestCase):
    def _turma(self, nome: str):
        municipio = Municipio.objects.create(nome=f"Mun {nome}", uf="MA", ativo=True)
        secretaria = Secretaria.objects.create(municipio=municipio, nome=f"Sec {nome}", ativo=True)
        unidade = Unidade.objects.create(secretaria=secretaria, nome=f"Unid {nome}", tipo=Unidade.Tipo.EDUCACAO, ativo=True)
        return Turma.objects.create(unidade=unidade, nome=f"Turma {nome}", ano_letivo=2026)

    def test_apoio_form_filters_matricula_by_aluno(self):
        turma_a = self._turma("A")
        turma_b = self._turma("B")
        aluno_a = Aluno.objects.create(nome="Aluno A")
        aluno_b = Aluno.objects.create(nome="Aluno B")
        mat_a = Matricula.objects.create(aluno=aluno_a, turma=turma_a)
        Matricula.objects.create(aluno=aluno_b, turma=turma_b)

        form = ApoioMatriculaForm(aluno=aluno_a)
        qs_ids = list(form.fields["matricula"].queryset.values_list("id", flat=True))
        self.assertEqual(qs_ids, [mat_a.id])


class NeeAlertasExpansionTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="nee_alerta", password="123456")
        profile = self.user.profile
        profile.role = "MUNICIPAL"
        profile.ativo = True
        profile.must_change_password = False

        self.municipio = Municipio.objects.create(nome="Mun NEE", uf="MA", ativo=True)
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED NEE", ativo=True)
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola NEE",
            tipo=Unidade.Tipo.EDUCACAO,
            ativo=True,
        )
        profile.municipio = self.municipio
        profile.save(update_fields=["role", "ativo", "must_change_password", "municipio"])
        self.client.force_login(self.user)

        self.turma = Turma.objects.create(unidade=self.unidade, nome="Turma NEE", ano_letivo=2026)
        self.aluno = Aluno.objects.create(nome="Aluno Plano Incompleto")
        self.matricula = Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        tipo = TipoNecessidade.objects.create(nome="TEA")
        AlunoNecessidade.objects.create(aluno=self.aluno, tipo=tipo, ativo=True)
        PlanoClinicoNEE.objects.create(aluno=self.aluno, responsavel=self.user, objetivo_geral="Plano sem objetivo")

    def test_alertas_index_contains_new_cards(self):
        response = self.client.get(reverse("nee:alertas_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sem evolução de plano (30d+)")
        self.assertContains(response, "Plano incompleto")

    def test_alertas_lista_plano_incompleto(self):
        response = self.client.get(reverse("nee:alertas_lista", kwargs={"kind": "plano-incompleto"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aluno Plano Incompleto")


class NeeRelatorioCapacidadeTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="nee_capacidade", password="123456")
        profile = self.user.profile
        profile.role = "MUNICIPAL"
        profile.ativo = True
        profile.must_change_password = False

        self.municipio = Municipio.objects.create(nome="Mun Cap", uf="MA", ativo=True)
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Cap", ativo=True)
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Capacidade",
            tipo=Unidade.Tipo.EDUCACAO,
            ativo=True,
        )
        profile.municipio = self.municipio
        profile.save(update_fields=["role", "ativo", "must_change_password", "municipio"])
        self.client.force_login(self.user)

        turma = Turma.objects.create(unidade=self.unidade, nome="Turma Cap", ano_letivo=2026)
        tipo = TipoNecessidade.objects.create(nome="Deficiência visual")
        for idx in range(2):
            aluno = Aluno.objects.create(nome=f"Aluno Cap {idx}")
            Matricula.objects.create(aluno=aluno, turma=turma, situacao=Matricula.Situacao.ATIVA)
            AlunoNecessidade.objects.create(aluno=aluno, tipo=tipo, ativo=True)
            AcompanhamentoNEE.objects.create(
                aluno=aluno,
                data=timezone.localdate(),
                tipo_evento=AcompanhamentoNEE.TipoEvento.ATENDIMENTO,
                descricao="Registro de acompanhamento",
                autor=self.user,
            )

    def test_relatorio_capacidade_page_and_export(self):
        response = self.client.get(reverse("nee:relatorios_capacidade"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escola Capacidade")

        response_csv = self.client.get(reverse("nee:relatorios_capacidade") + "?export=csv")
        self.assertEqual(response_csv.status_code, 200)
        self.assertIn("text/csv", response_csv["Content-Type"])
