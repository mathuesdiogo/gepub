from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Profile
from apps.org.models import Municipio, Secretaria, Setor, Unidade

from .models import PontoCadastro, PontoFechamentoCompetencia, PontoOcorrencia, PontoVinculoEscala


User = get_user_model()


class PontoWorkflowTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Ponto", uf="MA", ativo=True)
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria ADM", sigla="ADM")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Prefeitura Sede", tipo=Unidade.Tipo.OUTROS)
        self.setor = Setor.objects.create(unidade=self.unidade, nome="Recursos Humanos")

        self.gestor = User.objects.create_user(username="gestor_ponto", password="123")
        self.gestor.profile.role = Profile.Role.MUNICIPAL
        self.gestor.profile.municipio = self.municipio
        self.gestor.profile.must_change_password = False
        self.gestor.profile.save(update_fields=["role", "municipio", "must_change_password"])

        self.servidor = User.objects.create_user(username="servidor_01", first_name="Servidor", password="123")
        self.servidor.profile.role = Profile.Role.UNIDADE
        self.servidor.profile.municipio = self.municipio
        self.servidor.profile.secretaria = self.secretaria
        self.servidor.profile.unidade = self.unidade
        self.servidor.profile.must_change_password = False
        self.servidor.profile.save(
            update_fields=["role", "municipio", "secretaria", "unidade", "must_change_password"]
        )

    def test_full_workflow_escalas_ocorrencias_competencia(self):
        self.client.force_login(self.gestor)

        r_escala = self.client.post(
            reverse("ponto:escala_create"),
            data={
                "secretaria": self.secretaria.pk,
                "unidade": self.unidade.pk,
                "setor": self.setor.pk,
                "codigo": "ESC-ADM",
                "nome": "Escala Administrativa",
                "tipo_turno": "MATUTINO",
                "hora_entrada": "08:00",
                "hora_saida": "17:00",
                "carga_horaria_semanal": "40.00",
                "tolerancia_entrada_min": 10,
                "dias_semana": "SEG,TER,QUA,QUI,SEX",
                "status": "ATIVO",
                "observacao": "Escala base",
            },
        )
        self.assertEqual(r_escala.status_code, 302)
        escala = PontoCadastro.objects.get(codigo="ESC-ADM", municipio=self.municipio)

        r_vinculo = self.client.post(
            reverse("ponto:vinculo_create"),
            data={
                "escala": escala.pk,
                "servidor": self.servidor.pk,
                "unidade": self.unidade.pk,
                "setor": self.setor.pk,
                "data_inicio": "2026-02-01",
                "ativo": "on",
                "observacao": "Lotação principal",
            },
        )
        self.assertEqual(r_vinculo.status_code, 302)
        vinculo = PontoVinculoEscala.objects.get(municipio=self.municipio, servidor=self.servidor, escala=escala)

        r_ocorrencia = self.client.post(
            reverse("ponto:ocorrencia_create"),
            data={
                "servidor": self.servidor.pk,
                "vinculo": vinculo.pk,
                "data_ocorrencia": "2026-02-10",
                "tipo": PontoOcorrencia.Tipo.ATRASO,
                "minutos": 15,
                "descricao": "Atraso por deslocamento",
            },
        )
        self.assertEqual(r_ocorrencia.status_code, 302)
        ocorrencia = PontoOcorrencia.objects.get(municipio=self.municipio, servidor=self.servidor)
        self.assertEqual(ocorrencia.status, PontoOcorrencia.Status.PENDENTE)
        self.assertEqual(ocorrencia.competencia, "2026-02")

        r_aprovacao = self.client.post(reverse("ponto:ocorrencia_aprovar", args=[ocorrencia.pk]))
        self.assertEqual(r_aprovacao.status_code, 302)
        ocorrencia.refresh_from_db()
        self.assertEqual(ocorrencia.status, PontoOcorrencia.Status.APROVADA)

        r_comp = self.client.post(
            reverse("ponto:competencia_create"),
            data={"competencia": "2026-02", "observacao": "Fechamento mensal"},
        )
        self.assertEqual(r_comp.status_code, 302)
        competencia = PontoFechamentoCompetencia.objects.get(municipio=self.municipio, competencia="2026-02")
        self.assertEqual(competencia.status, PontoFechamentoCompetencia.Status.ABERTA)

        r_fechar = self.client.post(reverse("ponto:competencia_fechar", args=[competencia.pk]))
        self.assertEqual(r_fechar.status_code, 302)
        competencia.refresh_from_db()
        self.assertEqual(competencia.status, PontoFechamentoCompetencia.Status.FECHADA)
        self.assertEqual(competencia.total_ocorrencias, 1)
        self.assertEqual(competencia.total_pendentes, 0)
        self.assertGreaterEqual(competencia.total_servidores, 1)

    def test_professor_cannot_access_ponto_module(self):
        professor = User.objects.create_user(username="prof_ponto", password="123")
        professor.profile.role = Profile.Role.PROFESSOR
        professor.profile.municipio = self.municipio
        professor.profile.must_change_password = False
        professor.profile.save(update_fields=["role", "municipio", "must_change_password"])

        self.client.force_login(professor)
        resp = self.client.get(reverse("ponto:index"))
        self.assertEqual(resp.status_code, 403)
