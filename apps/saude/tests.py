from django.test import TestCase
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone

from apps.educacao.models import Aluno
from apps.educacao.models_beneficios import BeneficioEdital, BeneficioEditalInscricao, BeneficioTipo
from apps.org.models import Municipio, Secretaria, Unidade
from apps.saude.models import (
    AgendamentoSaude,
    AtendimentoSaude,
    EspecialidadeSaude,
    FilaEsperaSaude,
    PacienteSaude,
    ProfissionalSaude,
)
from django.contrib.auth import get_user_model


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
        self.assertIn("/saude/portal/inscritos/", reverse("saude:portal_inscritos_list"))

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


class SaudeAgendaRegulacaoEnhancementsTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="saude_admin",
            email="saude_admin@example.com",
            password="Senha@123",
        )
        profile = self.user.profile
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.user)

        self.municipio = Municipio.objects.create(nome="Mun Saúde", uf="MA", ativo=True)
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Sec Saúde", ativo=True)
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="UBS Centro",
            tipo=Unidade.Tipo.SAUDE,
            ativo=True,
        )
        self.especialidade = EspecialidadeSaude.objects.create(nome="Pediatria")
        self.profissional = ProfissionalSaude.objects.create(
            unidade=self.unidade,
            especialidade=self.especialidade,
            nome="Dra. Saúde",
            cargo=ProfissionalSaude.Cargo.MEDICO,
        )
        self.aluno = Aluno.objects.create(nome="Paciente Saúde")

    def test_agenda_remarcacao_auto_remarcates_falta(self):
        inicio_original = timezone.now() - timezone.timedelta(days=2)
        agendamento = AgendamentoSaude.objects.create(
            unidade=self.unidade,
            profissional=self.profissional,
            especialidade=self.especialidade,
            aluno=self.aluno,
            paciente_nome=self.aluno.nome,
            inicio=inicio_original,
            fim=inicio_original + timezone.timedelta(minutes=30),
            status=AgendamentoSaude.Status.FALTA,
        )

        response = self.client.post(
            reverse("saude:agenda_remarcacao_auto"),
            {"dias_busca": 30, "limite": 10},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        agendamento.refresh_from_db()
        self.assertEqual(agendamento.status, AgendamentoSaude.Status.MARCADO)
        self.assertGreater(agendamento.inicio, inicio_original)

    def test_fila_list_exposes_sla_metrics(self):
        antigo = timezone.now() - timezone.timedelta(days=20)
        FilaEsperaSaude.objects.create(
            unidade=self.unidade,
            especialidade=self.especialidade,
            aluno=self.aluno,
            paciente_nome="Paciente Aguardando",
            status=FilaEsperaSaude.Status.AGUARDANDO,
        )
        item_antigo = FilaEsperaSaude.objects.create(
            unidade=self.unidade,
            paciente_nome="Paciente SLA",
            status=FilaEsperaSaude.Status.AGUARDANDO,
        )
        FilaEsperaSaude.objects.filter(pk=item_antigo.pk).update(criado_em=antigo)
        FilaEsperaSaude.objects.create(
            unidade=self.unidade,
            paciente_nome="Paciente Chamado",
            status=FilaEsperaSaude.Status.CHAMADO,
        )

        response = self.client.get(reverse("saude:fila_list"))
        self.assertEqual(response.status_code, 200)
        metrics = response.context["metrics"]
        self.assertGreaterEqual(metrics["total"], 3)
        self.assertGreaterEqual(metrics["aguardando"], 2)
        self.assertGreaterEqual(metrics["chamado"], 1)
        self.assertGreaterEqual(metrics["fora_sla"], 1)


class SaudePortalInscritosTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="saude_portal_admin",
            email="saude_portal_admin@example.com",
            password="Senha@123",
        )
        profile = self.user.profile
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.user)

        self.municipio = Municipio.objects.create(nome="Mun Portal Saúde", uf="MA", ativo=True)
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Sec Saúde", ativo=True)
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="UBS Portal", tipo=Unidade.Tipo.SAUDE, ativo=True)
        self.aluno = Aluno.objects.create(nome="Paciente Edital Saúde", ativo=True)
        self.paciente = PacienteSaude.objects.create(unidade_referencia=self.unidade, aluno=self.aluno, nome=self.aluno.nome)

        self.beneficio = BeneficioTipo.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            area=BeneficioTipo.Area.SAUDE,
            nome="Insumo Saúde Portal",
            categoria=BeneficioTipo.Categoria.EQUIPAMENTO,
            periodicidade=BeneficioTipo.Periodicidade.MENSAL,
            status=BeneficioTipo.Status.ATIVO,
            criado_por=self.user,
        )
        self.edital = BeneficioEdital.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            area=BeneficioTipo.Area.SAUDE,
            titulo="Edital Saúde Portal",
            numero_ano="88/2026-SA",
            beneficio=self.beneficio,
            publico_alvo=BeneficioTipo.PublicoAlvo.PROGRAMAS,
            status=BeneficioEdital.Status.EM_ANALISE,
        )
        self.inscricao = BeneficioEditalInscricao.objects.create(
            edital=self.edital,
            aluno=self.aluno,
            status=BeneficioEditalInscricao.Status.EM_ANALISE,
            pontuacao=10,
            criado_por=self.user,
            atualizado_por=self.user,
            dados_json={"avaliacao": {"pendencias_documentos": ["Comprovante de residência"]}},
        )

    def test_portal_inscritos_list_get(self):
        resp = self.client.get(reverse("saude:portal_inscritos_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Portal de Inscritos")
        self.assertContains(resp, self.aluno.nome)

    def test_portal_paciente_inscricoes_get(self):
        resp = self.client.get(reverse("saude:portal_paciente_inscricoes", args=[self.paciente.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Portal de Editais do Paciente")
        self.assertContains(resp, self.edital.numero_ano)

    def test_portal_paciente_inscricao_detail_get(self):
        resp = self.client.get(reverse("saude:portal_paciente_inscricao_detail", args=[self.paciente.pk, self.inscricao.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Acompanhamento da Inscrição")
        self.assertContains(resp, "Pendências documentais")
