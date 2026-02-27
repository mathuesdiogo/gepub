from django.test import TestCase
from unittest.mock import patch
from django.urls import reverse

from apps.educacao.models import Aluno
from apps.org.models import Municipio, Secretaria, Unidade
from apps.saude.models import AgendamentoSaude, AtendimentoSaude, EspecialidadeSaude, ProfissionalSaude


class SaudeCPFSecurityTestCase(TestCase):
    def _unidade_saude(self):
        municipio = Municipio.objects.create(nome="Mun Test", uf="MA", ativo=True)
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Sec Test", ativo=True)
        return Unidade.objects.create(secretaria=secretaria, nome="UBS Teste", tipo=Unidade.Tipo.SAUDE, ativo=True)

    @patch.dict(
        "os.environ",
        {
            "DJANGO_CPF_HASH_KEY": "hash-key-tests",
            "DJANGO_CPF_ENCRYPTION_KEY": "enc-key-tests",
        },
        clear=False,
    )
    def test_profissional_and_atendimento_mask_cpf(self):
        unidade = self._unidade_saude()
        aluno = Aluno.objects.create(nome="Paciente Teste", cpf="11122233344")
        profissional = ProfissionalSaude.objects.create(
            unidade=unidade,
            nome="Prof Teste",
            cpf="99988877766",
            cargo=ProfissionalSaude.Cargo.MEDICO,
        )
        profissional.refresh_from_db()
        self.assertEqual(profissional.cpf, "***.***.***-66")
        self.assertTrue(profissional.cpf_enc)
        self.assertTrue(profissional.cpf_hash)

        atendimento = AtendimentoSaude.objects.create(
            unidade=unidade,
            profissional=profissional,
            aluno=aluno,
            paciente_nome="",
            paciente_cpf="",
            tipo=AtendimentoSaude.Tipo.CONSULTA,
        )
        atendimento.refresh_from_db()
        self.assertEqual(atendimento.paciente_nome, "Paciente Teste")
        self.assertEqual(atendimento.paciente_cpf, "***.***.***-44")
        self.assertTrue(atendimento.paciente_cpf_enc)
        self.assertTrue(atendimento.paciente_cpf_hash)


class SaudeHubSmokeTestCase(TestCase):
    def test_new_saude_routes_reverse(self):
        self.assertIn("/saude/especialidades/", reverse("saude:especialidade_list"))
        self.assertIn("/saude/agenda/", reverse("saude:agenda_list"))
        self.assertIn("/saude/agenda/grades/", reverse("saude:grade_list"))
        self.assertIn("/saude/agenda/bloqueios/", reverse("saude:bloqueio_list"))
        self.assertIn("/saude/agenda/fila-espera/", reverse("saude:fila_list"))
        self.assertIn("/saude/procedimentos/", reverse("saude:procedimento_list"))
        self.assertIn("/saude/vacinacao/", reverse("saude:vacinacao_list"))
        self.assertIn("/saude/encaminhamentos/", reverse("saude:encaminhamento_list"))
        self.assertIn("/saude/auditoria/prontuario/", reverse("saude:auditoria_prontuario_list"))
        self.assertIn("/saude/cid/", reverse("saude:cid_list"))
        self.assertIn("/saude/programas/", reverse("saude:programa_list"))
        self.assertIn("/saude/pacientes/", reverse("saude:paciente_list"))
        self.assertIn("/saude/checkins/", reverse("saude:checkin_list"))
        self.assertIn("/saude/medicamentos-uso/", reverse("saude:medicamento_uso_list"))
        self.assertIn("/saude/dispensacoes/", reverse("saude:dispensacao_list"))
        self.assertIn("/saude/exames/fluxo/", reverse("saude:exame_coleta_list"))
        self.assertIn("/saude/internacoes/", reverse("saude:internacao_list"))

    def test_agendamento_str(self):
        municipio = Municipio.objects.create(nome="Mun Hub", uf="MA", ativo=True)
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Sec Hub", ativo=True)
        unidade = Unidade.objects.create(secretaria=secretaria, nome="UBS Hub", tipo=Unidade.Tipo.SAUDE, ativo=True)
        especialidade = EspecialidadeSaude.objects.create(nome="Clínico Geral")
        profissional = ProfissionalSaude.objects.create(
            unidade=unidade,
            especialidade=especialidade,
            nome="Médico Hub",
            cargo=ProfissionalSaude.Cargo.MEDICO,
            cpf="12345678901",
        )
        aluno = Aluno.objects.create(nome="Aluno Hub", cpf="12312312312")
        ag = AgendamentoSaude.objects.create(
            unidade=unidade,
            profissional=profissional,
            especialidade=especialidade,
            aluno=aluno,
            paciente_nome=aluno.nome,
            inicio="2026-02-25T09:00:00-03:00",
            fim="2026-02-25T09:30:00-03:00",
        )
        self.assertIn("Aluno Hub", str(ag))
