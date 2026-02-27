from django.test import TestCase
from apps.educacao.models import Aluno, Matricula, Turma
from apps.nee.forms import ApoioMatriculaForm
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
