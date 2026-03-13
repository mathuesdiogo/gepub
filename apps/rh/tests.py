from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile
from apps.org.models import Municipio, Secretaria, Setor, Unidade

from .models import (
    RhCadastro,
    RhPdpNecessidade,
    RhPdpPlano,
    RhRemanejamentoEdital,
    RhRemanejamentoInscricao,
    RhRemanejamentoRecurso,
    RhSubstituicaoServidor,
)


User = get_user_model()


class RhWorkflowsTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade RH", uf="MA", ativo=True)
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria Administração", sigla="SAD")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Prefeitura Sede",
            tipo=Unidade.Tipo.ADMINISTRACAO,
            ativo=True,
        )
        self.setor = Setor.objects.create(unidade=self.unidade, nome="Recursos Humanos", ativo=True)

        self.admin = User.objects.create_superuser(username="admin_rh", password="123456", email="admin@rh.local")
        self._set_profile_scope(self.admin, role=Profile.Role.ADMIN)

        self.user_a = User.objects.create_user(username="servidor_a", password="123456", first_name="Servidor A")
        self._set_profile_scope(self.user_a, role=Profile.Role.UNIDADE)
        self.user_b = User.objects.create_user(username="servidor_b", password="123456", first_name="Servidor B")
        self._set_profile_scope(self.user_b, role=Profile.Role.UNIDADE)

        self.rh_a = RhCadastro.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            setor=self.setor,
            servidor=self.user_a,
            codigo="RH-A",
            matricula="MAT-A",
            nome="Servidor A",
            cargo="Docente",
            status=RhCadastro.Status.ATIVO,
        )
        self.rh_b = RhCadastro.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            setor=self.setor,
            servidor=self.user_b,
            codigo="RH-B",
            matricula="MAT-B",
            nome="Servidor B",
            cargo="Técnico",
            status=RhCadastro.Status.ATIVO,
        )

    def _set_profile_scope(self, user, *, role: str):
        profile = user.profile
        profile.role = role
        profile.municipio = self.municipio
        profile.secretaria = self.secretaria
        profile.unidade = self.unidade
        profile.setor = self.setor
        profile.must_change_password = False
        profile.save(
            update_fields=[
                "role",
                "municipio",
                "secretaria",
                "unidade",
                "setor",
                "must_change_password",
            ]
        )

    def _arquivo(self, nome: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(nome, b"%PDF-1.4\n%%EOF\n", content_type="application/pdf")

    def _create_edital_aberto(self) -> RhRemanejamentoEdital:
        now = timezone.now()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("rh:remanejamento_edital_create"),
            data={
                "municipio": self.municipio.pk,
                "numero": "ED-RH-001/2026",
                "titulo": "Remanejamento 2026",
                "tipo_servidor": RhRemanejamentoEdital.TipoServidor.AMBOS,
                "inscricao_inicio": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "inscricao_fim": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
                "recurso_inicio": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                "recurso_fim": (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                "status": RhRemanejamentoEdital.Status.ABERTO,
            },
        )
        self.assertEqual(response.status_code, 302)
        return RhRemanejamentoEdital.objects.get(numero="ED-RH-001/2026", municipio=self.municipio)

    def test_remanejamento_workflow_completo(self):
        edital = self._create_edital_aberto()

        self.client.force_login(self.admin)
        response_inscricao = self.client.post(
            reverse("rh:remanejamento_inscricao_create", args=[edital.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "servidor": self.rh_a.pk,
                "disciplina_interesse": "Matemática",
                "ingressou_mesma_disciplina": "on",
                "unidades_interesse": [self.unidade.pk],
                "portaria_nomeacao": self._arquivo("nomeacao.pdf"),
                "portaria_lotacao": self._arquivo("lotacao.pdf"),
                "situacao_funcional_arquivo": self._arquivo("situacao.pdf"),
            },
        )
        self.assertEqual(response_inscricao.status_code, 302)
        inscricao = RhRemanejamentoInscricao.objects.get(edital=edital, servidor=self.rh_a)
        self.assertEqual(inscricao.status, RhRemanejamentoInscricao.Status.VALIDA)
        self.assertTrue(inscricao.protocolo.startswith("REM-"))

        self.client.force_login(self.user_a)
        response_cancelar = self.client.post(
            reverse("rh:remanejamento_inscricao_cancelar", args=[inscricao.pk]) + f"?municipio={self.municipio.pk}",
            data={"motivo": "Desistência"},
        )
        self.assertEqual(response_cancelar.status_code, 302)
        inscricao.refresh_from_db()
        self.assertEqual(inscricao.status, RhRemanejamentoInscricao.Status.CANCELADA)

        self.client.force_login(self.admin)
        response_nova = self.client.post(
            reverse("rh:remanejamento_inscricao_create", args=[edital.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "servidor": self.rh_a.pk,
                "disciplina_interesse": "Matemática",
                "unidades_interesse": [self.unidade.pk],
                "portaria_nomeacao": self._arquivo("nomeacao2.pdf"),
                "portaria_lotacao": self._arquivo("lotacao2.pdf"),
                "situacao_funcional_arquivo": self._arquivo("situacao2.pdf"),
            },
        )
        self.assertEqual(response_nova.status_code, 302)
        inscricao_valida = RhRemanejamentoInscricao.objects.get(
            edital=edital,
            servidor=self.rh_a,
            status=RhRemanejamentoInscricao.Status.VALIDA,
        )

        self.client.force_login(self.admin)
        response_recurso = self.client.post(
            reverse("rh:remanejamento_recurso_create", args=[inscricao_valida.pk]) + f"?municipio={self.municipio.pk}",
            data={"texto": "Solicito revisão da análise."},
        )
        self.assertEqual(response_recurso.status_code, 302)
        recurso = RhRemanejamentoRecurso.objects.get(inscricao=inscricao_valida)
        self.assertEqual(recurso.status, RhRemanejamentoRecurso.Status.PENDENTE)

        self.client.force_login(self.admin)
        response_decisao = self.client.post(
            reverse("rh:remanejamento_recurso_decidir", args=[recurso.pk]) + f"?municipio={self.municipio.pk}",
            data={"decisao": RhRemanejamentoRecurso.Status.DEFERIDO, "resposta": "Deferido conforme edital."},
        )
        self.assertEqual(response_decisao.status_code, 302)
        recurso.refresh_from_db()
        self.assertEqual(recurso.status, RhRemanejamentoRecurso.Status.DEFERIDO)
        self.assertEqual(recurso.resposta, "Deferido conforme edital.")

    def test_substituicao_workflow_create_and_cancel(self):
        self.client.force_login(self.admin)
        response_create = self.client.post(
            reverse("rh:substituicao_create"),
            data={
                "municipio": self.municipio.pk,
                "substituido": self.rh_a.pk,
                "substituto": self.rh_b.pk,
                "motivo": "Licença médica do titular.",
                "data_inicio": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "data_fim": (timezone.localdate() + timedelta(days=12)).isoformat(),
                "setores_liberados": [self.setor.pk],
                "modulos_liberados_texto": "Administracao::Protocolo\nEducacao::Diario",
                "grupos_liberados_texto": "TRAMITADOR",
                "tipos_conteudoportal_texto": "PORTARIA",
                "substituto_ja_tramitador": "on",
            },
        )
        self.assertEqual(response_create.status_code, 302)
        sub = RhSubstituicaoServidor.objects.get(municipio=self.municipio, substituido=self.rh_a, substituto=self.rh_b)
        self.assertEqual(sub.status, RhSubstituicaoServidor.Status.AGENDADA)
        self.assertIn("Administracao::Protocolo", sub.modulos_liberados_json)
        self.assertTrue(sub.setores_liberados.filter(pk=self.setor.pk).exists())

        response_cancel = self.client.post(
            reverse("rh:substituicao_cancelar", args=[sub.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_cancel.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, RhSubstituicaoServidor.Status.CANCELADA)

    def test_pdp_workflow_create_necessidade_status_export(self):
        self.client.force_login(self.admin)
        response_plano = self.client.post(
            reverse("rh:pdp_plano_create"),
            data={
                "municipio": self.municipio.pk,
                "ano": 2026,
                "titulo": "PDP 2026 - Cidade RH",
                "inicio_coleta": timezone.localdate().isoformat(),
                "fim_coleta": (timezone.localdate() + timedelta(days=60)).isoformat(),
                "status": RhPdpPlano.Status.COLETA,
            },
        )
        self.assertEqual(response_plano.status_code, 302)
        plano = RhPdpPlano.objects.get(municipio=self.municipio, ano=2026)

        self.client.force_login(self.user_a)
        response_necessidade = self.client.post(
            reverse("rh:pdp_necessidade_create", args=[plano.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "tipo_submissao": RhPdpNecessidade.TipoSubmissao.INDIVIDUAL,
                "setor_lotacao": self.setor.pk,
                "area_estrategica": "Educação",
                "area_tematica": "Avaliação e indicadores",
                "objeto_tematico": "Monitoramento pedagógico",
                "necessidade_a_ser_atendida": "Capacitação para uso de indicadores e recuperação de aprendizagem.",
                "acao_transversal": "on",
                "titulo_acao": "Formação em indicadores educacionais",
                "quantidade_prevista_servidores": 8,
                "carga_horaria_individual_prevista": "40:00",
                "custo_tipo": RhPdpNecessidade.CustoTipo.ONUS_LIMITADO,
                "custo_individual_previsto": "850.00",
                "modalidade": RhPdpNecessidade.Modalidade.SEMIPRESENCIAL,
                "termino_previsto": 2026,
            },
        )
        self.assertEqual(response_necessidade.status_code, 302)
        necessidade = RhPdpNecessidade.objects.get(plano=plano)
        self.assertEqual(necessidade.status, RhPdpNecessidade.Status.ENVIADA)
        self.assertEqual(necessidade.tipo_submissao, RhPdpNecessidade.TipoSubmissao.INDIVIDUAL)
        self.assertEqual(necessidade.servidor_id, self.user_a.pk)

        self.client.force_login(self.admin)
        response_aprovar_local = self.client.post(
            reverse("rh:pdp_necessidade_status", args=[necessidade.pk]) + f"?municipio={self.municipio.pk}",
            data={"acao": "aprovar_local", "parecer": "Aderente ao plano municipal."},
        )
        self.assertEqual(response_aprovar_local.status_code, 302)
        necessidade.refresh_from_db()
        self.assertEqual(necessidade.status, RhPdpNecessidade.Status.APROVADA_LOCAL)

        response_export = self.client.post(
            reverse("rh:pdp_plano_exportar_sipec", args=[plano.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(response_export.status_code, 302)
        plano.refresh_from_db()
        self.assertEqual(plano.status, RhPdpPlano.Status.EXPORTADO_SIPEC)
        self.assertIsNotNone(plano.enviado_sipec_em)

    def test_unidade_sem_manage_nao_acessa_criacao_substituicao(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("rh:substituicao_create") + f"?municipio={self.municipio.pk}")
        self.assertEqual(response.status_code, 403)
