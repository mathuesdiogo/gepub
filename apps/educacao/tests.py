from django.test import TestCase
from unittest.mock import patch
from django.urls import reverse
from datetime import date, time, timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.http import HttpResponse
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model

from apps.accounts.models import Profile
from apps.almoxarifado.models import AlmoxarifadoCadastro
from apps.core.models import AuditoriaEvento, TransparenciaEventoPublico
from apps.educacao.forms_horarios import AulaHorarioForm
from apps.educacao.forms_diario import AulaForm
from apps.educacao.forms_programas import ProgramaComplementarParticipacaoCreateForm
from apps.educacao.models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    CoordenacaoEnsino,
    Curso,
    CursoDisciplina,
    MatrizComponente,
    MatrizComponenteEquivalenciaGrupo,
    MatrizComponenteEquivalenciaItem,
    MatrizComponenteRelacao,
    MatrizCurricular,
    Matricula,
    MatriculaCurso,
    MatriculaMovimentacao,
    RenovacaoMatricula,
    RenovacaoMatriculaOferta,
    RenovacaoMatriculaPedido,
    Estagio,
    Turma,
)
from apps.educacao.models_horarios import GradeHorario, AulaHorario
from apps.educacao.models_notas import BNCCCodigo, ComponenteCurricular
from apps.educacao.models_diario import (
    Aula,
    Avaliacao,
    DiarioTurma,
    Frequencia,
    JustificativaFaltaPedido,
    MaterialAulaProfessor,
    Nota,
    PlanoEnsinoProfessor,
)
from apps.educacao.models_periodos import FechamentoPeriodoTurma, PeriodoLetivo
from apps.educacao.models_assistencia import CardapioEscolar, RegistroRefeicaoEscolar, RegistroTransporteEscolar, RotaTransporteEscolar
from apps.educacao.models_calendario import CalendarioEducacionalEvento
from apps.educacao.models_beneficios import (
    BeneficioEdital,
    BeneficioEditalCriterio,
    BeneficioEditalDocumento,
    BeneficioEditalInscricao,
    BeneficioEntrega,
    BeneficioEntregaItem,
    BeneficioTipo,
    BeneficioTipoItem,
)
from apps.educacao.models_informatica import (
    InformaticaCurso,
    InformaticaEncontroSemanal,
    InformaticaGradeHorario,
    InformaticaLaboratorio,
    InformaticaMatricula,
    InformaticaMatriculaMovimentacao,
    InformaticaPlanoEnsinoProfessor,
    InformaticaTurma,
)
from apps.educacao.models_biblioteca import (
    BibliotecaBloqueio,
    BibliotecaEmprestimo,
    BibliotecaEscolar,
    BibliotecaExemplar,
    BibliotecaLivro,
    BibliotecaReserva,
    MatriculaInstitucional,
)
from apps.educacao.models_programas import (
    ProgramaComplementar,
    ProgramaComplementarHorario,
    ProgramaComplementarOferta,
    ProgramaComplementarParticipacao,
)
from apps.educacao.services_biblioteca import LibraryLoanService
from apps.educacao.services_programas import ProgramasComplementaresService
from apps.educacao.services_matricula import (
    aplicar_movimentacao_matricula,
    desfazer_movimentacao_matricula,
    desfazer_ultima_movimentacao_matricula,
    registrar_movimentacao,
)
from apps.educacao.services_requisitos import (
    avaliar_requisitos_matricula,
    registrar_override_requisitos_matricula,
)
from apps.educacao.services_schedule_conflicts import ScheduleConflictService
from apps.educacao.services_matricula_institucional import InstitutionalEnrollmentService
from apps.educacao.services_turma_setup import (
    clonar_matriz_para_ano,
    preencher_componentes_base_matriz,
)
from apps.educacao.views_renovacao import _processar_pedidos_renovacao
from apps.educacao.models_schedule_conflicts import ScheduleConflictOverride, ScheduleConflictSetting
from apps.org.models import Municipio, Secretaria, Unidade
from apps.processos.models import ProcessoAdministrativo
from apps.ouvidoria.models import OuvidoriaCadastro


class AlunoCPFSecurityTestCase(TestCase):
    @patch.dict(
        "os.environ",
        {
            "DJANGO_CPF_HASH_KEY": "hash-key-tests",
            "DJANGO_CPF_ENCRYPTION_KEY": "enc-key-tests",
        },
        clear=False,
    )
    def test_aluno_save_masks_and_populates_security_fields(self):
        aluno = Aluno.objects.create(nome="Aluno Teste", cpf="987.654.321-00")
        aluno.refresh_from_db()
        self.assertEqual(aluno.cpf, "***.***.***-00")
        self.assertEqual(aluno.cpf_last4, "2100")
        self.assertTrue(aluno.cpf_enc)
        self.assertTrue(aluno.cpf_hash)
        self.assertEqual(aluno.cpf_digits, "98765432100")


class EducacaoRoutesSmokeTestCase(TestCase):
    def test_diario_and_horario_routes_reverse(self):
        self.assertIn("/diario/1/frequencia/2/", reverse("educacao:aula_frequencia", args=[1, 2]))
        self.assertIn("/horarios/turma/1/", reverse("educacao:horario_turma", args=[1]))
        self.assertIn("/api/turmas/1/alunos-suggest/", reverse("educacao:api_alunos_turma_suggest", args=[1]))
        self.assertIn("/professor/prof1/agenda-avaliacoes/", reverse("educacao:professor_agenda_avaliacoes", args=["prof1"]))
        self.assertIn("/professor/prof1/planos-ensino/", reverse("educacao:professor_planos_ensino", args=["prof1"]))
        self.assertIn("/planos-ensino/fluxo/", reverse("educacao:plano_ensino_fluxo_list"))
        self.assertIn("/professor/prof1/materiais/", reverse("educacao:professor_materiais", args=["prof1"]))
        self.assertIn("/informatica/grades/", reverse("educacao:informatica_grade_list"))
        self.assertIn("/informatica/professor/agenda/", reverse("educacao:informatica_professor_agenda"))
        self.assertIn("/informatica/alunos/novo/", reverse("educacao:informatica_aluno_create"))
        self.assertIn("/informatica/api/aluno/1/origem/", reverse("educacao:informatica_api_aluno_origem", args=[1]))
        self.assertIn("/informatica/matriculas/1/remanejar/", reverse("educacao:informatica_matricula_remanejar", args=[1]))
        self.assertIn("/matriculas/renovacao/", reverse("educacao:renovacao_matricula_list"))
        self.assertIn("/turmas/geracao-lote/", reverse("educacao:turma_geracao_lote"))
        self.assertIn("/matriculas/evasao-lote/", reverse("educacao:evasao_lote"))
        self.assertIn("/periodos/fechamento-lote/", reverse("educacao:fechamento_periodo_lote"))
        self.assertIn("/alunos/operacoes-lote/", reverse("educacao:operacoes_lote"))
        self.assertIn("/minicursos/", reverse("educacao:minicurso_dashboard"))
        self.assertIn("/biblioteca/", reverse("educacao:biblioteca_dashboard"))
        self.assertIn("/biblioteca/emprestimos/novo/", reverse("educacao:biblioteca_emprestimo_create"))
        self.assertIn("/biblioteca/reservas/", reverse("educacao:biblioteca_reserva_list"))
        self.assertIn("/biblioteca/relatorios/", reverse("educacao:biblioteca_relatorios"))
        self.assertIn("/programas/", reverse("educacao:programas_dashboard"))
        self.assertIn("/programas/relatorios/", reverse("educacao:programa_complementar_relatorios"))
        self.assertIn("/programas/participacoes/nova/", reverse("educacao:programa_complementar_participacao_create"))
        self.assertIn("/aluno/aln1/ensino/programas/", reverse("educacao:aluno_ensino_programas", args=["aln1"]))
        self.assertIn("/aluno/aln1/ensino/renovacao-matricula/", reverse("educacao:aluno_ensino_renovacao", args=["aln1"]))


class RenovacaoMatriculaModelTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="renovacao_admin",
            email="renovacao.admin@example.com",
            password="123456",
        )
        self.municipio = Municipio.objects.create(nome="Cidade Renovação", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria de Educação")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Renovação",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="6º Ano A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Renovação")

    def test_etapas_por_janela_e_processamento(self):
        hoje = date.today()
        renovacao = RenovacaoMatricula.objects.create(
            descricao="Renovação 2026",
            ano_letivo=2026,
            secretaria=self.secretaria,
            data_inicio=hoje + timedelta(days=2),
            data_fim=hoje + timedelta(days=10),
            criado_por=self.user,
        )
        self.assertEqual(renovacao.etapa_atual(ref_date=hoje), RenovacaoMatricula.Etapa.AGENDADA)
        self.assertEqual(renovacao.etapa_atual(ref_date=hoje + timedelta(days=3)), RenovacaoMatricula.Etapa.AGUARDANDO_MATRICULA)
        self.assertEqual(
            renovacao.etapa_atual(ref_date=hoje + timedelta(days=20)),
            RenovacaoMatricula.Etapa.AGUARDANDO_PROCESSAMENTO,
        )

        renovacao.processado_em = timezone.now()
        renovacao.save(update_fields=["processado_em"])
        self.assertEqual(renovacao.etapa_atual(ref_date=hoje + timedelta(days=20)), RenovacaoMatricula.Etapa.PROCESSADA)

    def test_pedido_deve_ter_oferta_da_mesma_renovacao(self):
        hoje = date.today()
        renovacao_1 = RenovacaoMatricula.objects.create(
            descricao="Renovação A",
            ano_letivo=2026,
            secretaria=self.secretaria,
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=5),
            criado_por=self.user,
        )
        renovacao_2 = RenovacaoMatricula.objects.create(
            descricao="Renovação B",
            ano_letivo=2026,
            secretaria=self.secretaria,
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=5),
            criado_por=self.user,
        )
        oferta = RenovacaoMatriculaOferta.objects.create(renovacao=renovacao_2, turma=self.turma)
        pedido = RenovacaoMatriculaPedido(
            renovacao=renovacao_1,
            aluno=self.aluno,
            oferta=oferta,
            prioridade=1,
        )
        with self.assertRaises(ValidationError):
            pedido.full_clean()


class RenovacaoMatriculaProcessingTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="renovacao_proc_admin",
            email="renovacao.proc@example.com",
            password="123456",
        )
        self.municipio = Municipio.objects.create(nome="Cidade Processamento", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria Municipal de Educação")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Processamento",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma_origem = Turma.objects.create(
            unidade=self.unidade,
            nome="7º Ano A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        self.turma_destino_1 = Turma.objects.create(
            unidade=self.unidade,
            nome="7º Ano B",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        self.turma_destino_2 = Turma.objects.create(
            unidade=self.unidade,
            nome="7º Ano C",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        hoje = date.today()
        self.renovacao = RenovacaoMatricula.objects.create(
            descricao="Renovação Processamento 2026",
            ano_letivo=2026,
            secretaria=self.secretaria,
            data_inicio=hoje - timedelta(days=3),
            data_fim=hoje + timedelta(days=3),
            criado_por=self.user,
        )
        self.oferta_1 = RenovacaoMatriculaOferta.objects.create(
            renovacao=self.renovacao,
            turma=self.turma_destino_1,
        )
        self.oferta_2 = RenovacaoMatriculaOferta.objects.create(
            renovacao=self.renovacao,
            turma=self.turma_destino_2,
        )

    def test_processamento_aprova_maior_prioridade_e_remaneja_matricula_ativa(self):
        aluno = Aluno.objects.create(nome="Aluno Prioridade")
        matricula_origem = Matricula.objects.create(
            aluno=aluno,
            turma=self.turma_origem,
            situacao=Matricula.Situacao.ATIVA,
        )
        pedido_prioridade_2 = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno,
            oferta=self.oferta_1,
            prioridade=2,
        )
        pedido_prioridade_1 = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno,
            oferta=self.oferta_2,
            prioridade=1,
        )

        resultado = _processar_pedidos_renovacao(self.renovacao, self.user)

        self.assertEqual(resultado["total"], 2)
        self.assertEqual(resultado["aprovados"], 1)
        self.assertEqual(resultado["rejeitados"], 1)

        pedido_prioridade_1.refresh_from_db()
        pedido_prioridade_2.refresh_from_db()
        matricula_origem.refresh_from_db()

        self.assertEqual(pedido_prioridade_1.status, RenovacaoMatriculaPedido.Status.APROVADO)
        self.assertEqual(pedido_prioridade_2.status, RenovacaoMatriculaPedido.Status.REJEITADO)
        self.assertEqual(matricula_origem.turma_id, self.turma_destino_2.id)
        self.assertEqual(matricula_origem.situacao, Matricula.Situacao.ATIVA)
        self.assertEqual(Matricula.objects.filter(aluno=aluno).count(), 1)
        self.assertTrue(
            MatriculaMovimentacao.objects.filter(
                matricula=matricula_origem,
                tipo=MatriculaMovimentacao.Tipo.REMANEJAMENTO,
                turma_origem=self.turma_origem,
                turma_destino=self.turma_destino_2,
            ).exists()
        )

    def test_processamento_atualiza_status_do_processo_vinculado(self):
        aluno = Aluno.objects.create(nome="Aluno Processo Vinculado")
        processo = ProcessoAdministrativo.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            numero=f"ALUNO-{date.today().strftime('%Y%m%d')}-7001",
            tipo="RENOVACAO_MATRICULA",
            assunto="Pedido de renovação",
            solicitante_nome=aluno.nome,
            descricao="Fluxo de validação de processo.",
            status=ProcessoAdministrativo.Status.ABERTO,
            criado_por=self.user,
        )
        pedido = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno,
            oferta=self.oferta_1,
            prioridade=1,
            processo_administrativo=processo,
        )

        _processar_pedidos_renovacao(self.renovacao, self.user)
        pedido.refresh_from_db()
        processo.refresh_from_db()

        self.assertEqual(pedido.status, RenovacaoMatriculaPedido.Status.APROVADO)
        self.assertEqual(processo.status, ProcessoAdministrativo.Status.CONCLUIDO)

    def test_processamento_rejeita_quando_oferta_esta_inativa(self):
        aluno = Aluno.objects.create(nome="Aluno Oferta Inativa")
        self.oferta_1.ativo = False
        self.oferta_1.save(update_fields=["ativo"])

        pedido = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno,
            oferta=self.oferta_1,
            prioridade=1,
        )

        resultado = _processar_pedidos_renovacao(self.renovacao, self.user)
        pedido.refresh_from_db()

        self.assertEqual(resultado["total"], 1)
        self.assertEqual(resultado["aprovados"], 0)
        self.assertEqual(resultado["rejeitados"], 1)
        self.assertEqual(pedido.status, RenovacaoMatriculaPedido.Status.REJEITADO)
        self.assertIn("oferta indisponível", pedido.observacao_processamento.lower())
        self.assertFalse(Matricula.objects.filter(aluno=aluno).exists())

    def test_processamento_cria_matricula_quando_nao_existe_ativa_no_ano(self):
        aluno = Aluno.objects.create(nome="Aluno Sem Matrícula")
        pedido = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno,
            oferta=self.oferta_1,
            prioridade=1,
        )

        resultado = _processar_pedidos_renovacao(self.renovacao, self.user)
        pedido.refresh_from_db()

        self.assertEqual(resultado["aprovados"], 1)
        self.assertEqual(pedido.status, RenovacaoMatriculaPedido.Status.APROVADO)
        self.assertIsNotNone(pedido.matricula_resultante)
        self.assertTrue(
            MatriculaMovimentacao.objects.filter(
                matricula=pedido.matricula_resultante,
                tipo=MatriculaMovimentacao.Tipo.CRIACAO,
            ).exists()
        )

    def test_processamento_por_chamada_respeita_prioridade_e_finaliza_quando_zerar_pendencias(self):
        aluno_chamada_1 = Aluno.objects.create(nome="Aluno Chamada 1")
        aluno_chamada_2 = Aluno.objects.create(nome="Aluno Chamada 2")
        pedido_1 = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno_chamada_1,
            oferta=self.oferta_1,
            prioridade=1,
        )
        pedido_2 = RenovacaoMatriculaPedido.objects.create(
            renovacao=self.renovacao,
            aluno=aluno_chamada_2,
            oferta=self.oferta_2,
            prioridade=2,
        )

        resultado_chamada_1 = _processar_pedidos_renovacao(self.renovacao, self.user, prioridade_max=1)
        self.assertEqual(resultado_chamada_1["total"], 1)
        self.assertEqual(resultado_chamada_1["aprovados"], 1)
        self.assertEqual(resultado_chamada_1["rejeitados"], 0)
        self.assertEqual(resultado_chamada_1["pendentes_restantes"], 1)

        pedido_1.refresh_from_db()
        pedido_2.refresh_from_db()
        self.renovacao.refresh_from_db()
        self.assertEqual(pedido_1.status, RenovacaoMatriculaPedido.Status.APROVADO)
        self.assertEqual(pedido_2.status, RenovacaoMatriculaPedido.Status.PENDENTE)
        self.assertIsNone(self.renovacao.processado_em)

        resultado_chamada_2 = _processar_pedidos_renovacao(self.renovacao, self.user, prioridade_max=2)
        self.assertEqual(resultado_chamada_2["total"], 1)
        self.assertEqual(resultado_chamada_2["aprovados"], 1)
        self.assertEqual(resultado_chamada_2["rejeitados"], 0)
        self.assertEqual(resultado_chamada_2["pendentes_restantes"], 0)

        pedido_2.refresh_from_db()
        self.renovacao.refresh_from_db()
        self.assertEqual(pedido_2.status, RenovacaoMatriculaPedido.Status.APROVADO)
        self.assertIsNotNone(self.renovacao.processado_em)


class RenovacaoMatriculaTransparenciaTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="renovacao_trans_admin",
            email="renovacao.trans@example.com",
            password="123456",
            is_superuser=True,
            is_staff=True,
        )
        self.municipio = Municipio.objects.create(nome="Cidade Transparência", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria de Educação")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Transparência",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="8º Ano A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        profile = self.user.profile
        profile.role = Profile.Role.ADMIN
        profile.ativo = True
        profile.municipio = self.municipio
        profile.must_change_password = False
        profile.save(update_fields=["role", "ativo", "municipio", "must_change_password"])
        self.client.force_login(self.user)

    def test_criar_renovacao_publica_evento_transparencia(self):
        response = self.client.post(
            reverse("educacao:renovacao_matricula_list"),
            {
                "_action": "create",
                "descricao": "Renovação Transparência 2026",
                "ano_letivo": 2026,
                "secretaria": self.secretaria.id,
                "data_inicio": "2026-03-01",
                "data_fim": "2026-03-31",
                "observacao": "Janela oficial",
            },
        )
        self.assertEqual(response.status_code, 302)

        renovacao = RenovacaoMatricula.objects.filter(descricao="Renovação Transparência 2026").first()
        self.assertIsNotNone(renovacao)
        evento = TransparenciaEventoPublico.objects.filter(
            municipio=self.municipio,
            tipo_evento="RENOVACAO_CRIADA",
            referencia=f"RENOVACAO-{renovacao.pk}",
        ).first()

        self.assertIsNotNone(evento)
        self.assertEqual(evento.modulo, TransparenciaEventoPublico.Modulo.OUTROS)
        self.assertEqual(evento.dados.get("contexto"), "EDUCACAO_RENOVACAO")
        self.assertEqual(evento.dados.get("renovacao_id"), renovacao.id)
        self.assertEqual(evento.dados.get("ano_letivo"), 2026)

    def test_processar_renovacao_publica_evento_transparencia(self):
        hoje = date.today()
        renovacao = RenovacaoMatricula.objects.create(
            descricao="Renovação Processamento Transparência",
            ano_letivo=2026,
            secretaria=self.secretaria,
            data_inicio=hoje - timedelta(days=2),
            data_fim=hoje + timedelta(days=2),
            criado_por=self.user,
        )
        oferta = RenovacaoMatriculaOferta.objects.create(
            renovacao=renovacao,
            turma=self.turma,
        )
        aluno = Aluno.objects.create(nome="Aluno Transparência")
        RenovacaoMatriculaPedido.objects.create(
            renovacao=renovacao,
            aluno=aluno,
            oferta=oferta,
            prioridade=1,
        )

        response = self.client.post(
            reverse("educacao:renovacao_matricula_detail", args=[renovacao.id]),
            {"_action": "processar"},
        )
        self.assertEqual(response.status_code, 302)

        evento = TransparenciaEventoPublico.objects.filter(
            municipio=self.municipio,
            tipo_evento="RENOVACAO_PROCESSADA",
            referencia=f"RENOVACAO-{renovacao.pk}",
        ).first()

        self.assertIsNotNone(evento)
        self.assertEqual(evento.modulo, TransparenciaEventoPublico.Modulo.OUTROS)
        self.assertEqual(evento.dados.get("contexto"), "EDUCACAO_RENOVACAO")
        self.assertEqual(evento.dados.get("renovacao_id"), renovacao.id)
        self.assertEqual(evento.dados.get("total_pedidos_processados"), 1)
        self.assertEqual(evento.dados.get("total_aprovados"), 1)
        self.assertEqual(evento.dados.get("total_rejeitados"), 0)


class InformaticaGradeTurmaRulesTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.prof = User.objects.create_user(username="prof_informatica", password="123456")
        self.municipio = Municipio.objects.create(nome="Cidade Info", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SME")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Lab", tipo=Unidade.Tipo.EDUCACAO)
        self.curso = InformaticaCurso.objects.create(
            municipio=self.municipio,
            nome="Informática Básica",
            aulas_por_semana=2,
            duracao_bloco_minutos=60,
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            max_alunos_por_turma=12,
        )
        self.lab = InformaticaLaboratorio.objects.create(
            nome="Lab 01",
            unidade=self.unidade,
            quantidade_computadores=12,
            capacidade_operacional=12,
            status=InformaticaLaboratorio.Status.ATIVO,
        )

    def test_grade_especial_deve_ser_sexta(self):
        grade = InformaticaGradeHorario(
            nome="Sexta Especial",
            codigo="SEXTA-01",
            tipo_grade=InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA,
            laboratorio=self.lab,
            turno=InformaticaGradeHorario.Turno.MANHA,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.QUARTA,
            dia_semana_2=None,
            hora_inicio=time(8, 0),
            hora_fim=time(10, 0),
            duracao_total_minutos=120,
            duracao_aula_minutos=90,
            duracao_intervalo_minutos=30,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
        )
        with self.assertRaises(ValidationError):
            grade.full_clean()

    def test_nao_permite_conflito_grade_mesmo_laboratorio(self):
        InformaticaGradeHorario.objects.create(
            nome="Grade Base",
            codigo="BASE-01",
            tipo_grade=InformaticaGradeHorario.TipoGrade.PADRAO_SEMANAL,
            laboratorio=self.lab,
            turno=InformaticaGradeHorario.Turno.MANHA,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.SEGUNDA,
            dia_semana_2=InformaticaGradeHorario.DiaSemana.QUARTA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            duracao_total_minutos=60,
            duracao_aula_minutos=45,
            duracao_intervalo_minutos=15,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
        )

        grade_conflito = InformaticaGradeHorario(
            nome="Grade Conflito",
            codigo="BASE-02",
            tipo_grade=InformaticaGradeHorario.TipoGrade.PADRAO_SEMANAL,
            laboratorio=self.lab,
            turno=InformaticaGradeHorario.Turno.MANHA,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.SEGUNDA,
            dia_semana_2=InformaticaGradeHorario.DiaSemana.QUINTA,
            hora_inicio=time(8, 30),
            hora_fim=time(9, 30),
            duracao_total_minutos=60,
            duracao_aula_minutos=45,
            duracao_intervalo_minutos=15,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
        )
        with self.assertRaises(ValidationError):
            grade_conflito.full_clean()

    def test_turma_herda_modalidade_e_carga_da_grade(self):
        grade_sexta = InformaticaGradeHorario.objects.create(
            nome="Sexta Especial",
            codigo="SEXTA-02",
            tipo_grade=InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA,
            laboratorio=self.lab,
            turno=InformaticaGradeHorario.Turno.TARDE,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.SEXTA,
            dia_semana_2=None,
            hora_inicio=time(14, 0),
            hora_fim=time(16, 0),
            duracao_total_minutos=120,
            duracao_aula_minutos=90,
            duracao_intervalo_minutos=30,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
            professor_principal=self.prof,
        )

        turma = InformaticaTurma(
            curso=self.curso,
            grade_horario=grade_sexta,
            laboratorio=self.lab,
            codigo="INF-SEXTA-A",
            instrutor=self.prof,
            ano_letivo=2026,
            max_vagas=12,
            status=InformaticaTurma.Status.ATIVA,
        )
        turma.full_clean()
        turma.save()
        turma.refresh_from_db()

        self.assertEqual(turma.turno, grade_sexta.turno)
        self.assertEqual(turma.modalidade_oferta, InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA)
        self.assertTrue(turma.encontro_unico_semana)
        self.assertEqual(turma.carga_horaria_semanal_minutos, 120)


class InformaticaMatriculaProfessorFlowTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="admin_info_flow",
            email="admin.info.flow@example.com",
            password="123456",
        )
        self.prof = User.objects.create_user(username="prof_info_flow", password="123456")
        prof_profile, _ = Profile.objects.get_or_create(user=self.prof, defaults={"ativo": True})
        prof_profile.role = Profile.Role.EDU_PROF
        prof_profile.must_change_password = False
        prof_profile.save(update_fields=["role", "must_change_password"])
        self.prof_sem_turma = User.objects.create_user(username="prof_sem_turma_flow", password="123456")
        prof_sem_turma_profile, _ = Profile.objects.get_or_create(user=self.prof_sem_turma, defaults={"ativo": True})
        prof_sem_turma_profile.role = Profile.Role.EDU_PROF
        prof_sem_turma_profile.must_change_password = False
        prof_sem_turma_profile.save(update_fields=["role", "must_change_password"])

        self.municipio = Municipio.objects.create(nome="Cidade Fluxo", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SME Fluxo")
        self.unidade_origem = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Origem Fluxo",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.unidade_lab = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Lab Fluxo",
            tipo=Unidade.Tipo.EDUCACAO,
        )

        self.aluno = Aluno.objects.create(nome="Aluno Fluxo")
        turma_regular = Turma.objects.create(
            unidade=self.unidade_origem,
            nome="5A Fluxo",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        Matricula.objects.create(
            aluno=self.aluno,
            turma=turma_regular,
            data_matricula=date(2026, 3, 10),
            situacao=Matricula.Situacao.ATIVA,
        )

        self.curso = InformaticaCurso.objects.create(
            municipio=self.municipio,
            nome="Informática Fluxo",
            aulas_por_semana=2,
            duracao_bloco_minutos=60,
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            max_alunos_por_turma=12,
        )
        self.laboratorio = InformaticaLaboratorio.objects.create(
            nome="Lab Fluxo",
            unidade=self.unidade_lab,
            quantidade_computadores=12,
            capacidade_operacional=12,
            status=InformaticaLaboratorio.Status.ATIVO,
        )
        self.grade = InformaticaGradeHorario.objects.create(
            nome="Grade Fluxo",
            codigo="GRD-FLX-01",
            tipo_grade=InformaticaGradeHorario.TipoGrade.PADRAO_SEMANAL,
            laboratorio=self.laboratorio,
            turno=InformaticaGradeHorario.Turno.MANHA,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.SEGUNDA,
            dia_semana_2=InformaticaGradeHorario.DiaSemana.QUARTA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            duracao_total_minutos=60,
            duracao_aula_minutos=45,
            duracao_intervalo_minutos=15,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
            professor_principal=self.prof,
        )
        self.turma_info = InformaticaTurma.objects.create(
            curso=self.curso,
            grade_horario=self.grade,
            laboratorio=self.laboratorio,
            codigo="INF-FLX-01",
            instrutor=self.prof,
            ano_letivo=2026,
            max_vagas=12,
            status=InformaticaTurma.Status.ATIVA,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=self.turma_info,
            grade_horario=self.grade,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.SEGUNDA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=self.turma_info,
            grade_horario=self.grade,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.QUARTA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )

    def test_matricula_autopreenche_origem_pelo_aluno(self):
        from apps.educacao.forms_informatica import InformaticaMatriculaForm

        form = InformaticaMatriculaForm(
            data={
                "aluno": str(self.aluno.id),
                "escola_origem": "",
                "turma": str(self.turma_info.id),
                "status": InformaticaMatricula.Status.MATRICULADO,
                "origem_indicacao": "",
                "prioridade": "0",
                "observacoes": "",
            },
            user=self.admin,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["escola_origem"].id, self.unidade_origem.id)
        self.assertIn("Escola de origem:", form.cleaned_data["origem_indicacao"])

        matricula_info = form.save(commit=False)
        matricula_info.curso = self.turma_info.curso
        matricula_info.criado_por = self.admin
        matricula_info.full_clean()
        matricula_info.save()

        self.assertEqual(matricula_info.escola_origem_id, self.unidade_origem.id)
        self.assertIn("Escola de origem:", matricula_info.origem_indicacao)

    def test_professor_consegue_abrir_fluxo_de_cadastro_e_matricula(self):
        self.client.force_login(self.prof)
        response_matricula = self.client.get(reverse("educacao:informatica_matricula_create"))
        self.assertEqual(response_matricula.status_code, 200)

        response_aluno = self.client.get(reverse("educacao:informatica_aluno_create"))
        self.assertEqual(response_aluno.status_code, 200)

    def test_professor_sem_turma_nao_acessa_fluxo_de_matricula(self):
        self.client.force_login(self.prof_sem_turma)
        response_matricula = self.client.get(reverse("educacao:informatica_matricula_create"))
        self.assertEqual(response_matricula.status_code, 403)

        response_aluno = self.client.get(reverse("educacao:informatica_aluno_create"))
        self.assertEqual(response_aluno.status_code, 403)


class InformaticaMatriculaRemanejamentoTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.coord = User.objects.create_user(username="coord_info_rem", password="123456")
        coord_profile, _ = Profile.objects.get_or_create(user=self.coord, defaults={"ativo": True})
        coord_profile.role = Profile.Role.EDU_COORD
        coord_profile.must_change_password = False
        coord_profile.save(update_fields=["role", "must_change_password"])

        self.prof = User.objects.create_user(username="prof_info_rem", password="123456")
        prof_profile, _ = Profile.objects.get_or_create(user=self.prof, defaults={"ativo": True})
        prof_profile.role = Profile.Role.EDU_PROF
        prof_profile.must_change_password = False
        prof_profile.save(update_fields=["role", "must_change_password"])

        self.municipio = Municipio.objects.create(nome="Cidade Remanejamento", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SME Remanejamento")
        self.unidade_origem = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Origem Remanejamento",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.unidade_lab = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Lab Remanejamento",
            tipo=Unidade.Tipo.EDUCACAO,
        )

        coord_profile.unidade = self.unidade_lab
        coord_profile.save(update_fields=["unidade"])

        self.aluno = Aluno.objects.create(nome="Aluno Remanejamento")
        turma_regular = Turma.objects.create(
            unidade=self.unidade_origem,
            nome="7A Rem",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        Matricula.objects.create(
            aluno=self.aluno,
            turma=turma_regular,
            data_matricula=date(2026, 3, 10),
            situacao=Matricula.Situacao.ATIVA,
        )

        self.curso = InformaticaCurso.objects.create(
            municipio=self.municipio,
            nome="Informática Remanejamento",
            aulas_por_semana=2,
            duracao_bloco_minutos=60,
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            max_alunos_por_turma=12,
        )
        self.laboratorio = InformaticaLaboratorio.objects.create(
            nome="Lab Rem",
            unidade=self.unidade_lab,
            quantidade_computadores=12,
            capacidade_operacional=12,
            status=InformaticaLaboratorio.Status.ATIVO,
        )
        self.grade_origem = InformaticaGradeHorario.objects.create(
            nome="Grade Origem Rem",
            codigo="GRD-REM-01",
            tipo_grade=InformaticaGradeHorario.TipoGrade.PADRAO_SEMANAL,
            laboratorio=self.laboratorio,
            turno=InformaticaGradeHorario.Turno.MANHA,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.SEGUNDA,
            dia_semana_2=InformaticaGradeHorario.DiaSemana.QUARTA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            duracao_total_minutos=60,
            duracao_aula_minutos=45,
            duracao_intervalo_minutos=15,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
            professor_principal=self.prof,
        )
        self.grade_destino = InformaticaGradeHorario.objects.create(
            nome="Grade Destino Rem",
            codigo="GRD-REM-02",
            tipo_grade=InformaticaGradeHorario.TipoGrade.PADRAO_SEMANAL,
            laboratorio=self.laboratorio,
            turno=InformaticaGradeHorario.Turno.TARDE,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.TERCA,
            dia_semana_2=InformaticaGradeHorario.DiaSemana.QUINTA,
            hora_inicio=time(14, 0),
            hora_fim=time(15, 0),
            duracao_total_minutos=60,
            duracao_aula_minutos=45,
            duracao_intervalo_minutos=15,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
            professor_principal=self.prof,
        )
        self.turma_origem = InformaticaTurma.objects.create(
            curso=self.curso,
            grade_horario=self.grade_origem,
            laboratorio=self.laboratorio,
            codigo="INF-REM-01",
            instrutor=self.prof,
            ano_letivo=2026,
            max_vagas=12,
            status=InformaticaTurma.Status.ATIVA,
        )
        self.turma_destino = InformaticaTurma.objects.create(
            curso=self.curso,
            grade_horario=self.grade_destino,
            laboratorio=self.laboratorio,
            codigo="INF-REM-02",
            instrutor=self.prof,
            ano_letivo=2026,
            max_vagas=12,
            status=InformaticaTurma.Status.ATIVA,
        )

        InformaticaEncontroSemanal.objects.create(
            turma=self.turma_origem,
            grade_horario=self.grade_origem,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.SEGUNDA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=self.turma_origem,
            grade_horario=self.grade_origem,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.QUARTA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=self.turma_destino,
            grade_horario=self.grade_destino,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.TERCA,
            hora_inicio=time(14, 0),
            hora_fim=time(15, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=self.turma_destino,
            grade_horario=self.grade_destino,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.QUINTA,
            hora_inicio=time(14, 0),
            hora_fim=time(15, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )

        self.matricula_info = InformaticaMatricula.objects.create(
            aluno=self.aluno,
            escola_origem=self.unidade_origem,
            curso=self.curso,
            turma=self.turma_origem,
            status=InformaticaMatricula.Status.MATRICULADO,
            origem_indicacao="Escola",
            criado_por=self.coord,
        )

    def test_coordenador_remaneja_matricula_com_movimentacao(self):
        self.client.force_login(self.coord)
        response = self.client.post(
            reverse("educacao:informatica_matricula_remanejar", args=[self.matricula_info.pk]),
            {
                "turma_destino": str(self.turma_destino.pk),
                "motivo": "Ajuste pedagógico da turma.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("educacao:informatica_matricula_list"))

        self.matricula_info.refresh_from_db()
        self.assertEqual(self.matricula_info.turma_id, self.turma_destino.id)

        mov = InformaticaMatriculaMovimentacao.objects.get(matricula=self.matricula_info)
        self.assertEqual(mov.tipo, InformaticaMatriculaMovimentacao.Tipo.REMANEJAMENTO)
        self.assertEqual(mov.turma_origem_id, self.turma_origem.id)
        self.assertEqual(mov.turma_destino_id, self.turma_destino.id)
        self.assertEqual(mov.usuario_id, self.coord.id)
        self.assertEqual(mov.status_novo, InformaticaMatricula.Status.MATRICULADO)

    def test_professor_nao_pode_remanejar_matricula(self):
        self.client.force_login(self.prof)
        response = self.client.get(reverse("educacao:informatica_matricula_remanejar", args=[self.matricula_info.pk]))
        self.assertEqual(response.status_code, 403)


class MatriculaMovimentacaoTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="gestor", password="123456")
        self.municipio = Municipio.objects.create(nome="Cidade Teste", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola A", tipo=Unidade.Tipo.EDUCACAO)
        self.turma = Turma.objects.create(unidade=self.unidade, nome="5A", ano_letivo=2026, turno=Turma.Turno.MANHA)
        self.aluno = Aluno.objects.create(nome="Aluno Workflow")
        self.matricula = Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

    def test_registrar_movimentacao_criacao(self):
        mov = registrar_movimentacao(
            matricula=self.matricula,
            tipo=MatriculaMovimentacao.Tipo.CRIACAO,
            usuario=self.user,
            turma_destino=self.turma,
            situacao_nova=Matricula.Situacao.ATIVA,
            motivo="Teste",
        )
        self.assertEqual(mov.aluno_id, self.aluno.id)
        self.assertEqual(mov.matricula_id, self.matricula.id)
        self.assertEqual(mov.tipo, MatriculaMovimentacao.Tipo.CRIACAO)
        self.assertEqual(mov.situacao_nova, Matricula.Situacao.ATIVA)

    def test_aplicar_trancamento_altera_situacao_e_registra_movimento(self):
        resultado = aplicar_movimentacao_matricula(
            matricula=self.matricula,
            tipo=MatriculaMovimentacao.Tipo.TRANCAMENTO,
            usuario=self.user,
            data_referencia=date(2026, 3, 15),
            tipo_trancamento=MatriculaMovimentacao.TipoTrancamento.VOLUNTARIO,
            motivo="Pausa temporária",
        )
        self.matricula.refresh_from_db()
        self.assertEqual(self.matricula.situacao, Matricula.Situacao.TRANCADO)
        self.assertEqual(resultado.movimentacao.tipo, MatriculaMovimentacao.Tipo.TRANCAMENTO)
        self.assertEqual(resultado.movimentacao.situacao_nova, Matricula.Situacao.TRANCADO)
        self.assertEqual(resultado.movimentacao.data_referencia, date(2026, 3, 15))
        self.assertEqual(
            resultado.movimentacao.tipo_trancamento,
            MatriculaMovimentacao.TipoTrancamento.VOLUNTARIO,
        )

    def test_desfazer_ultimo_procedimento_restabelece_estado_anterior(self):
        aplicar_movimentacao_matricula(
            matricula=self.matricula,
            tipo=MatriculaMovimentacao.Tipo.CANCELAMENTO,
            usuario=self.user,
            motivo="Teste cancelamento",
        )
        resultado = desfazer_ultima_movimentacao_matricula(
            matricula=self.matricula,
            usuario=self.user,
            motivo="Correção de lançamento",
        )
        self.matricula.refresh_from_db()
        self.assertEqual(self.matricula.situacao, Matricula.Situacao.ATIVA)
        self.assertEqual(resultado.movimentacao.tipo, MatriculaMovimentacao.Tipo.DESFAZER)
        self.assertEqual(resultado.movimentacao.situacao_nova, Matricula.Situacao.ATIVA)

    def test_desfazer_movimentacao_especifica_exige_ultimo_registro(self):
        mov1 = aplicar_movimentacao_matricula(
            matricula=self.matricula,
            tipo=MatriculaMovimentacao.Tipo.CANCELAMENTO,
            usuario=self.user,
            motivo="Primeiro passo",
        ).movimentacao
        aplicar_movimentacao_matricula(
            matricula=self.matricula,
            tipo=MatriculaMovimentacao.Tipo.REATIVACAO,
            usuario=self.user,
            motivo="Segundo passo",
        )
        with self.assertRaisesMessage(ValueError, "Só é possível desfazer o último procedimento."):
            desfazer_movimentacao_matricula(
                matricula=self.matricula,
                usuario=self.user,
                movimentacao_id=mov1.id,
                motivo="Tentativa fora de ordem",
            )


class HorarioConflitosFormTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.prof1 = User.objects.create_user(username="prof1", password="123456")
        self.prof2 = User.objects.create_user(username="prof2", password="123456")

        municipio = Municipio.objects.create(nome="Cidade Horario", uf="MA")
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Secretaria Educação")
        unidade = Unidade.objects.create(secretaria=secretaria, nome="Escola Horario", tipo=Unidade.Tipo.EDUCACAO)

        self.turma_a = Turma.objects.create(unidade=unidade, nome="6A", ano_letivo=2026, turno=Turma.Turno.MANHA)
        self.turma_b = Turma.objects.create(unidade=unidade, nome="6B", ano_letivo=2026, turno=Turma.Turno.MANHA)

        self.grade_a = GradeHorario.objects.create(turma=self.turma_a)
        self.grade_b = GradeHorario.objects.create(turma=self.turma_b)

    def _base_payload(self):
        return {
            "dia": AulaHorario.Dia.SEG,
            "inicio": "08:00",
            "fim": "08:50",
            "disciplina": "Matemática",
            "professor": self.prof1.pk,
            "sala": "Sala 01",
            "observacoes": "",
        }

    def test_conflito_mesma_turma(self):
        AulaHorario.objects.create(
            grade=self.grade_a,
            dia=AulaHorario.Dia.SEG,
            inicio=time(8, 10),
            fim=time(9, 0),
            disciplina="Português",
            professor=self.prof2,
            sala="Sala 02",
        )
        form = AulaHorarioForm(data=self._base_payload(), grade=self.grade_a)
        self.assertFalse(form.is_valid())
        self.assertIn("Conflito na turma", " ".join(form.non_field_errors()))

    def test_conflito_professor_entre_turmas(self):
        AulaHorario.objects.create(
            grade=self.grade_b,
            dia=AulaHorario.Dia.SEG,
            inicio=time(8, 15),
            fim=time(9, 0),
            disciplina="Ciências",
            professor=self.prof1,
            sala="Sala 03",
        )
        form = AulaHorarioForm(data=self._base_payload(), grade=self.grade_a)
        self.assertFalse(form.is_valid())
        self.assertIn("Professor já alocado", " ".join(form.errors.get("professor", [])))

    def test_conflito_sala_mesma_unidade(self):
        AulaHorario.objects.create(
            grade=self.grade_b,
            dia=AulaHorario.Dia.SEG,
            inicio=time(8, 20),
            fim=time(9, 10),
            disciplina="História",
            professor=self.prof2,
            sala="Sala 01",
        )
        payload = self._base_payload()
        payload["professor"] = self.prof2.pk
        form = AulaHorarioForm(data=payload, grade=self.grade_a)
        self.assertFalse(form.is_valid())
        self.assertIn("Sala ocupada", " ".join(form.errors.get("sala", [])))

    def test_sem_conflitos_form_valido(self):
        AulaHorario.objects.create(
            grade=self.grade_b,
            dia=AulaHorario.Dia.SEG,
            inicio=time(9, 0),
            fim=time(9, 50),
            disciplina="Artes",
            professor=self.prof1,
            sala="Sala 01",
        )
        payload = self._base_payload()
        payload["inicio"] = "10:00"
        payload["fim"] = "10:50"
        form = AulaHorarioForm(data=payload, grade=self.grade_a)
        self.assertTrue(form.is_valid(), form.errors)


class ScheduleConflictServiceTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="schedule_admin",
            password="123456",
            email="schedule.admin@example.com",
        )

        municipio = Municipio.objects.create(nome="Cidade Agenda", uf="MA")
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(secretaria=secretaria, nome="Escola Agenda", tipo=Unidade.Tipo.EDUCACAO)
        self.aluno = Aluno.objects.create(nome="Aluno Agenda")

        self.turma_base = self._create_turma_with_slot("Turma Base", time(8, 0), time(9, 0))
        self.turma_conflito = self._create_turma_with_slot("Turma Conflito", time(8, 30), time(9, 30))
        self.turma_encostada = self._create_turma_with_slot("Turma Encostada", time(9, 0), time(10, 0))

        Matricula.objects.create(
            aluno=self.aluno,
            turma=self.turma_base,
            data_matricula=date(2026, 2, 1),
            situacao=Matricula.Situacao.ATIVA,
        )

    def _create_turma_with_slot(self, nome: str, inicio: time, fim: time) -> Turma:
        turma = Turma.objects.create(
            unidade=self.unidade,
            nome=nome,
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        grade = GradeHorario.objects.create(turma=turma)
        AulaHorario.objects.create(
            grade=grade,
            dia=AulaHorario.Dia.TER,
            inicio=inicio,
            fim=fim,
            disciplina="Oficina",
        )
        return turma

    def test_detecta_conflito_entre_matriculas_ativas(self):
        result = ScheduleConflictService.validate_regular_enrollment(
            aluno=self.aluno,
            turma=self.turma_conflito,
            data_matricula=date(2026, 2, 10),
        )

        self.assertTrue(result.has_conflict)
        self.assertEqual(result.blocking_mode, "block")
        self.assertGreaterEqual(len(result.conflicts), 1)

    def test_permite_intervalos_encostados_por_padrao(self):
        result = ScheduleConflictService.validate_regular_enrollment(
            aluno=self.aluno,
            turma=self.turma_encostada,
            data_matricula=date(2026, 2, 10),
        )
        self.assertFalse(result.has_conflict)

    def test_permite_override_com_auditoria(self):
        result = ScheduleConflictService.ensure_regular_enrollment_allowed(
            aluno=self.aluno,
            turma=self.turma_conflito,
            data_matricula=date(2026, 2, 10),
            allow_override=True,
            override_justificativa="Ajuste pedagógico excepcional.",
            usuario=self.admin,
            contexto="TESTE_OVERRIDE",
            ip_origem="127.0.0.1",
        )

        self.assertTrue(result.has_conflict)
        self.assertEqual(ScheduleConflictOverride.objects.count(), 1)
        override = ScheduleConflictOverride.objects.first()
        self.assertEqual(override.contexto, "TESTE_OVERRIDE")
        self.assertEqual(override.usuario, self.admin)

    def test_modo_warn_nao_bloqueia_fluxo(self):
        ScheduleConflictSetting.objects.create(
            nome="Warn",
            modo_validacao=ScheduleConflictSetting.ValidationMode.WARN,
            ativo=True,
        )
        result = ScheduleConflictService.ensure_regular_enrollment_allowed(
            aluno=self.aluno,
            turma=self.turma_conflito,
            data_matricula=date(2026, 2, 10),
            allow_override=False,
            usuario=self.admin,
            contexto="TESTE_WARN",
        )

        self.assertTrue(result.has_conflict)
        self.assertEqual(result.blocking_mode, "warn")
        self.assertEqual(ScheduleConflictOverride.objects.count(), 0)


class MatriculaInstitucionalBibliotecaTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="biblioteca_admin",
            password="123456",
            email="biblioteca.admin@example.com",
        )

        self.municipio = Municipio.objects.create(nome="Cidade Biblioteca", uf="MA")
        self.secretaria = Secretaria.objects.create(
            municipio=self.municipio,
            nome="Secretaria Educação Biblioteca",
            sigla="GNF",
        )
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Biblioteca",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="8A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Biblioteca")
        self.biblioteca = BibliotecaEscolar.objects.create(
            unidade=self.unidade,
            nome="Biblioteca Central",
            status=BibliotecaEscolar.Status.ATIVA,
            limite_emprestimos_ativos=2,
            dias_prazo_emprestimo=7,
        )
        self.livro = BibliotecaLivro.objects.create(
            biblioteca=self.biblioteca,
            titulo="Dom Casmurro",
            autor="Machado de Assis",
        )
        self.exemplar = BibliotecaExemplar.objects.create(
            livro=self.livro,
            codigo_exemplar="EX-0001",
            status=BibliotecaExemplar.Status.DISPONIVEL,
        )

    def test_matricula_ativa_gera_matricula_institucional(self):
        Matricula.objects.create(
            aluno=self.aluno,
            turma=self.turma,
            data_matricula=date(2026, 2, 1),
            situacao=Matricula.Situacao.ATIVA,
        )
        enrollment = MatriculaInstitucional.objects.get(aluno=self.aluno)
        self.assertTrue(enrollment.numero_matricula.startswith("GNF-2026-"))
        self.assertEqual(enrollment.status, MatriculaInstitucional.Status.ATIVA)

    def test_fluxo_emprestimo_e_devolucao(self):
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        loan = LibraryLoanService.create_loan(
            biblioteca=self.biblioteca,
            aluno=self.aluno,
            exemplar=self.exemplar,
            usuario=self.admin,
        )
        self.exemplar.refresh_from_db()
        self.assertEqual(loan.status, BibliotecaEmprestimo.Status.ATIVO)
        self.assertEqual(self.exemplar.status, BibliotecaExemplar.Status.EMPRESTADO)

        loan = LibraryLoanService.register_return(
            emprestimo=loan,
            usuario=self.admin,
            data_devolucao=date.today(),
        )
        self.exemplar.refresh_from_db()
        self.assertEqual(loan.status, BibliotecaEmprestimo.Status.DEVOLVIDO)
        self.assertEqual(self.exemplar.status, BibliotecaExemplar.Status.DISPONIVEL)

    def test_renovacao_incrementa_prazo(self):
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        loan = LibraryLoanService.create_loan(
            biblioteca=self.biblioteca,
            aluno=self.aluno,
            exemplar=self.exemplar,
            usuario=self.admin,
        )
        due_before = loan.data_prevista_devolucao
        loan = LibraryLoanService.renew_loan(
            emprestimo=loan,
            usuario=self.admin,
            dias_adicionais=5,
            observacoes="Renovação pedagógica.",
        )
        self.assertEqual(loan.status, BibliotecaEmprestimo.Status.RENOVADO)
        self.assertEqual(loan.renovacoes, 1)
        self.assertEqual(loan.data_prevista_devolucao, due_before + timedelta(days=5))

    def test_bloqueio_ativo_impede_emprestimo(self):
        enrollment = InstitutionalEnrollmentService.ensure_for_student(
            aluno=self.aluno,
            unidade=self.unidade,
            ano_referencia=2026,
        )
        BibliotecaBloqueio.objects.create(
            biblioteca=self.biblioteca,
            aluno=self.aluno,
            matricula_institucional=enrollment,
            motivo="Atraso de devolução",
            status=BibliotecaBloqueio.Status.ATIVO,
        )
        with self.assertRaisesMessage(ValueError, "bloqueio ativo"):
            LibraryLoanService.create_loan(
                biblioteca=self.biblioteca,
                aluno=self.aluno,
                exemplar=self.exemplar,
                usuario=self.admin,
            )

    def test_matricula_institucional_nao_ativa_impede_emprestimo(self):
        enrollment = InstitutionalEnrollmentService.ensure_for_student(
            aluno=self.aluno,
            unidade=self.unidade,
            ano_referencia=2026,
        )
        enrollment.status = MatriculaInstitucional.Status.BLOQUEADA
        enrollment.save(update_fields=["status", "atualizado_em"])

        with self.assertRaisesMessage(ValueError, "não está ativa"):
            LibraryLoanService.create_loan(
                biblioteca=self.biblioteca,
                aluno=self.aluno,
                exemplar=self.exemplar,
                usuario=self.admin,
            )

    def test_reserva_do_mesmo_aluno_e_marcada_como_atendida_ao_emprestar(self):
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        reserva = LibraryLoanService.create_reservation(
            biblioteca=self.biblioteca,
            aluno=self.aluno,
            livro=self.livro,
            usuario=self.admin,
            dias_validade=4,
        )
        self.assertEqual(reserva.status, BibliotecaReserva.Status.ATIVA)

        LibraryLoanService.create_loan(
            biblioteca=self.biblioteca,
            aluno=self.aluno,
            exemplar=self.exemplar,
            usuario=self.admin,
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, BibliotecaReserva.Status.ATENDIDA)

    def test_reserva_ativa_de_outro_aluno_impede_renovacao(self):
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        loan = LibraryLoanService.create_loan(
            biblioteca=self.biblioteca,
            aluno=self.aluno,
            exemplar=self.exemplar,
            usuario=self.admin,
        )

        outro_aluno = Aluno.objects.create(nome="Aluno Reserva")
        Matricula.objects.create(aluno=outro_aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        LibraryLoanService.create_reservation(
            biblioteca=self.biblioteca,
            aluno=outro_aluno,
            livro=self.livro,
            usuario=self.admin,
            dias_validade=5,
        )

        with self.assertRaisesMessage(ValueError, "reserva ativa"):
            LibraryLoanService.renew_loan(
                emprestimo=loan,
                usuario=self.admin,
                dias_adicionais=3,
            )


class ProgramasComplementaresTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="programas_admin",
            password="123456",
            email="programas.admin@example.com",
        )
        self.prof = User.objects.create_user(
            username="programas_prof",
            password="123456",
            email="programas.prof@example.com",
        )
        admin_profile = getattr(self.admin, "profile", None)
        if admin_profile:
            admin_profile.must_change_password = False
            admin_profile.ativo = True
            admin_profile.save(update_fields=["must_change_password", "ativo"])

        self.municipio = Municipio.objects.create(nome="Cidade Programas", uf="MA")
        self.secretaria = Secretaria.objects.create(
            municipio=self.municipio,
            nome="Secretaria Programas",
            sigla="GPR",
        )
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Programas",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma_regular = Turma.objects.create(
            unidade=self.unidade,
            nome="7A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        self.aluno = Aluno.objects.create(
            nome="Aluno Programas",
            data_nascimento=date(2013, 5, 10),
        )
        Matricula.objects.create(
            aluno=self.aluno,
            turma=self.turma_regular,
            data_matricula=date(2026, 2, 10),
            situacao=Matricula.Situacao.ATIVA,
        )

        self.programa = ProgramaComplementar.objects.create(
            nome="Ballet Municipal",
            tipo=ProgramaComplementar.Tipo.BALLET,
            slug="ballet-municipal-programas",
            status=ProgramaComplementar.Status.ATIVO,
            secretaria_responsavel=self.secretaria,
            unidade_gestora=self.unidade,
            faixa_etaria_min=8,
            faixa_etaria_max=16,
        )
        self.oferta = ProgramaComplementarOferta.objects.create(
            programa=self.programa,
            unidade=self.unidade,
            ano_letivo=2026,
            codigo="BAL-A-01",
            nome="Ballet A",
            turno=ProgramaComplementarOferta.Turno.MANHA,
            capacidade_maxima=20,
            status=ProgramaComplementarOferta.Status.ATIVA,
            exige_vinculo_escolar_ativo=True,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 12, 10),
            responsavel=self.prof,
        )
        ProgramaComplementarHorario.objects.create(
            oferta=self.oferta,
            dia_semana=ProgramaComplementarHorario.DiaSemana.SEGUNDA,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            frequencia_tipo=ProgramaComplementarHorario.FrequenciaTipo.SEMANAL,
            turno=ProgramaComplementarOferta.Turno.MANHA,
            ativo=True,
        )

    def test_cria_participacao_programa_com_matricula_institucional(self):
        participacao = ProgramasComplementaresService.create_participation(
            aluno=self.aluno,
            oferta=self.oferta,
            usuario=self.admin,
            data_ingresso=date(2026, 3, 1),
            status=ProgramaComplementarParticipacao.Status.ATIVO,
        )
        self.assertEqual(participacao.programa, self.programa)
        self.assertEqual(participacao.oferta, self.oferta)
        self.assertEqual(participacao.status, ProgramaComplementarParticipacao.Status.ATIVO)
        self.assertTrue(participacao.matricula_institucional.numero_matricula.startswith("GPR-2026-"))

    def test_bloqueia_participacao_com_conflito_de_horario(self):
        ProgramasComplementaresService.create_participation(
            aluno=self.aluno,
            oferta=self.oferta,
            usuario=self.admin,
            data_ingresso=date(2026, 3, 1),
            status=ProgramaComplementarParticipacao.Status.ATIVO,
        )
        programa_reforco = ProgramaComplementar.objects.create(
            nome="Reforço Matemática",
            tipo=ProgramaComplementar.Tipo.REFORCO,
            slug="reforco-matematica-programas",
            status=ProgramaComplementar.Status.ATIVO,
            secretaria_responsavel=self.secretaria,
            unidade_gestora=self.unidade,
            faixa_etaria_min=8,
            faixa_etaria_max=16,
        )
        oferta_reforco = ProgramaComplementarOferta.objects.create(
            programa=programa_reforco,
            unidade=self.unidade,
            ano_letivo=2026,
            codigo="REF-MAT-01",
            nome="Reforço MAT 01",
            turno=ProgramaComplementarOferta.Turno.MANHA,
            capacidade_maxima=20,
            status=ProgramaComplementarOferta.Status.ATIVA,
            exige_vinculo_escolar_ativo=True,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 12, 10),
            responsavel=self.prof,
        )
        ProgramaComplementarHorario.objects.create(
            oferta=oferta_reforco,
            dia_semana=ProgramaComplementarHorario.DiaSemana.SEGUNDA,
            hora_inicio=time(8, 30),
            hora_fim=time(9, 30),
            frequencia_tipo=ProgramaComplementarHorario.FrequenciaTipo.SEMANAL,
            turno=ProgramaComplementarOferta.Turno.MANHA,
            ativo=True,
        )

        with self.assertRaisesMessage(ValueError, "Conflito de horário"):
            ProgramasComplementaresService.create_participation(
                aluno=self.aluno,
                oferta=oferta_reforco,
                usuario=self.admin,
                data_ingresso=date(2026, 3, 1),
                status=ProgramaComplementarParticipacao.Status.ATIVO,
            )

    def test_sync_informatica_cria_programa_e_participacao(self):
        laboratorio = InformaticaLaboratorio.objects.create(
            nome="Lab Programas",
            unidade=self.unidade,
            quantidade_computadores=12,
            capacidade_operacional=12,
            status=InformaticaLaboratorio.Status.ATIVO,
        )
        curso = InformaticaCurso.objects.create(
            municipio=self.municipio,
            nome="Informática Programas",
            aulas_por_semana=2,
            duracao_bloco_minutos=60,
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            max_alunos_por_turma=12,
        )
        grade = InformaticaGradeHorario.objects.create(
            nome="Grade Programas",
            codigo="GRD-PRG-01",
            tipo_grade=InformaticaGradeHorario.TipoGrade.PADRAO_SEMANAL,
            laboratorio=laboratorio,
            turno=InformaticaGradeHorario.Turno.MANHA,
            dia_semana_1=InformaticaGradeHorario.DiaSemana.TERCA,
            dia_semana_2=InformaticaGradeHorario.DiaSemana.QUINTA,
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            duracao_total_minutos=60,
            duracao_aula_minutos=45,
            duracao_intervalo_minutos=15,
            capacidade_maxima=12,
            status=InformaticaGradeHorario.Status.ATIVA,
            professor_principal=self.prof,
        )
        turma_info = InformaticaTurma.objects.create(
            curso=curso,
            grade_horario=grade,
            laboratorio=laboratorio,
            codigo="INF-PRG-01",
            instrutor=self.prof,
            ano_letivo=2026,
            max_vagas=12,
            status=InformaticaTurma.Status.ATIVA,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=turma_info,
            grade_horario=grade,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.TERCA,
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )
        InformaticaEncontroSemanal.objects.create(
            turma=turma_info,
            grade_horario=grade,
            dia_semana=InformaticaEncontroSemanal.DiaSemana.QUINTA,
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            minutos_aula_efetiva=45,
            minutos_intervalo_tecnico=15,
            ativo=True,
        )
        matricula_info = InformaticaMatricula.objects.create(
            aluno=self.aluno,
            escola_origem=self.unidade,
            curso=curso,
            turma=turma_info,
            data_matricula=date(2026, 3, 10),
            status=InformaticaMatricula.Status.MATRICULADO,
            criado_por=self.admin,
        )

        participacao = ProgramaComplementarParticipacao.objects.get(legacy_informatica_matricula=matricula_info)
        self.assertEqual(participacao.programa.tipo, ProgramaComplementar.Tipo.INFORMATICA)
        self.assertEqual(participacao.oferta.legacy_informatica_turma, turma_info)
        self.assertEqual(participacao.oferta.horarios.count(), 2)

    def test_override_de_conflito_exige_permissao_de_perfil(self):
        ProgramasComplementaresService.create_participation(
            aluno=self.aluno,
            oferta=self.oferta,
            usuario=self.admin,
            data_ingresso=date(2026, 3, 1),
            status=ProgramaComplementarParticipacao.Status.ATIVO,
        )

        programa_choque = ProgramaComplementar.objects.create(
            nome="Oficina de Teatro",
            tipo=ProgramaComplementar.Tipo.CULTURA,
            slug="oficina-teatro-programas",
            status=ProgramaComplementar.Status.ATIVO,
            secretaria_responsavel=self.secretaria,
            unidade_gestora=self.unidade,
        )
        oferta_choque = ProgramaComplementarOferta.objects.create(
            programa=programa_choque,
            unidade=self.unidade,
            ano_letivo=2026,
            codigo="TEA-01",
            nome="Teatro Turma 01",
            turno=ProgramaComplementarOferta.Turno.MANHA,
            capacidade_maxima=20,
            status=ProgramaComplementarOferta.Status.ATIVA,
            exige_vinculo_escolar_ativo=True,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 12, 10),
            responsavel=self.prof,
        )
        ProgramaComplementarHorario.objects.create(
            oferta=oferta_choque,
            dia_semana=ProgramaComplementarHorario.DiaSemana.SEGUNDA,
            hora_inicio=time(8, 30),
            hora_fim=time(9, 30),
            frequencia_tipo=ProgramaComplementarHorario.FrequenciaTipo.SEMANAL,
            turno=ProgramaComplementarOferta.Turno.MANHA,
            ativo=True,
        )

        with self.assertRaisesMessage(ValueError, "não possui permissão"):
            ProgramasComplementaresService.create_participation(
                aluno=self.aluno,
                oferta=oferta_choque,
                usuario=self.prof,
                data_ingresso=date(2026, 3, 5),
                status=ProgramaComplementarParticipacao.Status.ATIVO,
                allow_override_conflict=True,
                override_justificativa="Necessidade de ajuste excepcional",
            )

    def test_form_de_participacao_oculta_campos_de_override_sem_permissao(self):
        form_sem_override = ProgramaComplementarParticipacaoCreateForm(user=self.admin, allow_override=False)
        self.assertNotIn("allow_override_conflict", form_sem_override.fields)
        self.assertNotIn("override_justificativa", form_sem_override.fields)

        form_com_override = ProgramaComplementarParticipacaoCreateForm(user=self.admin, allow_override=True)
        self.assertIn("allow_override_conflict", form_com_override.fields)
        self.assertIn("override_justificativa", form_com_override.fields)

    def test_relatorios_programas_carrega_e_exporta_csv(self):
        self.client.force_login(self.admin)
        ProgramasComplementaresService.create_participation(
            aluno=self.aluno,
            oferta=self.oferta,
            usuario=self.admin,
            data_ingresso=date(2026, 3, 1),
            status=ProgramaComplementarParticipacao.Status.ATIVO,
        )

        response = self.client.get(reverse("educacao:programa_complementar_relatorios"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Relatórios de Programas")

        csv_response = self.client.get(reverse("educacao:programa_complementar_relatorios"), {"export": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn("programas_relatorios.csv", csv_response["Content-Disposition"])

    def test_area_aluno_programas_aplica_filtro_concluidos(self):
        ProgramasComplementaresService.create_participation(
            aluno=self.aluno,
            oferta=self.oferta,
            usuario=self.admin,
            data_ingresso=date(2026, 3, 1),
            status=ProgramaComplementarParticipacao.Status.ATIVO,
        )

        programa_concluido = ProgramaComplementar.objects.create(
            nome="Música Escolar",
            tipo=ProgramaComplementar.Tipo.CULTURA,
            slug="musica-escolar-programas",
            status=ProgramaComplementar.Status.ATIVO,
            secretaria_responsavel=self.secretaria,
            unidade_gestora=self.unidade,
        )
        oferta_concluida = ProgramaComplementarOferta.objects.create(
            programa=programa_concluido,
            unidade=self.unidade,
            ano_letivo=2026,
            codigo="MUS-01",
            nome="Música Turma 01",
            turno=ProgramaComplementarOferta.Turno.TARDE,
            capacidade_maxima=20,
            status=ProgramaComplementarOferta.Status.ATIVA,
            exige_vinculo_escolar_ativo=True,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 12, 10),
            responsavel=self.prof,
        )
        ProgramaComplementarHorario.objects.create(
            oferta=oferta_concluida,
            dia_semana=ProgramaComplementarHorario.DiaSemana.QUARTA,
            hora_inicio=time(14, 0),
            hora_fim=time(15, 0),
            frequencia_tipo=ProgramaComplementarHorario.FrequenciaTipo.SEMANAL,
            turno=ProgramaComplementarOferta.Turno.TARDE,
            ativo=True,
        )
        ProgramasComplementaresService.create_participation(
            aluno=self.aluno,
            oferta=oferta_concluida,
            usuario=self.admin,
            data_ingresso=date(2026, 3, 2),
            status=ProgramaComplementarParticipacao.Status.CONCLUIDO,
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("educacao:aluno_ensino_programas", args=[str(self.aluno.id)]),
            {"filtro": "concluidos"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filtro_programas"], "concluidos")
        self.assertEqual(len(response.context["participacoes_visiveis"]), 1)
        self.assertEqual(
            response.context["participacoes_visiveis"][0].status,
            ProgramaComplementarParticipacao.Status.CONCLUIDO,
        )


class CensoEscolarViewTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admincenso", password="123456", email="admin@local")
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        municipio = Municipio.objects.create(nome="Cidade Censo", uf="MA")
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(
            secretaria=secretaria,
            nome="Escola Censo",
            tipo=Unidade.Tipo.EDUCACAO,
            codigo_inep="21000000",
        )
        self.turma = Turma.objects.create(unidade=self.unidade, nome="7A", ano_letivo=2026, turno=Turma.Turno.MANHA)
        self.aluno = Aluno.objects.create(nome="Aluno Censo", cpf="123.456.789-10")
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

    def test_censo_escolar_page_loads(self):
        resp = self.client.get(reverse("educacao:censo_escolar"), {"ano": 2026})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Censo Escolar")

    def test_censo_escolar_csv_export(self):
        resp = self.client.get(
            reverse("educacao:censo_escolar"),
            {"ano": 2026, "dataset": "matriculas", "export": "csv"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("censo_2026_matriculas.csv", resp["Content-Disposition"])

    def test_censo_layout_invalid_fallback(self):
        resp = self.client.get(
            reverse("educacao:censo_escolar"),
            {"ano": 2026, "layout": 2035, "dataset": "matriculas"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["layout"], 2026)

    def test_censo_dataset_invalid_fallback(self):
        resp = self.client.get(
            reverse("educacao:censo_escolar"),
            {"ano": 2026, "layout": 2026, "dataset": "xpto"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["dataset"], "matriculas")

    def test_censo_layout_validation_rows_render(self):
        resp = self.client.get(
            reverse("educacao:censo_escolar"),
            {"ano": 2026, "layout": 2026, "dataset": "matriculas"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Validação por Layout")
        self.assertContains(resp, "Unidade da matrícula sem INEP")


class FechamentoHistoricoTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="adminedu", password="123456", email="admin@edu.local")
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        municipio = Municipio.objects.create(nome="Cidade Fechamento", uf="MA")
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Secretaria Educação")
        unidade = Unidade.objects.create(secretaria=secretaria, nome="Escola Fechamento", tipo=Unidade.Tipo.EDUCACAO, codigo_inep="21999999")

        self.turma = Turma.objects.create(unidade=unidade, nome="8A", ano_letivo=2026, turno=Turma.Turno.MANHA)
        self.aluno = Aluno.objects.create(nome="Aluno Histórico", cpf="987.654.321-00")
        self.matricula = Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

        self.periodo = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=1,
            inicio="2026-02-01",
            fim="2026-04-30",
            ativo=True,
        )
        self.diario = DiarioTurma.objects.create(turma=self.turma, professor=self.admin, ano_letivo=2026)
        self.avaliacao = Avaliacao.objects.create(diario=self.diario, periodo=self.periodo, titulo="Prova 1", peso=Decimal("1.00"), nota_maxima=Decimal("10.00"), data="2026-03-10")
        Nota.objects.create(avaliacao=self.avaliacao, aluno=self.aluno, valor=Decimal("8.50"))
        self.aula = Aula.objects.create(diario=self.diario, data="2026-03-11", conteudo="Conteúdo")
        Frequencia.objects.create(aula=self.aula, aluno=self.aluno, status=Frequencia.Status.PRESENTE)

    def test_fechamento_turma_periodo_get(self):
        resp = self.client.get(reverse("educacao:fechamento_turma_periodo", args=[self.turma.pk]), {"periodo": self.periodo.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Fechamento do Período")

    def test_fechamento_turma_periodo_post_cria_fechamento(self):
        resp = self.client.post(
            reverse("educacao:fechamento_turma_periodo", args=[self.turma.pk]),
            {
                "periodo": self.periodo.pk,
                "media_corte": "6.00",
                "frequencia_corte": "75.00",
                "observacao": "Fechamento teste",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        fechamento = FechamentoPeriodoTurma.objects.get(turma=self.turma, periodo=self.periodo)
        self.assertEqual(fechamento.total_alunos, 1)
        self.assertEqual(fechamento.aprovados, 1)

    def test_historico_aluno_get(self):
        resp = self.client.get(reverse("educacao:historico_aluno", args=[self.aluno.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Histórico Escolar")

    def test_historico_aluno_export_csv(self):
        resp = self.client.get(reverse("educacao:historico_aluno", args=[self.aluno.pk]), {"export": "csv"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])

    def test_portal_professor_get(self):
        resp = self.client.get(reverse("educacao:portal_professor"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Portal do Professor")

    def test_portal_aluno_get(self):
        resp = self.client.get(reverse("educacao:portal_aluno", args=[self.aluno.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("educacao:aluno_meus_dados", args=[self.aluno.pk]))
        resp_follow = self.client.get(reverse("educacao:portal_aluno", args=[self.aluno.pk]), follow=True)
        self.assertEqual(resp_follow.status_code, 200)
        self.assertContains(resp_follow, "Meus dados acadêmicos detalhados")

    def _create_aluno_profile_user(self, username: str = "aluno.santa2026"):
        User = get_user_model()
        aluno_user = User.objects.create_user(username=username, password="123456")
        profile, _ = Profile.objects.get_or_create(user=aluno_user, defaults={"ativo": True})
        profile.role = Profile.Role.ALUNO
        profile.aluno = self.aluno
        profile.municipio = self.turma.unidade.secretaria.municipio
        profile.must_change_password = False
        if not profile.codigo_acesso:
            profile.codigo_acesso = username
        profile.save()
        return aluno_user, profile

    def _create_professor_profile_user(self, username: str = "prof.area"):
        User = get_user_model()
        prof_user = User.objects.create_user(username=username, password="123456")
        profile, _ = Profile.objects.get_or_create(user=prof_user, defaults={"ativo": True})
        profile.role = Profile.Role.EDU_PROF
        profile.municipio = self.turma.unidade.secretaria.municipio
        profile.secretaria = self.turma.unidade.secretaria
        profile.unidade = self.turma.unidade
        profile.must_change_password = False
        profile.codigo_acesso = username
        profile.save()
        return prof_user, profile

    def _create_coordenador_profile_user(self, username: str = "coord.area"):
        User = get_user_model()
        coord_user = User.objects.create_user(username=username, password="123456")
        profile, _ = Profile.objects.get_or_create(user=coord_user, defaults={"ativo": True})
        profile.role = Profile.Role.EDU_COORD
        profile.municipio = self.turma.unidade.secretaria.municipio
        profile.secretaria = self.turma.unidade.secretaria
        profile.unidade = self.turma.unidade
        profile.must_change_password = False
        profile.codigo_acesso = username
        profile.save()
        return coord_user, profile

    def test_aluno_role_can_access_meus_dados(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.santa2026")

        self.client.force_login(aluno_user)
        resp = self.client.get(reverse("educacao:aluno_meus_dados", args=[profile.codigo_acesso]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.aluno.nome)
        self.assertContains(resp, self.turma.nome)

    def test_aluno_role_can_access_area_routes(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.rotas")
        self.client.force_login(aluno_user)
        routes = [
            "aluno_documentos_processos",
            "aluno_ensino",
            "aluno_ensino_dados",
            "aluno_ensino_renovacao",
            "aluno_ensino_justificativa",
            "aluno_ensino_boletins",
            "aluno_ensino_avaliacoes",
            "aluno_ensino_disciplinas",
            "aluno_ensino_horarios",
            "aluno_ensino_mensagens",
            "aluno_ensino_biblioteca",
            "aluno_ensino_apoio",
            "aluno_ensino_seletivos",
            "aluno_pesquisa",
            "aluno_central_servicos",
            "aluno_atividades",
            "aluno_saude",
            "aluno_comunicacao",
        ]
        for route_name in routes:
            with self.subTest(route=route_name):
                resp = self.client.get(reverse(f"educacao:{route_name}", args=[profile.codigo_acesso]), follow=True)
                self.assertEqual(resp.status_code, 200)

    def test_professor_area_routes_get(self):
        prof_user, profile = self._create_professor_profile_user("prof.rotas")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)

        self.client.force_login(prof_user)
        routes = [
            "professor_inicio",
            "professor_diarios",
            "professor_aulas",
            "professor_frequencias",
            "professor_notas",
            "professor_agenda_avaliacoes",
            "professor_horarios",
            "professor_planos_ensino",
            "professor_materiais",
            "professor_justificativas",
            "professor_fechamento",
        ]
        for route_name in routes:
            with self.subTest(route=route_name):
                resp = self.client.get(reverse(f"educacao:{route_name}", args=[profile.codigo_acesso]))
                self.assertEqual(resp.status_code, 200)

    def test_professor_plano_ensino_submit_and_cancel(self):
        prof_user, profile = self._create_professor_profile_user("prof.plano")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)

        self.client.force_login(prof_user)
        url = reverse("educacao:professor_plano_ensino_editar", args=[profile.codigo_acesso, self.diario.pk])

        resp_submit = self.client.post(
            url,
            data={
                "titulo": "Plano anual 5A",
                "ementa": "Conteúdo anual",
                "objetivos": "Objetivos pedagógicos",
                "metodologia": "Metodologias ativas",
                "criterios_avaliacao": "Provas e atividades",
                "cronograma": "Março a dezembro",
                "referencias": "BNCC e diretrizes municipais",
                "action": "submit",
            },
            follow=True,
        )
        self.assertEqual(resp_submit.status_code, 200)
        plano = PlanoEnsinoProfessor.objects.get(diario=self.diario, professor=prof_user)
        self.assertEqual(plano.status, PlanoEnsinoProfessor.Status.SUBMETIDO)
        self.assertIsNotNone(plano.submetido_em)

        resp_cancel = self.client.post(
            url,
            data={
                "titulo": plano.titulo,
                "ementa": plano.ementa,
                "objetivos": plano.objetivos,
                "metodologia": plano.metodologia,
                "criterios_avaliacao": plano.criterios_avaliacao,
                "cronograma": plano.cronograma,
                "referencias": plano.referencias,
                "action": "cancel_submit",
            },
            follow=True,
        )
        self.assertEqual(resp_cancel.status_code, 200)
        plano.refresh_from_db()
        self.assertEqual(plano.status, PlanoEnsinoProfessor.Status.RASCUNHO)
        self.assertIsNone(plano.submetido_em)

    def test_professor_plano_ensino_nao_submete_com_pendencias(self):
        prof_user, profile = self._create_professor_profile_user("prof.plano.pendente")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)

        self.client.force_login(prof_user)
        url = reverse("educacao:professor_plano_ensino_editar", args=[profile.codigo_acesso, self.diario.pk])
        resp_submit = self.client.post(
            url,
            data={
                "titulo": "Plano anual 5A",
                "ementa": "",
                "objetivos": "",
                "metodologia": "",
                "criterios_avaliacao": "",
                "cronograma": "",
                "referencias": "",
                "action": "submit",
            },
            follow=True,
        )
        self.assertEqual(resp_submit.status_code, 200)
        self.assertContains(resp_submit, "Não foi possível submeter.")
        plano = PlanoEnsinoProfessor.objects.get(diario=self.diario, professor=prof_user)
        self.assertEqual(plano.status, PlanoEnsinoProfessor.Status.RASCUNHO)
        self.assertIsNone(plano.submetido_em)

    def test_professor_nao_edita_plano_aprovado(self):
        prof_user, profile = self._create_professor_profile_user("prof.plano.aprovado")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)
        plano = PlanoEnsinoProfessor.objects.create(
            diario=self.diario,
            professor=prof_user,
            ano_letivo=self.diario.ano_letivo,
            titulo="Plano já aprovado",
            ementa="Texto base",
            objetivos="Objetivos",
            metodologia="Metodologia",
            criterios_avaliacao="Critérios",
            cronograma="Cronograma",
            referencias="Referências",
            status=PlanoEnsinoProfessor.Status.APROVADO,
            submetido_em=timezone.now(),
            aprovado_em=timezone.now(),
        )

        self.client.force_login(prof_user)
        url = reverse("educacao:professor_plano_ensino_editar", args=[profile.codigo_acesso, self.diario.pk])
        resp = self.client.post(
            url,
            data={
                "titulo": "Alteração indevida",
                "ementa": plano.ementa,
                "objetivos": plano.objetivos,
                "metodologia": plano.metodologia,
                "criterios_avaliacao": plano.criterios_avaliacao,
                "cronograma": plano.cronograma,
                "referencias": plano.referencias,
                "action": "save",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        plano.refresh_from_db()
        self.assertEqual(plano.titulo, "Plano já aprovado")
        self.assertContains(resp, "não pode ser editado no momento")

    def test_coordenacao_aprova_e_homologa_plano_regular(self):
        prof_user, _profile_prof = self._create_professor_profile_user("prof.plano.coord")
        coord_user, _profile_coord = self._create_coordenador_profile_user("coord.plano.regular")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)

        plano = PlanoEnsinoProfessor.objects.create(
            diario=self.diario,
            professor=prof_user,
            ano_letivo=self.diario.ano_letivo,
            titulo="Plano para aprovação",
            ementa="Ementa",
            objetivos="Objetivos",
            metodologia="Metodologia",
            criterios_avaliacao="Critérios",
            cronograma="Cronograma",
            referencias="Referências",
            status=PlanoEnsinoProfessor.Status.SUBMETIDO,
            submetido_em=timezone.now(),
        )

        self.client.force_login(coord_user)
        url = reverse("educacao:plano_ensino_fluxo_regular_detail", args=[plano.pk])

        resp_aprovar = self.client.post(url, data={"action": "aprovar"}, follow=True)
        self.assertEqual(resp_aprovar.status_code, 200)
        plano.refresh_from_db()
        self.assertEqual(plano.status, PlanoEnsinoProfessor.Status.APROVADO)
        self.assertEqual(plano.aprovado_por_id, coord_user.id)

        resp_homologar = self.client.post(url, data={"action": "homologar"}, follow=True)
        self.assertEqual(resp_homologar.status_code, 200)
        plano.refresh_from_db()
        self.assertEqual(plano.status, PlanoEnsinoProfessor.Status.HOMOLOGADO)
        self.assertEqual(plano.homologado_por_id, coord_user.id)

    def test_coordenacao_devolve_plano_informatica(self):
        prof_user, _profile_prof = self._create_professor_profile_user("prof.plano.info")
        coord_user, _profile_coord = self._create_coordenador_profile_user("coord.plano.info")

        municipio = self.turma.unidade.secretaria.municipio
        laboratorio = InformaticaLaboratorio.objects.create(
            nome="Lab Teste",
            unidade=self.turma.unidade,
            quantidade_computadores=20,
            capacidade_operacional=12,
        )
        curso = InformaticaCurso.objects.create(
            municipio=municipio,
            nome="Curso Informática Teste",
            descricao="Curso de teste",
            max_alunos_por_turma=12,
        )
        turma_info = InformaticaTurma.objects.create(
            curso=curso,
            laboratorio=laboratorio,
            codigo="INFO-T1",
            nome="Turma Info T1",
            instrutor=prof_user,
            ano_letivo=2026,
            status=InformaticaTurma.Status.ATIVA,
            max_vagas=12,
        )
        plano_info = InformaticaPlanoEnsinoProfessor.objects.create(
            turma=turma_info,
            professor=prof_user,
            ano_letivo=2026,
            titulo="Plano informática",
            ementa="Ementa",
            objetivos="Objetivos",
            metodologia="Metodologia",
            criterios_avaliacao="Critérios",
            cronograma="Cronograma",
            referencias="Referências",
            status=InformaticaPlanoEnsinoProfessor.Status.SUBMETIDO,
            submetido_em=timezone.now(),
        )

        self.client.force_login(coord_user)
        url = reverse("educacao:plano_ensino_fluxo_informatica_detail", args=[plano_info.pk])
        resp = self.client.post(
            url,
            data={
                "action": "devolver",
                "motivo_devolucao": "Ajustar critérios de avaliação para incluir recuperação.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        plano_info.refresh_from_db()
        self.assertEqual(plano_info.status, InformaticaPlanoEnsinoProfessor.Status.DEVOLVIDO)
        self.assertEqual(plano_info.devolvido_por_id, coord_user.id)
        self.assertIn("Ajustar critérios", plano_info.motivo_devolucao)

    def test_professor_material_create(self):
        prof_user, profile = self._create_professor_profile_user("prof.material")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)

        self.client.force_login(prof_user)
        url = reverse("educacao:professor_material_novo", args=[profile.codigo_acesso])
        arquivo = SimpleUploadedFile("plano.txt", b"conteudo teste", content_type="text/plain")
        resp = self.client.post(
            url,
            data={
                "titulo": "Material de apoio",
                "descricao": "Roteiro de aula",
                "diario": str(self.diario.pk),
                "aula": "",
                "arquivo": arquivo,
                "link_externo": "",
                "publico_alunos": "on",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            MaterialAulaProfessor.objects.filter(
                professor=prof_user,
                diario=self.diario,
                titulo="Material de apoio",
            ).exists()
        )

    def test_professor_nao_pode_acessar_area_de_outro_professor(self):
        prof_a, profile_a = self._create_professor_profile_user("prof.area.a")
        _prof_b, profile_b = self._create_professor_profile_user("prof.area.b")
        self.diario.professor = prof_a
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_a)

        self.client.force_login(prof_a)
        resp = self.client.get(reverse("educacao:professor_inicio", args=[profile_b.codigo_acesso]))
        self.assertEqual(resp.status_code, 404)

    def test_professor_pode_abrir_fechamento_da_propria_turma(self):
        prof_user, _profile = self._create_professor_profile_user("prof.fechamento")
        self.diario.professor = prof_user
        self.diario.save(update_fields=["professor"])
        self.turma.professores.add(prof_user)

        self.client.force_login(prof_user)
        resp = self.client.get(
            reverse("educacao:fechamento_turma_periodo", args=[self.turma.pk]),
            {"periodo": self.periodo.pk},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Fechamento do Período")

    def test_aluno_boletim_default_mostra_periodo_referencia_da_matricula(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.boletim.default")
        periodo_2 = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=2,
            inicio="2026-05-01",
            fim="2026-07-31",
            ativo=True,
        )
        avaliacao_2 = Avaliacao.objects.create(
            diario=self.diario,
            periodo=periodo_2,
            titulo="Prova 2",
            peso=Decimal("1.00"),
            nota_maxima=Decimal("10.00"),
            data="2026-06-10",
        )
        Nota.objects.create(avaliacao=avaliacao_2, aluno=self.aluno, valor=Decimal("7.50"))

        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_ensino_boletins", args=[profile.codigo_acesso])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Boletim por Período/Semestre")
        self.assertContains(resp, "2026/1")
        self.assertEqual(resp.context["periodo_referencia"].pk, self.periodo.pk)

    def test_aluno_boletim_permite_consultar_outro_periodo(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.boletim.filtro")
        periodo_2 = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=2,
            inicio="2026-05-01",
            fim="2026-07-31",
            ativo=True,
        )
        avaliacao_2 = Avaliacao.objects.create(
            diario=self.diario,
            periodo=periodo_2,
            titulo="Prova 2",
            peso=Decimal("1.00"),
            nota_maxima=Decimal("10.00"),
            data="2026-06-10",
        )
        Nota.objects.create(avaliacao=avaliacao_2, aluno=self.aluno, valor=Decimal("7.50"))

        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_ensino_boletins", args=[profile.codigo_acesso])
        resp = self.client.get(url, {"periodo": str(periodo_2.pk)})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "2026/2")
        self.assertEqual(resp.context["periodo_referencia"].pk, periodo_2.pk)

    def test_aluno_avaliacoes_filtra_por_periodo(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.avaliacoes.filtro")
        periodo_2 = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=2,
            inicio="2026-05-01",
            fim="2026-07-31",
            ativo=True,
        )
        avaliacao_2 = Avaliacao.objects.create(
            diario=self.diario,
            periodo=periodo_2,
            titulo="Prova 2",
            peso=Decimal("1.00"),
            nota_maxima=Decimal("10.00"),
            data="2026-06-10",
        )
        Nota.objects.create(avaliacao=avaliacao_2, aluno=self.aluno, valor=Decimal("7.50"))

        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_ensino_avaliacoes", args=[profile.codigo_acesso])

        resp_default = self.client.get(url)
        self.assertEqual(resp_default.status_code, 200)
        self.assertContains(resp_default, "Prova 1")
        self.assertNotContains(resp_default, "Prova 2")

        resp_periodo_2 = self.client.get(url, {"periodo": str(periodo_2.pk)})
        self.assertEqual(resp_periodo_2.status_code, 200)
        self.assertContains(resp_periodo_2, "Prova 2")
        self.assertNotContains(resp_periodo_2, "Prova 1")

    def test_aluno_documentos_processos_post_cria_processo(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.docs")
        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_documentos_processos", args=[profile.codigo_acesso])
        resp = self.client.post(
            url,
            {
                "form_kind": "documento",
                "doc-tipo": "DECLARACAO_MATRICULA",
                "doc-descricao": "Documento para bolsa municipal",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            ProcessoAdministrativo.objects.filter(
                criado_por=aluno_user,
                tipo__icontains="DOCUMENTO",
                solicitante_nome=self.aluno.nome,
            ).exists()
        )

    def test_aluno_renovacao_post_cria_pedido_e_processo(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.renovacao")
        hoje = date.today()
        renovacao = RenovacaoMatricula.objects.create(
            descricao="Renovação Rede 2026",
            ano_letivo=2026,
            secretaria=self.turma.unidade.secretaria,
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje + timedelta(days=3),
            criado_por=self.admin,
        )
        oferta = RenovacaoMatriculaOferta.objects.create(
            renovacao=renovacao,
            turma=self.turma,
        )

        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_ensino_renovacao", args=[profile.codigo_acesso])
        resp = self.client.post(
            url,
            {
                "form_kind": "pedido_renovacao",
                "renovacao_id": str(renovacao.pk),
                "oferta_id": str(oferta.pk),
                "prioridade": 1,
                "observacao_aluno": "Solicitação dentro da janela.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        pedido = RenovacaoMatriculaPedido.objects.get(renovacao=renovacao, aluno=self.aluno, oferta=oferta)
        self.assertIsNotNone(pedido.processo_administrativo_id)
        self.assertTrue(
            ProcessoAdministrativo.objects.filter(
                pk=pedido.processo_administrativo_id,
                tipo="RENOVACAO_MATRICULA",
                solicitante_nome=self.aluno.nome,
            ).exists()
        )

    def test_aluno_renovacao_cancelar_pedido_arquiva_processo(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.renovacao.cancel")
        hoje = date.today()
        renovacao = RenovacaoMatricula.objects.create(
            descricao="Renovação Cancelamento 2026",
            ano_letivo=2026,
            secretaria=self.turma.unidade.secretaria,
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje + timedelta(days=3),
            criado_por=self.admin,
        )
        oferta = RenovacaoMatriculaOferta.objects.create(
            renovacao=renovacao,
            turma=self.turma,
        )
        processo = ProcessoAdministrativo.objects.create(
            municipio=self.turma.unidade.secretaria.municipio,
            secretaria=self.turma.unidade.secretaria,
            unidade=self.turma.unidade,
            numero=f"ALUNO-{hoje.strftime('%Y%m%d')}-9001",
            tipo="RENOVACAO_MATRICULA",
            assunto="Teste de cancelamento",
            solicitante_nome=self.aluno.nome,
            descricao="Pedido de teste",
            status=ProcessoAdministrativo.Status.ABERTO,
            criado_por=aluno_user,
        )
        pedido = RenovacaoMatriculaPedido.objects.create(
            renovacao=renovacao,
            aluno=self.aluno,
            oferta=oferta,
            prioridade=1,
            processo_administrativo=processo,
        )

        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_ensino_renovacao", args=[profile.codigo_acesso])
        resp = self.client.post(
            url,
            {
                "form_kind": "cancelar_pedido_renovacao",
                "pedido_id": str(pedido.pk),
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(RenovacaoMatriculaPedido.objects.filter(pk=pedido.pk).exists())
        processo.refresh_from_db()
        self.assertEqual(processo.status, ProcessoAdministrativo.Status.ARQUIVADO)

    def test_aluno_role_can_emitir_carteira_pdf(self):
        aluno_user, _profile = self._create_aluno_profile_user("aluno.carteira")
        self.client.force_login(aluno_user)
        resp = self.client.get(reverse("educacao:carteira_emitir_pdf", args=[self.aluno.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp["Content-Type"])

    def test_aluno_central_servicos_post_cria_chamado(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.chamado")
        self.client.force_login(aluno_user)
        url = reverse("educacao:aluno_central_servicos", args=[profile.codigo_acesso])
        resp = self.client.post(
            url,
            {
                "form_kind": "abrir_chamado",
                "ch-categoria": "ACADEMICO",
                "ch-assunto": "Dúvida sobre avaliação",
                "ch-descricao": "Solicito verificação da nota do último bimestre.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            OuvidoriaCadastro.objects.filter(
                criado_por=aluno_user,
                solicitante_nome=self.aluno.nome,
                assunto__icontains="Dúvida sobre avaliação",
            ).exists()
        )

    def test_aluno_justificativa_falta_post_cria_pedido_vinculado_aula(self):
        aluno_user, profile = self._create_aluno_profile_user("aluno.justificativa")
        self.client.force_login(aluno_user)

        aula_falta = Aula.objects.create(diario=self.diario, data="2026-03-20", conteudo="Aula com ausência")
        Frequencia.objects.update_or_create(
            aula=aula_falta,
            aluno=self.aluno,
            defaults={"status": Frequencia.Status.FALTA},
        )

        resp = self.client.post(
            reverse("educacao:aluno_ensino_justificativa", args=[profile.codigo_acesso]),
            {
                "form_kind": "justificativa",
                "falta-turma": str(self.turma.pk),
                "falta-aula": str(aula_falta.pk),
                "falta-motivo": "Apresentei atestado médico.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        pedido = JustificativaFaltaPedido.objects.filter(aluno=self.aluno, aula=aula_falta).first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.status, JustificativaFaltaPedido.Status.PENDENTE)

    def test_professor_pode_deferir_pedido_e_frequencia_vira_justificada(self):
        aula_falta = Aula.objects.create(diario=self.diario, data="2026-03-21", conteudo="Aula para decisão")
        Frequencia.objects.update_or_create(
            aula=aula_falta,
            aluno=self.aluno,
            defaults={"status": Frequencia.Status.FALTA},
        )
        pedido = JustificativaFaltaPedido.objects.create(
            aula=aula_falta,
            aluno=self.aluno,
            motivo="Atestado anexado.",
            status=JustificativaFaltaPedido.Status.PENDENTE,
        )

        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("educacao:justificativa_falta_detail", args=[pedido.pk]),
            {"decisao": "DEFERIDO", "parecer": "Documento válido. Pedido deferido."},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, JustificativaFaltaPedido.Status.DEFERIDO)
        freq = Frequencia.objects.get(aula=aula_falta, aluno=self.aluno)
        self.assertEqual(freq.status, Frequencia.Status.JUSTIFICADA)

    def test_aluno_nao_pode_acessar_dados_de_outro_aluno(self):
        User = get_user_model()
        outro_aluno = Aluno.objects.create(nome="Outro Aluno")
        Matricula.objects.create(aluno=outro_aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

        aluno_user = User.objects.create_user(username="aluno.own", password="123456")
        profile, _ = Profile.objects.get_or_create(user=aluno_user, defaults={"ativo": True})
        profile.role = Profile.Role.ALUNO
        profile.aluno = self.aluno
        profile.municipio = self.turma.unidade.secretaria.municipio
        profile.must_change_password = False
        profile.codigo_acesso = "aluno.own"
        profile.save()

        outro_user = User.objects.create_user(username="aluno.other", password="123456")
        profile_outro, _ = Profile.objects.get_or_create(user=outro_user, defaults={"ativo": True})
        profile_outro.role = Profile.Role.ALUNO
        profile_outro.aluno = outro_aluno
        profile_outro.municipio = self.turma.unidade.secretaria.municipio
        profile_outro.must_change_password = False
        profile_outro.codigo_acesso = "aluno.other"
        profile_outro.save()

        self.client.force_login(aluno_user)
        resp_meus_dados = self.client.get(reverse("educacao:aluno_meus_dados", args=[profile_outro.codigo_acesso]))
        self.assertEqual(resp_meus_dados.status_code, 404)

        resp_historico = self.client.get(reverse("educacao:historico_aluno", args=[outro_aluno.pk]))
        self.assertEqual(resp_historico.status_code, 404)

    def test_portal_aluno_edital_detail_get(self):
        beneficio = BeneficioTipo.objects.create(
            municipio=self.turma.unidade.secretaria.municipio,
            secretaria=self.turma.unidade.secretaria,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Kit Portal Aluno",
            categoria=BeneficioTipo.Categoria.KIT_ESCOLAR,
            periodicidade=BeneficioTipo.Periodicidade.ANUAL,
            status=BeneficioTipo.Status.ATIVO,
            criado_por=self.admin,
        )
        edital = BeneficioEdital.objects.create(
            municipio=self.turma.unidade.secretaria.municipio,
            secretaria=self.turma.unidade.secretaria,
            area=BeneficioTipo.Area.EDUCACAO,
            titulo="Edital Portal Aluno",
            numero_ano="77/2026-PORTAL",
            beneficio=beneficio,
            publico_alvo=BeneficioTipo.PublicoAlvo.TODOS,
            status=BeneficioEdital.Status.EM_ANALISE,
        )
        inscricao = BeneficioEditalInscricao.objects.create(
            edital=edital,
            aluno=self.aluno,
            escola=self.turma.unidade,
            turma=self.turma,
            status=BeneficioEditalInscricao.Status.EM_ANALISE,
            pontuacao=Decimal("12"),
            criado_por=self.admin,
            atualizado_por=self.admin,
            dados_json={"avaliacao": {"pendencias_documentos": ["Documento X"]}},
        )
        resp = self.client.get(reverse("educacao:portal_aluno_edital_detail", args=[self.aluno.pk, inscricao.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Acompanhamento da Inscrição")
        self.assertContains(resp, "Etapas do edital")


class ComponenteCurricularCrudTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admincomp", password="123456", email="admin@comp.local")
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)
        self.componente = ComponenteCurricular.objects.create(nome="Matemática", sigla="MAT", ativo=True)

    def test_componente_list_get(self):
        resp = self.client.get(reverse("educacao:componente_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Componentes Curriculares")

    def test_componente_create(self):
        resp = self.client.post(
            reverse("educacao:componente_create"),
            {"nome": "Língua Portuguesa", "sigla": "LP", "ativo": "on"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ComponenteCurricular.objects.filter(nome="Língua Portuguesa").exists())


class CalendarioEducacionalTestCase(TestCase):
    def setUp(self):
        def ensure_profile(user):
            profile = getattr(user, "profile", None)
            if profile is None:
                profile = Profile.objects.create(user=user)
            return profile

        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="admcal",
            password="123456",
            email="admcal@local",
        )
        admin_profile = ensure_profile(self.admin)
        if admin_profile:
            admin_profile.must_change_password = False
            admin_profile.save(update_fields=["must_change_password"])

        self.prof = User.objects.create_user(username="profcal", password="123456")
        prof_profile = ensure_profile(self.prof)
        if prof_profile:
            prof_profile.role = "PROFESSOR"
            prof_profile.must_change_password = False
            prof_profile.save(update_fields=["role", "must_change_password"])

        self.aluno_user = User.objects.create_user(username="alunocal", password="123456")

        self.municipio = Municipio.objects.create(nome="Cidade Calendário", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Calendário",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="9A",
            ano_letivo=date.today().year,
            turno=Turma.Turno.MANHA,
        )
        self.turma.professores.add(self.prof)

        self.aluno = Aluno.objects.create(nome="Aluno Calendário")
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

        aluno_profile = ensure_profile(self.aluno_user)
        if aluno_profile:
            aluno_profile.role = "ALUNO"
            aluno_profile.aluno = self.aluno
            aluno_profile.must_change_password = False
            aluno_profile.save(update_fields=["role", "aluno", "must_change_password"])

        self.evento = CalendarioEducacionalEvento.objects.create(
            ano_letivo=date.today().year,
            secretaria=self.secretaria,
            unidade=self.unidade,
            titulo="Início do Bimestre",
            tipo=CalendarioEducacionalEvento.Tipo.BIMESTRE_INICIO,
            data_inicio=date.today() + timedelta(days=5),
            data_fim=date.today() + timedelta(days=5),
            dia_letivo=True,
            ativo=True,
            criado_por=self.admin,
            atualizado_por=self.admin,
        )

    def test_calendario_index_loads(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("educacao:calendario_index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Calendário Educacional")

    def test_secretaria_manage_can_create_event(self):
        self.client.force_login(self.admin)
        payload = {
            "ano_letivo": date.today().year,
            "secretaria": self.secretaria.pk,
            "unidade": self.unidade.pk,
            "titulo": "Feriado Municipal",
            "descricao": "Data oficial do município",
            "tipo": CalendarioEducacionalEvento.Tipo.FERIADO,
            "data_inicio": (date.today() + timedelta(days=10)).isoformat(),
            "data_fim": (date.today() + timedelta(days=10)).isoformat(),
            "dia_letivo": "",
            "ativo": "on",
        }
        resp = self.client.post(reverse("educacao:calendario_evento_create"), payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CalendarioEducacionalEvento.objects.filter(titulo="Feriado Municipal").exists())

    def test_professor_dashboard_displays_calendar_event(self):
        self.client.force_login(self.prof)
        resp = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.evento.titulo)

    def test_aluno_dashboard_displays_calendar_event(self):
        self.client.force_login(self.aluno_user)
        resp = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.evento.titulo)

    def test_calendario_export_pdf_mes(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("educacao:calendario_index"),
            {"ano": date.today().year, "mes": date.today().month, "export": "pdf_mes"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp["Content-Type"])

    def test_calendario_export_pdf_ano(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("educacao:calendario_index"),
            {"ano": date.today().year, "export": "pdf_ano"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp["Content-Type"])

    def test_professor_pode_emitir_declaracao_vinculo_do_aluno_da_turma(self):
        self.client.force_login(self.prof)
        resp = self.client.get(reverse("educacao:declaracao_vinculo_pdf", args=[self.aluno.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp["Content-Type"])
        doc = AlunoDocumento.objects.filter(aluno=self.aluno, tipo=AlunoDocumento.Tipo.DECLARACAO).order_by("-id").first()
        self.assertIsNotNone(doc)
        self.assertTrue(bool(getattr(doc, "arquivo", None)))


class AssistenciaEscolarTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="adminassist", password="123456", email="admin@assist.local")
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        municipio = Municipio.objects.create(nome="Cidade Assistência", uf="MA")
        secretaria = Secretaria.objects.create(municipio=municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(secretaria=secretaria, nome="Escola Assistência", tipo=Unidade.Tipo.EDUCACAO, codigo_inep="21000111")

    def test_assistencia_index_get(self):
        resp = self.client.get(reverse("educacao:assistencia_index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Assistência Escolar")

    def test_cardapio_create_flow(self):
        resp = self.client.post(
            reverse("educacao:assist_cardapio_create"),
            {
                "unidade": self.unidade.pk,
                "data": "2026-03-01",
                "turno": "MANHA",
                "descricao": "Arroz, feijão e frango",
                "observacao": "",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CardapioEscolar.objects.filter(unidade=self.unidade).exists())

    def test_refeicao_and_transporte_basic_models(self):
        refeicao = RegistroRefeicaoEscolar.objects.create(unidade=self.unidade, data="2026-03-02", turno="MANHA", total_servidas=120)
        rota = RotaTransporteEscolar.objects.create(unidade=self.unidade, nome="Rota Centro", turno="MANHA", ativo=True)
        registro = RegistroTransporteEscolar.objects.create(data="2026-03-02", rota=rota, total_previsto=40, total_transportados=36)
        self.assertEqual(refeicao.total_servidas, 120)
        self.assertEqual(registro.total_transportados, 36)

    def test_indicadores_gerenciais_get(self):
        resp = self.client.get(reverse("educacao:indicadores_gerenciais"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Indicadores Gerenciais")


class EducacaoCatalogoDocumentacaoTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admincatalogo", password="123456", email="admin@catalogo.local")
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Catálogo", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Catálogo",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="1A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Documentação")
        self.matricula = Matricula.objects.create(
            aluno=self.aluno,
            turma=self.turma,
            situacao=Matricula.Situacao.ATIVA,
        )

    def test_curso_and_coordenacao_crud(self):
        resp_create_curso = self.client.post(
            reverse("educacao:curso_create"),
            {
                "nome": "Técnico em Informática",
                "codigo": "TI-01",
                "modalidade_oferta": Curso.ModalidadeOferta.TECNICA,
                "eixo_tecnologico": "Informação e Comunicação",
                "carga_horaria": 1200,
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp_create_curso.status_code, 200)
        curso = Curso.objects.get(nome="Técnico em Informática")

        resp_create_coord = self.client.post(
            reverse("educacao:coordenacao_create"),
            {
                "coordenador": self.admin.pk,
                "unidade": self.unidade.pk,
                "modalidade": Turma.Modalidade.EJA,
                "etapa": Turma.Etapa.EJA_FUNDAMENTAL,
                "inicio": "2026-02-01",
                "fim": "",
                "observacao": "Coordenação EJA",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp_create_coord.status_code, 200)
        self.assertTrue(CoordenacaoEnsino.objects.filter(unidade=self.unidade, modalidade=Turma.Modalidade.EJA).exists())

        self.turma.curso = curso
        self.turma.modalidade = Turma.Modalidade.EDUCACAO_PROFISSIONAL
        self.turma.etapa = Turma.Etapa.TECNICO_INTEGRADO
        self.turma.save(update_fields=["curso", "modalidade", "etapa"])
        self.assertEqual(self.turma.curso_id, curso.id)

    def test_curso_grade_curricular_no_update(self):
        curso = Curso.objects.create(
            nome="Robótica",
            codigo="ROB-01",
            modalidade_oferta=Curso.ModalidadeOferta.FIC,
            carga_horaria=120,
            ativo=True,
        )
        resp = self.client.post(
            reverse("educacao:curso_update", args=[curso.pk]),
            {
                "_action": "add_disciplina",
                "grade-nome": "Programação de Robôs",
                "grade-tipo_aula": "LABORATORIO",
                "grade-carga_horaria": 40,
                "grade-ordem": 1,
                "grade-obrigatoria": "on",
                "grade-ementa": "Lógica e automação.",
                "grade-ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CursoDisciplina.objects.filter(curso=curso, nome="Programação de Robôs").exists()
        )

    def test_aluno_matricula_em_curso_complementar(self):
        curso = Curso.objects.create(
            nome="Ballet",
            codigo="BAL-01",
            modalidade_oferta=Curso.ModalidadeOferta.LIVRE,
            carga_horaria=80,
            ativo=True,
        )
        turma_curso = Turma.objects.create(
            unidade=self.unidade,
            nome="Ballet T1",
            ano_letivo=2026,
            turno=Turma.Turno.TARDE,
            curso=curso,
            modalidade=Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
            etapa=Turma.Etapa.FIC,
        )

        resp = self.client.post(
            reverse("educacao:aluno_detail", args=[self.aluno.pk]),
            {
                "_action": "add_matricula_curso",
                "curso": curso.pk,
                "turma": turma_curso.pk,
                "data_matricula": "2026-03-01",
                "situacao": "MATRICULADO",
                "data_conclusao": "",
                "nota_final": "",
                "frequencia_percentual": "",
                "observacao": "Curso complementar artístico",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MatriculaCurso.objects.filter(aluno=self.aluno, curso=curso).exists())

    def test_aluno_documento_e_certificado_via_detail(self):
        arquivo_doc = SimpleUploadedFile("rg.pdf", b"%PDF-1.4 doc", content_type="application/pdf")
        resp_doc = self.client.post(
            reverse("educacao:aluno_detail", args=[self.aluno.pk]),
            {
                "_action": "add_documento",
                "tipo": "RG",
                "titulo": "RG do aluno",
                "numero_documento": "1234567",
                "data_emissao": "2020-01-01",
                "validade": "",
                "observacao": "Documento civil",
                "ativo": "on",
                "arquivo": arquivo_doc,
            },
            follow=True,
        )
        self.assertEqual(resp_doc.status_code, 200)
        self.assertTrue(AlunoDocumento.objects.filter(aluno=self.aluno, titulo="RG do aluno").exists())

        arquivo_cert = SimpleUploadedFile("certificado.pdf", b"%PDF-1.4 cert", content_type="application/pdf")
        resp_cert = self.client.post(
            reverse("educacao:aluno_detail", args=[self.aluno.pk]),
            {
                "_action": "add_certificado",
                "tipo": "CERTIFICADO_CONCLUSAO",
                "titulo": "Certificado de conclusão",
                "matricula": self.matricula.pk,
                "curso": "",
                "data_emissao": "2026-12-15",
                "carga_horaria": 800,
                "resultado_final": "Aprovado",
                "observacao": "Emitido para arquivo escolar",
                "ativo": "on",
                "arquivo_pdf": arquivo_cert,
            },
            follow=True,
        )
        self.assertEqual(resp_cert.status_code, 200)
        cert = AlunoCertificado.objects.get(aluno=self.aluno, titulo="Certificado de conclusão")
        self.assertTrue(cert.codigo_verificacao)

    def test_declaracao_vinculo_pdf(self):
        resp = self.client.get(reverse("educacao:declaracao_vinculo_pdf", args=[self.aluno.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp["Content-Type"])
        self.assertIn("declaracao_vinculo", resp["Content-Disposition"])
        self.assertTrue(
            AlunoDocumento.objects.filter(
                aluno=self.aluno,
                tipo=AlunoDocumento.Tipo.DECLARACAO,
            ).exists()
        )

    def test_carteira_emitir_pdf_salva_documento(self):
        resp = self.client.get(reverse("educacao:carteira_emitir_pdf", args=[self.aluno.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp["Content-Type"])
        self.assertTrue(
            AlunoDocumento.objects.filter(
                aluno=self.aluno,
                tipo=AlunoDocumento.Tipo.CERTIFICADO,
                titulo__icontains="Carteira estudantil",
            ).exists()
        )


class AulaBNCCIntegracaoTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="adminbncc", password="123456", email="admin@bncc.local")
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])

        self.municipio = Municipio.objects.create(nome="Cidade BNCC", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Secretaria Educação")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola BNCC", tipo=Unidade.Tipo.EDUCACAO)
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="2A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
        )
        self.diario = DiarioTurma.objects.create(turma=self.turma, professor=self.admin, ano_letivo=2026)
        self.periodo = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=1,
            inicio="2026-02-01",
            fim="2026-04-30",
            ativo=True,
        )
        self.componente = ComponenteCurricular.objects.create(
            nome="Língua Portuguesa",
            sigla="LP",
            modalidade_bncc=BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL,
            etapa_bncc=BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            area_codigo_bncc="LP",
            ativo=True,
        )
        self.codigo_lp = BNCCCodigo.objects.create(
            codigo="EF01LP01",
            descricao="Habilidade teste LP",
            modalidade=BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL,
            etapa=BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            area_codigo="LP",
            ano_inicial=1,
            ano_final=1,
            ativo=True,
        )
        self.codigo_ma = BNCCCodigo.objects.create(
            codigo="EF01MA01",
            descricao="Habilidade teste MA",
            modalidade=BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL,
            etapa=BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            area_codigo="MA",
            ano_inicial=1,
            ano_final=1,
            ativo=True,
        )

    def test_aula_form_filtra_bncc_por_componente_e_etapa(self):
        form = AulaForm(
            data={
                "data": "2026-03-10",
                "periodo": self.periodo.pk,
                "componente": self.componente.pk,
                "bncc_codigos": [self.codigo_lp.pk],
                "conteudo": "Leitura e interpretação",
                "observacoes": "",
            },
            diario=self.diario,
        )
        self.assertTrue(form.is_valid(), form.errors)
        qs_codes = form.fields["bncc_codigos"].queryset
        self.assertTrue(qs_codes.filter(codigo="EF01LP01").exists())
        self.assertFalse(qs_codes.filter(codigo="EF01MA01").exists())

    def test_aula_form_bloqueia_data_nao_letiva(self):
        CalendarioEducacionalEvento.objects.create(
            ano_letivo=2026,
            secretaria=self.secretaria,
            unidade=self.unidade,
            titulo="Feriado Municipal",
            tipo=CalendarioEducacionalEvento.Tipo.FERIADO,
            data_inicio="2026-03-15",
            data_fim="2026-03-15",
            dia_letivo=False,
            ativo=True,
            criado_por=self.admin,
            atualizado_por=self.admin,
        )
        form = AulaForm(
            data={
                "data": "2026-03-15",
                "periodo": self.periodo.pk,
                "componente": self.componente.pk,
                "bncc_codigos": [self.codigo_lp.pk],
                "conteudo": "Aula em feriado",
                "observacoes": "",
            },
            diario=self.diario,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("não letiva", " ".join(form.errors.get("data", [])))


class EducacaoSuggestApiTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_api_edu",
            password="123456",
            email="admin_api_edu@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade API Edu", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED API")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola API",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(unidade=self.unidade, nome="Turma API 1", ano_letivo=2026)

        for idx in range(12):
            aluno = Aluno.objects.create(nome=f"Aluno API {idx:02d}", cpf=f"000000000{idx:02d}")
            Matricula.objects.create(aluno=aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

        for idx in range(4):
            Turma.objects.create(unidade=self.unidade, nome=f"Turma API Extra {idx}", ano_letivo=2026)

    def test_api_alunos_suggest_returns_meta_with_pagination(self):
        response = self.client.get(
            reverse("educacao:api_alunos_suggest"),
            {"q": "Aluno API", "page": 2, "limit": 5},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["page"], 2)
        self.assertEqual(payload["meta"]["limit"], 5)
        self.assertGreaterEqual(payload["meta"]["total"], 12)
        self.assertEqual(len(payload["results"]), 5)

    def test_api_turmas_suggest_returns_meta_and_label(self):
        response = self.client.get(
            reverse("educacao:api_turmas_suggest"),
            {"q": "Turma API", "limit": 3},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["limit"], 3)
        self.assertTrue(payload["results"])
        self.assertIn("label", payload["results"][0])

    def test_api_alunos_turma_suggest_returns_meta(self):
        response = self.client.get(
            reverse("educacao:api_alunos_turma_suggest", args=[self.turma.pk]),
            {"q": "Aluno API", "page": 1, "limit": 4},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["limit"], 4)
        self.assertEqual(len(payload["results"]), 4)


class BeneficiosEntregasFlowTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_beneficios",
            password="123456",
            email="admin_beneficios@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.municipio = None
            profile.save(update_fields=["must_change_password", "municipio"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Benefícios", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Benefícios")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Benefícios",
            tipo=Unidade.Tipo.EDUCACAO,
            ativo=True,
        )
        self.turma = Turma.objects.create(unidade=self.unidade, nome="Turma 5B", ano_letivo=2026)
        self.aluno = Aluno.objects.create(nome="Aluno Benefício")
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

        self.item_estoque = AlmoxarifadoCadastro.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            codigo="KIT-CAD-001",
            nome="Caderno 96 folhas",
            saldo_atual=Decimal("10"),
            estoque_minimo=Decimal("1"),
            valor_medio=Decimal("5.5"),
            status=AlmoxarifadoCadastro.Status.ATIVO,
            criado_por=self.admin,
        )
        self.beneficio = BeneficioTipo.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Kit Escolar 2026",
            categoria=BeneficioTipo.Categoria.KIT_ESCOLAR,
            periodicidade=BeneficioTipo.Periodicidade.ANUAL,
            status=BeneficioTipo.Status.ATIVO,
            criado_por=self.admin,
        )
        self.comp = BeneficioTipoItem.objects.create(
            beneficio=self.beneficio,
            item_estoque=self.item_estoque,
            quantidade=Decimal("1"),
            unidade="UN",
            ordem=1,
        )

    def _nova_entrega(self):
        entrega = BeneficioEntrega.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            area=BeneficioTipo.Area.EDUCACAO,
            aluno=self.aluno,
            beneficio=self.beneficio,
            status=BeneficioEntrega.Status.PENDENTE,
            responsavel_entrega=self.admin,
        )
        BeneficioEntregaItem.objects.create(
            entrega=entrega,
            composicao_item=self.comp,
            item_estoque=self.item_estoque,
            item_nome=self.item_estoque.nome,
            quantidade_planejada=Decimal("1"),
            quantidade_entregue=Decimal("1"),
            unidade="UN",
        )
        return entrega

    def test_confirmar_entrega_baixa_estoque(self):
        entrega = self._nova_entrega()
        resp = self.client.post(
            reverse("educacao:beneficio_entrega_confirmar", args=[entrega.pk]) + f"?municipio={self.municipio.pk}",
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        entrega.refresh_from_db()
        self.item_estoque.refresh_from_db()
        self.assertEqual(entrega.status, BeneficioEntrega.Status.ENTREGUE)
        self.assertEqual(self.item_estoque.saldo_atual, Decimal("9"))

    def test_estorno_de_entrega_retorna_estoque(self):
        entrega = self._nova_entrega()
        self.client.post(
            reverse("educacao:beneficio_entrega_confirmar", args=[entrega.pk]) + f"?municipio={self.municipio.pk}",
            follow=True,
        )
        resp = self.client.post(
            reverse("educacao:beneficio_entrega_estornar", args=[entrega.pk]) + f"?municipio={self.municipio.pk}",
            {"motivo": "Entrega em duplicidade"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        entrega.refresh_from_db()
        self.item_estoque.refresh_from_db()
        self.assertEqual(entrega.status, BeneficioEntrega.Status.ESTORNADO)
        self.assertEqual(self.item_estoque.saldo_atual, Decimal("10"))

    def test_bloqueia_duplicidade_no_mesmo_periodo(self):
        entrega1 = self._nova_entrega()
        self.client.post(
            reverse("educacao:beneficio_entrega_confirmar", args=[entrega1.pk]) + f"?municipio={self.municipio.pk}",
            follow=True,
        )
        entrega2 = self._nova_entrega()
        self.client.post(
            reverse("educacao:beneficio_entrega_confirmar", args=[entrega2.pk]) + f"?municipio={self.municipio.pk}",
            follow=True,
        )
        entrega2.refresh_from_db()
        self.assertEqual(entrega2.status, BeneficioEntrega.Status.PENDENTE)


class BeneficiosEditalInscricaoAutomaticaTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_beneficios_inscricao",
            password="123456",
            email="admin_beneficios_inscricao@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Edital Benefício", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Integrada",
            tipo=Unidade.Tipo.EDUCACAO,
            ativo=True,
        )
        self.turma = Turma.objects.create(unidade=self.unidade, nome="Turma 8A", ano_letivo=2026)
        self.aluno = Aluno.objects.create(nome="Aluno Inscrição", ativo=True)
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

        self.beneficio = BeneficioTipo.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Cesta Edital 2026",
            categoria=BeneficioTipo.Categoria.CESTA_BASICA,
            periodicidade=BeneficioTipo.Periodicidade.MENSAL,
            status=BeneficioTipo.Status.ATIVO,
            criado_por=self.admin,
        )
        self.edital = BeneficioEdital.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            area=BeneficioTipo.Area.EDUCACAO,
            titulo="Edital Benefício Integrado",
            numero_ano="01/2026-TEST",
            beneficio=self.beneficio,
            publico_alvo=BeneficioTipo.PublicoAlvo.TODOS,
            status=BeneficioEdital.Status.PUBLICADO,
        )

    def test_calcula_pontuacao_automaticamente_no_envio(self):
        c1 = BeneficioEditalCriterio.objects.create(
            edital=self.edital,
            nome="Recebe Bolsa Família",
            tipo=BeneficioEditalCriterio.Tipo.PONTUACAO,
            fonte_dado="declaracao",
            peso=10,
            exige_comprovacao=False,
            ordem=1,
            ativo=True,
        )
        BeneficioEditalCriterio.objects.create(
            edital=self.edital,
            nome="Aluno ativo no cadastro",
            tipo=BeneficioEditalCriterio.Tipo.ELIMINATORIO,
            fonte_dado="cadastro",
            regra="aluno.ativo == true",
            exige_comprovacao=False,
            ordem=2,
            ativo=True,
        )
        req = BeneficioEditalDocumento.objects.create(
            edital=self.edital,
            nome="Declaração obrigatória",
            obrigatorio=True,
            formatos_aceitos="pdf,jpg,png",
            ordem=1,
        )

        upload = SimpleUploadedFile("declaracao.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        resp = self.client.post(
            reverse("educacao:beneficio_edital_inscricao_add", args=[self.edital.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "edital": str(self.edital.pk),
                "aluno": str(self.aluno.pk),
                "escola": str(self.unidade.pk),
                "turma": str(self.turma.pk),
                "criterio_%s_marcado" % c1.pk: "on",
                "documento_%s_arquivo" % req.pk: upload,
                "usar_documentos_cadastro": "on",
                "justificativa": "",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        inscricao = BeneficioEditalInscricao.objects.get(edital=self.edital, aluno=self.aluno)
        self.assertEqual(inscricao.pontuacao, Decimal("10"))
        self.assertEqual(inscricao.status, BeneficioEditalInscricao.Status.APTO)
        self.assertEqual(inscricao.documentos.count(), 1)

    def test_reaproveita_documentacao_do_cadastro_do_aluno(self):
        criterio = BeneficioEditalCriterio.objects.create(
            edital=self.edital,
            nome="Recebe Bolsa Família",
            tipo=BeneficioEditalCriterio.Tipo.PONTUACAO,
            fonte_dado="declaracao",
            peso=7,
            exige_comprovacao=True,
            ordem=1,
            ativo=True,
        )
        doc_aluno = AlunoDocumento.objects.create(
            aluno=self.aluno,
            tipo=AlunoDocumento.Tipo.DECLARACAO,
            titulo="Declaração de vínculo escolar",
            numero_documento="DECL-123",
            enviado_por=self.admin,
            ativo=True,
        )
        doc_aluno.arquivo.save(
            "declaracao_vinculo.pdf",
            SimpleUploadedFile("declaracao_vinculo.pdf", b"%PDF-1.4 vinculo", content_type="application/pdf"),
            save=True,
        )

        resp = self.client.post(
            reverse("educacao:beneficio_edital_inscricao_add", args=[self.edital.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "edital": str(self.edital.pk),
                "aluno": str(self.aluno.pk),
                "escola": str(self.unidade.pk),
                "turma": str(self.turma.pk),
                "criterio_%s_marcado" % criterio.pk: "on",
                "usar_documentos_cadastro": "on",
                "justificativa": "",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        inscricao = BeneficioEditalInscricao.objects.get(edital=self.edital, aluno=self.aluno)
        self.assertEqual(inscricao.pontuacao, Decimal("7"))
        self.assertEqual(inscricao.status, BeneficioEditalInscricao.Status.APTO)
        self.assertGreaterEqual(inscricao.documentos.count(), 1)

    def test_inscricao_detail_e_reprocessamento(self):
        criterio = BeneficioEditalCriterio.objects.create(
            edital=self.edital,
            nome="Aluno ativo no cadastro",
            tipo=BeneficioEditalCriterio.Tipo.ELIMINATORIO,
            fonte_dado="cadastro",
            regra="aluno.ativo == true",
            ordem=1,
            ativo=True,
        )
        self.client.post(
            reverse("educacao:beneficio_edital_inscricao_add", args=[self.edital.pk]) + f"?municipio={self.municipio.pk}",
            data={
                "edital": str(self.edital.pk),
                "aluno": str(self.aluno.pk),
                "escola": str(self.unidade.pk),
                "turma": str(self.turma.pk),
                "criterio_%s_marcado" % criterio.pk: "on",
                "usar_documentos_cadastro": "on",
                "justificativa": "",
            },
            follow=True,
        )
        inscricao = BeneficioEditalInscricao.objects.get(edital=self.edital, aluno=self.aluno)

        resp_detail = self.client.get(
            reverse("educacao:beneficio_edital_inscricao_detail", args=[self.edital.pk, inscricao.pk]) + f"?municipio={self.municipio.pk}"
        )
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "Avaliação por critério")

        resp_reprocess = self.client.post(
            reverse("educacao:beneficio_edital_inscricao_reprocessar", args=[self.edital.pk, inscricao.pk]) + f"?municipio={self.municipio.pk}",
            follow=True,
        )
        self.assertEqual(resp_reprocess.status_code, 200)
        inscricao.refresh_from_db()
        self.assertEqual(inscricao.status, BeneficioEditalInscricao.Status.ENVIADA)


class TurmaMatrizMotorPrincipalTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Matriz", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Matriz")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Base",
            tipo=Unidade.Tipo.EDUCACAO,
        )

    def test_expected_etapa_from_matriz_by_serie(self):
        matriz_creche = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Maternal I 2026",
            etapa_base=MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL,
            serie_ano=MatrizCurricular.SerieAno.INFANTIL_MATERNAL_I,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        matriz_pre = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Jardim II 2026",
            etapa_base=MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL,
            serie_ano=MatrizCurricular.SerieAno.INFANTIL_JARDIM_II,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        matriz_finais = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz 7º ano 2026",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_7,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )

        self.assertEqual(Turma.expected_etapa_from_matriz(matriz_creche), Turma.Etapa.CRECHE)
        self.assertEqual(Turma.expected_etapa_from_matriz(matriz_pre), Turma.Etapa.PRE_ESCOLA)
        self.assertEqual(Turma.expected_etapa_from_matriz(matriz_finais), Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS)

    def test_turma_form_auto_aligns_etapa_e_serie_from_matriz(self):
        from apps.educacao.forms import TurmaForm

        matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz 4º ano 2026",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_4,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        form = TurmaForm(
            data={
                "unidade": self.unidade.pk,
                "nome": "4A",
                "ano_letivo": 2026,
                "turno": Turma.Turno.MANHA,
                "modalidade": Turma.Modalidade.REGULAR,
                "etapa": Turma.Etapa.CRECHE,
                "serie_ano": Turma.SerieAno.INFANTIL_BERCARIO,
                "forma_oferta": Turma.FormaOferta.PRESENCIAL,
                "matriz_curricular": matriz.pk,
                "curso": "",
                "classe_especial": "",
                "bilingue_surdos": "",
                "ativo": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["serie_ano"], Turma.SerieAno.FUNDAMENTAL_4)
        self.assertEqual(form.cleaned_data["etapa"], Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS)


class MatrizRelacoesEHorarioGeracaoTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_horario_matriz",
            password="123456",
            email="admin_horario_matriz@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Horário Matriz", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Horário")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Horário Matriz",
            tipo=Unidade.Tipo.EDUCACAO,
        )

        self.componente_lp = ComponenteCurricular.objects.create(nome="Língua Portuguesa", sigla="LP")
        self.componente_ma = ComponenteCurricular.objects.create(nome="Matemática", sigla="MAT")

    def test_relacao_matriz_bloqueia_componentes_de_matrizes_diferentes(self):
        matriz_a = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz A",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_5,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        matriz_b = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz B",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_4,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        comp_a = MatrizComponente.objects.create(matriz=matriz_a, componente=self.componente_lp, ordem=1, ativo=True)
        comp_b = MatrizComponente.objects.create(matriz=matriz_b, componente=self.componente_ma, ordem=1, ativo=True)

        rel = MatrizComponenteRelacao(
            origem=comp_a,
            destino=comp_b,
            tipo=MatrizComponenteRelacao.Tipo.PRE_REQUISITO,
            ativo=True,
        )
        with self.assertRaises(ValidationError):
            rel.full_clean()

    def test_horario_gerar_padrao_usa_componentes_da_matriz(self):
        matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz 5º ano 2026",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_5,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=matriz,
            componente=self.componente_lp,
            ordem=1,
            aulas_semanais=3,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=matriz,
            componente=self.componente_ma,
            ordem=2,
            aulas_semanais=2,
            ativo=True,
        )
        turma = Turma.objects.create(
            unidade=self.unidade,
            nome="5A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_5,
            matriz_curricular=matriz,
            ativo=True,
        )

        resp = self.client.get(reverse("educacao:horario_gerar_padrao", args=[turma.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)

        disciplinas = list(
            AulaHorario.objects.filter(grade__turma=turma)
            .order_by("dia", "inicio")
            .values_list("disciplina", flat=True)
        )
        self.assertEqual(len(disciplinas), 25)
        self.assertTrue(set(disciplinas).issubset({"Língua Portuguesa", "Matemática"}))
        self.assertIn("Língua Portuguesa", disciplinas)
        self.assertIn("Matemática", disciplinas)


class RequisitosMatrizFluxoTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_requisitos_edu",
            password="123456",
            email="admin_requisitos_edu@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Requisitos", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Requisitos")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Requisitos",
            tipo=Unidade.Tipo.EDUCACAO,
        )

        self.componente_base = ComponenteCurricular.objects.create(nome="Leitura", sigla="LEI", ativo=True)
        self.componente_equivalente = ComponenteCurricular.objects.create(nome="Letramento", sigla="LET", ativo=True)
        self.componente_destino = ComponenteCurricular.objects.create(nome="Produção Textual", sigla="PTX", ativo=True)

        self.matriz_alvo = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Alvo 2026",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_4,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        self.matriz_alvo_comp_base = MatrizComponente.objects.create(
            matriz=self.matriz_alvo,
            componente=self.componente_base,
            ordem=1,
            ativo=True,
        )
        self.matriz_alvo_comp_equiv = MatrizComponente.objects.create(
            matriz=self.matriz_alvo,
            componente=self.componente_equivalente,
            ordem=2,
            ativo=True,
        )
        self.matriz_alvo_comp_destino = MatrizComponente.objects.create(
            matriz=self.matriz_alvo,
            componente=self.componente_destino,
            ordem=3,
            ativo=True,
        )
        MatrizComponenteRelacao.objects.create(
            origem=self.matriz_alvo_comp_base,
            destino=self.matriz_alvo_comp_destino,
            tipo=MatrizComponenteRelacao.Tipo.PRE_REQUISITO,
            ativo=True,
        )

        self.turma_alvo = Turma.objects.create(
            unidade=self.unidade,
            nome="4A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_4,
            matriz_curricular=self.matriz_alvo,
            ativo=True,
        )

    def test_matricula_create_bloqueia_quando_pre_requisito_nao_cumprido(self):
        matriz_historico = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Histórico Reprovação",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_3,
            ano_referencia=2025,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=matriz_historico,
            componente=self.componente_equivalente,
            ordem=1,
            ativo=True,
        )
        turma_historico = Turma.objects.create(
            unidade=self.unidade,
            nome="3A",
            ano_letivo=2025,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_3,
            matriz_curricular=matriz_historico,
            ativo=True,
        )
        aluno = Aluno.objects.create(nome="Aluno Sem Pré")
        Matricula.objects.create(
            aluno=aluno,
            turma=turma_historico,
            situacao=Matricula.Situacao.CONCLUIDO,
            resultado_final="Reprovado",
        )

        avaliacao = avaliar_requisitos_matricula(aluno=aluno, turma=self.turma_alvo)
        self.assertTrue(avaliacao.bloqueado)
        self.assertTrue(any("Pré-requisitos pendentes" in msg for msg in avaliacao.pendencias))

    def test_matricula_create_aceita_equivalencia_por_grupo(self):
        grupo = MatrizComponenteEquivalenciaGrupo.objects.create(
            matriz=self.matriz_alvo,
            nome="Base Linguagens",
            minimo_componentes=1,
            ativo=True,
        )
        MatrizComponenteEquivalenciaItem.objects.create(
            grupo=grupo,
            componente=self.matriz_alvo_comp_base,
            ordem=1,
            ativo=True,
        )
        MatrizComponenteEquivalenciaItem.objects.create(
            grupo=grupo,
            componente=self.matriz_alvo_comp_equiv,
            ordem=2,
            ativo=True,
        )

        matriz_historico = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Histórico Equivalência",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_3,
            ano_referencia=2025,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=matriz_historico,
            componente=self.componente_equivalente,
            ordem=1,
            ativo=True,
        )
        turma_historico = Turma.objects.create(
            unidade=self.unidade,
            nome="3B",
            ano_letivo=2025,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_3,
            matriz_curricular=matriz_historico,
            ativo=True,
        )
        aluno = Aluno.objects.create(nome="Aluno Com Equivalência")
        Matricula.objects.create(
            aluno=aluno,
            turma=turma_historico,
            situacao=Matricula.Situacao.CONCLUIDO,
            resultado_final="Aprovado",
        )

        avaliacao = avaliar_requisitos_matricula(aluno=aluno, turma=self.turma_alvo)
        self.assertFalse(avaliacao.bloqueado, avaliacao.pendencias)

    def test_aula_form_bloqueia_lancamento_por_pre_requisito(self):
        professor = get_user_model().objects.create_user(username="prof_requisito", password="123456")
        diario = DiarioTurma.objects.create(
            turma=self.turma_alvo,
            professor=professor,
            ano_letivo=2026,
        )
        periodo = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=1,
            inicio="2026-02-01",
            fim="2026-04-30",
            ativo=True,
        )

        matriz_historico = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Histórico para Aula",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_3,
            ano_referencia=2025,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=matriz_historico,
            componente=self.componente_equivalente,
            ordem=1,
            ativo=True,
        )
        turma_historico = Turma.objects.create(
            unidade=self.unidade,
            nome="3C",
            ano_letivo=2025,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_3,
            matriz_curricular=matriz_historico,
            ativo=True,
        )
        aluno = Aluno.objects.create(nome="Aluno Pendência Aula")
        Matricula.objects.create(
            aluno=aluno,
            turma=turma_historico,
            situacao=Matricula.Situacao.CONCLUIDO,
            resultado_final="Reprovado",
        )
        Matricula.objects.create(
            aluno=aluno,
            turma=self.turma_alvo,
            situacao=Matricula.Situacao.ATIVA,
        )

        form = AulaForm(
            data={
                "data": "2026-03-10",
                "periodo": periodo.pk,
                "componente": self.componente_destino.pk,
                "bncc_codigos": [],
                "conteudo": "Aula com bloqueio de requisito",
                "observacoes": "",
            },
            diario=diario,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Lançamento bloqueado por pré-requisito", " ".join(form.errors.get("componente", [])))

    def test_matriz_consistencia_view_exibe_metricas(self):
        response = self.client.get(reverse("educacao:matriz_consistencia", args=[self.matriz_alvo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Relatório de Consistência da Matriz")
        self.assertContains(response, "Cobertura")

    def test_matricula_form_override_exige_justificativa(self):
        from apps.educacao.forms import MatriculaForm

        form = MatriculaForm(
            data={
                "turma": self.turma_alvo.pk,
                "data_matricula": "2026-02-10",
                "situacao": Matricula.Situacao.ATIVA,
                "resultado_final": "",
                "concluinte": "",
                "observacao": "",
                "override_requisitos": "on",
                "override_justificativa": "",
            },
            user=self.admin,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("justificativa", " ".join(form.errors.get("override_justificativa", [])).lower())

    def test_aula_form_permite_override_com_justificativa_para_gestor(self):
        professor = get_user_model().objects.create_user(username="prof_override", password="123456")
        diario = DiarioTurma.objects.create(
            turma=self.turma_alvo,
            professor=professor,
            ano_letivo=2026,
        )
        periodo = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=1,
            inicio="2026-02-01",
            fim="2026-04-30",
            ativo=True,
        )
        matriz_historico = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Histórico Override Aula",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_3,
            ano_referencia=2025,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=matriz_historico,
            componente=self.componente_equivalente,
            ordem=1,
            ativo=True,
        )
        turma_historico = Turma.objects.create(
            unidade=self.unidade,
            nome="3D",
            ano_letivo=2025,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_3,
            matriz_curricular=matriz_historico,
            ativo=True,
        )
        aluno = Aluno.objects.create(nome="Aluno Override Aula")
        Matricula.objects.create(
            aluno=aluno,
            turma=turma_historico,
            situacao=Matricula.Situacao.CONCLUIDO,
            resultado_final="Reprovado",
        )
        Matricula.objects.create(aluno=aluno, turma=self.turma_alvo, situacao=Matricula.Situacao.ATIVA)

        form = AulaForm(
            data={
                "data": "2026-03-20",
                "periodo": periodo.pk,
                "componente": self.componente_destino.pk,
                "bncc_codigos": [],
                "conteudo": "Aula com override pedagógico",
                "observacoes": "",
                "override_requisitos": "on",
                "override_justificativa": "Coordenação autorizou transição assistida.",
            },
            diario=diario,
            user=self.admin,
        )
        self.assertTrue(form.is_valid(), form.errors)
        payload = getattr(form, "override_requisitos_payload", {})
        self.assertTrue(payload)
        self.assertIn("justificativa", payload)

    def test_registra_auditoria_override_matricula(self):
        aluno = Aluno.objects.create(nome="Aluno Auditoria Override")
        registro = registrar_override_requisitos_matricula(
            usuario=self.admin,
            aluno=aluno,
            turma=self.turma_alvo,
            justificativa="Matrícula excepcional por decisão pedagógica.",
            pendencias=["Pré-requisito pendente: Leitura"],
            origem="TESTE",
        )
        self.assertIsNotNone(registro)
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                id=registro.id,
                modulo="EDUCACAO",
                evento="OVERRIDE_REQUISITOS_MATRICULA",
            ).exists()
        )


class TurmaProvisionamentoAutomaticoTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_provisionamento_turma",
            password="123456",
            email="admin_provisionamento_turma@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.prof = user_model.objects.create_user(username="prof_auto", password="123456", email="prof_auto@local")

        self.municipio = Municipio.objects.create(nome="Cidade Provisionamento", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Provisionamento")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Provisionamento",
            tipo=Unidade.Tipo.EDUCACAO,
        )

        prof_profile = getattr(self.prof, "profile", None)
        if prof_profile is None:
            prof_profile = Profile.objects.create(user=self.prof)
        prof_profile.role = Profile.Role.EDU_PROF
        prof_profile.municipio = self.municipio
        prof_profile.secretaria = self.secretaria
        prof_profile.unidade = self.unidade
        prof_profile.ativo = True
        prof_profile.bloqueado = False
        prof_profile.must_change_password = False
        prof_profile.save()

        self.componente_lp = ComponenteCurricular.objects.create(nome="Língua Portuguesa", sigla="LP")
        self.componente_mat = ComponenteCurricular.objects.create(nome="Matemática", sigla="MAT")

        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz 5º ano 2026",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_5,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=self.matriz,
            componente=self.componente_lp,
            ordem=1,
            aulas_semanais=3,
            ativo=True,
        )
        MatrizComponente.objects.create(
            matriz=self.matriz,
            componente=self.componente_mat,
            ordem=2,
            aulas_semanais=2,
            ativo=True,
        )

    def test_turma_create_gera_diarios_e_horario_automaticamente(self):
        resp = self.client.post(
            reverse("educacao:turma_create"),
            data={
                "unidade": self.unidade.pk,
                "nome": "5A",
                "ano_letivo": 2026,
                "turno": Turma.Turno.MANHA,
                "modalidade": Turma.Modalidade.REGULAR,
                "etapa": Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
                "serie_ano": Turma.SerieAno.FUNDAMENTAL_5,
                "forma_oferta": Turma.FormaOferta.PRESENCIAL,
                "matriz_curricular": self.matriz.pk,
                "professores": [self.prof.pk],
                "curso": "",
                "classe_especial": "",
                "bilingue_surdos": "",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        turma = Turma.objects.get(nome="5A", unidade=self.unidade)
        self.assertTrue(turma.professores.filter(pk=self.prof.pk).exists())

        diario = DiarioTurma.objects.filter(turma=turma, professor=self.prof, ano_letivo=2026).first()
        self.assertIsNotNone(diario)

        grade = GradeHorario.objects.filter(turma=turma).first()
        self.assertIsNotNone(grade)
        aulas = list(grade.aulas.all())
        self.assertEqual(len(aulas), 25)
        self.assertTrue(any(a.professor_id == self.prof.pk for a in aulas))


class MatrizServicoAnualTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Matriz Anual", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Matriz Anual")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Matriz Anual",
            tipo=Unidade.Tipo.EDUCACAO,
        )

    def test_preencher_componentes_base_e_clonar_para_proximo_ano(self):
        matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz 9º ano",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_9,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )

        created, skipped = preencher_componentes_base_matriz(matriz)
        self.assertGreater(created, 0)
        self.assertEqual(skipped, 0)
        self.assertTrue(matriz.componentes.filter(componente__nome="Língua Portuguesa").exists())
        self.assertTrue(matriz.componentes.filter(componente__nome="Língua Inglesa").exists())

        copia = clonar_matriz_para_ano(matriz, ano_destino=2027)
        self.assertEqual(copia.ano_referencia, 2027)
        self.assertEqual(copia.componentes.count(), matriz.componentes.count())


class MatriculaRapidaViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_matricula_rapida",
            password="123456",
            email="admin_matricula_rapida@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Matrícula", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Matrícula")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Matrícula", tipo=Unidade.Tipo.EDUCACAO)

        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz 4º ano 2026",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_4,
            ano_referencia=2026,
            carga_horaria_anual=800,
            dias_letivos_previstos=200,
            ativo=True,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="4A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_4,
            matriz_curricular=self.matriz,
            ativo=True,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Matrícula Rápida")

    def test_fluxo_matricula_rapida_cria_matricula(self):
        resp = self.client.post(
            reverse("educacao:matricula_create") + f"?aluno={self.aluno.pk}",
            data={
                "aluno": str(self.aluno.pk),
                "turma": str(self.turma.pk),
                "data_matricula": "2026-03-04",
                "situacao": Matricula.Situacao.ATIVA,
                "resultado_final": "",
                "concluinte": "",
                "observacao": "Matrícula inicial",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Matricula.objects.filter(aluno=self.aluno, turma=self.turma).exists())


class MatrizModelosOficiaisViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_modelos_matriz",
            password="123456",
            email="admin_modelos_matriz@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Modelos", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Modelos")
        self.unidade_a = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Modelo A",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.unidade_b = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Modelo B",
            tipo=Unidade.Tipo.EDUCACAO,
        )

    def test_aplicar_modelo_oficial_em_lote(self):
        resp = self.client.post(
            reverse("educacao:matriz_modelos"),
            data={
                "_action": "aplicar_oficial",
                "oficial-rede_modelo": "MUNICIPAL",
                "oficial-ano_referencia": "2026",
                "oficial-secretaria": str(self.secretaria.pk),
                "oficial-sobrescrever_existentes": "",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        total_a = MatrizCurricular.objects.filter(unidade=self.unidade_a, ano_referencia=2026).count()
        total_b = MatrizCurricular.objects.filter(unidade=self.unidade_b, ano_referencia=2026).count()
        self.assertGreaterEqual(total_a, 14)
        self.assertGreaterEqual(total_b, 14)

        matriz_1ano = MatrizCurricular.objects.filter(
            unidade=self.unidade_a,
            ano_referencia=2026,
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_1,
        ).first()
        self.assertIsNotNone(matriz_1ano)
        self.assertTrue(matriz_1ano.componentes.filter(componente__nome="Língua Portuguesa").exists())

    def test_importar_csv_modelo_aplica_em_unidade(self):
        csv_data = "\n".join(
            [
                "etapa_base,serie_ano,matriz_nome,componente_nome,componente_sigla,aulas_semanais,carga_horaria_anual,ordem,area_codigo_bncc",
                "FUNDAMENTAL_ANOS_INICIAIS,FUNDAMENTAL_4,Matriz CSV 4º Ano,Língua Portuguesa,LP,7,280,1,LP",
                "FUNDAMENTAL_ANOS_INICIAIS,FUNDAMENTAL_4,Matriz CSV 4º Ano,Matemática,MAT,6,240,2,MA",
            ]
        )
        arquivo = SimpleUploadedFile(
            "modelo_matriz.csv",
            csv_data.encode("utf-8"),
            content_type="text/csv",
        )

        resp = self.client.post(
            reverse("educacao:matriz_modelos"),
            data={
                "_action": "importar_csv",
                "import-ano_referencia": "2027",
                "import-secretaria": str(self.secretaria.pk),
                "import-unidades": [str(self.unidade_a.pk)],
                "import-sobrescrever_existentes": "on",
                "import-arquivo_csv": arquivo,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        matriz = MatrizCurricular.objects.filter(
            unidade=self.unidade_a,
            ano_referencia=2027,
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_4,
        ).first()
        self.assertIsNotNone(matriz)
        self.assertEqual(matriz.componentes.count(), 2)
        self.assertTrue(matriz.componentes.filter(componente__sigla="LP").exists())
        self.assertTrue(matriz.componentes.filter(componente__sigla="MAT").exists())


class EstagioCrudViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_estagio",
            password="123456",
            email="admin_estagio@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Estágio", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Estágio")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Estágio",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="9A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_9,
            ativo=True,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Estágio")
        self.matricula = Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

    def test_fluxo_create_list_update_estagio(self):
        resp_create = self.client.post(
            reverse("educacao:estagio_create"),
            data={
                "aluno": str(self.aluno.pk),
                "matricula": str(self.matricula.pk),
                "turma": str(self.turma.pk),
                "unidade": str(self.unidade.pk),
                "tipo": Estagio.Tipo.OBRIGATORIO,
                "situacao": Estagio.Situacao.EM_ANALISE,
                "concedente_nome": "Hospital Municipal",
                "concedente_cnpj": "12.345.678/0001-90",
                "supervisor_nome": "Maria Supervisora",
                "orientador": str(self.admin.pk),
                "data_inicio_prevista": "2026-03-10",
                "data_fim_prevista": "2026-06-30",
                "carga_horaria_total": "160",
                "carga_horaria_cumprida": "0",
                "equivalencia_solicitada": "",
                "equivalencia_aprovada": "",
                "observacao": "Primeiro registro de estágio.",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp_create.status_code, 200)
        self.assertEqual(Estagio.objects.count(), 1)
        estagio = Estagio.objects.first()
        self.assertEqual(estagio.concedente_nome, "Hospital Municipal")

        resp_list = self.client.get(reverse("educacao:estagio_list"))
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, "Hospital Municipal")

        resp_update = self.client.post(
            reverse("educacao:estagio_update", args=[estagio.pk]),
            data={
                "aluno": str(self.aluno.pk),
                "matricula": str(self.matricula.pk),
                "turma": str(self.turma.pk),
                "unidade": str(self.unidade.pk),
                "tipo": Estagio.Tipo.NAO_OBRIGATORIO,
                "situacao": Estagio.Situacao.APROVADO,
                "concedente_nome": "Hospital Municipal",
                "concedente_cnpj": "12.345.678/0001-90",
                "supervisor_nome": "Maria Supervisora",
                "orientador": str(self.admin.pk),
                "data_inicio_prevista": "2026-03-10",
                "data_fim_prevista": "2026-06-30",
                "data_inicio_real": "2026-03-12",
                "data_fim_real": "",
                "carga_horaria_total": "160",
                "carga_horaria_cumprida": "20",
                "equivalencia_solicitada": "on",
                "equivalencia_aprovada": "",
                "observacao": "Aprovado para início.",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp_update.status_code, 200)
        estagio.refresh_from_db()
        self.assertEqual(estagio.tipo, Estagio.Tipo.NAO_OBRIGATORIO)
        self.assertEqual(estagio.situacao, Estagio.Situacao.APROVADO)
        self.assertEqual(estagio.carga_horaria_cumprida, 20)

    def test_model_rejeita_equivalencia_aprovada_sem_solicitacao(self):
        estagio = Estagio(
            aluno=self.aluno,
            matricula=self.matricula,
            turma=self.turma,
            unidade=self.unidade,
            tipo=Estagio.Tipo.OBRIGATORIO,
            situacao=Estagio.Situacao.EM_ANALISE,
            concedente_nome="Empresa XPTO",
            carga_horaria_total=120,
            carga_horaria_cumprida=10,
            equivalencia_solicitada=False,
            equivalencia_aprovada=True,
        )
        with self.assertRaises(ValidationError):
            estagio.full_clean()


class TurmaGeracaoLoteViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_lote_turma",
            password="123456",
            email="admin_lote_turma@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Lote", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Lote")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Lote", tipo=Unidade.Tipo.EDUCACAO)
        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Lote 5º Ano",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_5,
            ano_referencia=2026,
            ativo=True,
        )

    def _payload(self, action: str):
        return {
            "_action": action,
            "ano_letivo": "2026",
            "secretaria": str(self.secretaria.pk),
            "unidade": str(self.unidade.pk),
            "matrizes": [str(self.matriz.pk)],
            "quantidade_por_matriz": "2",
            "turno": Turma.Turno.MANHA,
            "prefixo_nome": "GNF",
            "gerar_horario": "on",
            "turmas_ativas": "on",
        }

    def test_wizard_preview_and_execute(self):
        resp_preview = self.client.post(
            reverse("educacao:turma_geracao_lote"),
            data=self._payload("preview"),
            follow=True,
        )
        self.assertEqual(resp_preview.status_code, 200)
        self.assertContains(resp_preview, "Pr\u00e9via da gera\u00e7\u00e3o")

        resp_execute = self.client.post(
            reverse("educacao:turma_geracao_lote"),
            data=self._payload("execute"),
            follow=True,
        )
        self.assertEqual(resp_execute.status_code, 200)
        turmas = Turma.objects.filter(unidade=self.unidade, ano_letivo=2026, matriz_curricular=self.matriz)
        self.assertEqual(turmas.count(), 2)
        self.assertEqual(GradeHorario.objects.filter(turma__in=turmas).count(), 2)


class EvasaoLoteViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_evasao_lote",
            password="123456",
            email="admin_evasao_lote@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Evasao", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Evasao")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Evasao", tipo=Unidade.Tipo.EDUCACAO)
        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Evasao 6º Ano",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_6,
            ano_referencia=2026,
            ativo=True,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="6A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_6,
            matriz_curricular=self.matriz,
            ativo=True,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Lote Evasao")
        self.matricula = Matricula.objects.create(
            aluno=self.aluno,
            turma=self.turma,
            situacao=Matricula.Situacao.ATIVA,
            data_matricula=date(2026, 3, 1),
        )

    def test_evasao_lote_execute_and_rollback(self):
        resp_execute = self.client.post(
            reverse("educacao:evasao_lote"),
            data={
                "_action": "execute",
                "ano_letivo": "2026",
                "secretaria": str(self.secretaria.pk),
                "unidade": str(self.unidade.pk),
                "turma": str(self.turma.pk),
                "data_referencia": "2026-03-13",
                "motivo": "Teste de evasão em lote",
            },
            follow=True,
        )
        self.assertEqual(resp_execute.status_code, 200)
        self.matricula.refresh_from_db()
        self.assertEqual(self.matricula.situacao, Matricula.Situacao.EVADIDO)

        mov = (
            MatriculaMovimentacao.objects.filter(
                matricula=self.matricula,
                tipo=MatriculaMovimentacao.Tipo.SITUACAO,
                situacao_nova=Matricula.Situacao.EVADIDO,
            )
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(mov)
        self.assertIn("[EVASAO-LOTE:", mov.motivo)
        token = mov.motivo.split("[EVASAO-LOTE:", 1)[1].split("]", 1)[0]

        resp_rollback = self.client.post(
            reverse("educacao:evasao_lote"),
            data={
                "_action": "rollback",
                "rollback_token": token,
            },
            follow=True,
        )
        self.assertEqual(resp_rollback.status_code, 200)

        self.matricula.refresh_from_db()
        self.assertEqual(self.matricula.situacao, Matricula.Situacao.ATIVA)
        self.assertTrue(
            MatriculaMovimentacao.objects.filter(
                matricula=self.matricula,
                tipo=MatriculaMovimentacao.Tipo.DESFAZER,
                movimentacao_desfeita=mov,
            ).exists()
        )


class FechamentoPeriodoLoteViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_fechamento_lote",
            password="123456",
            email="admin_fechamento_lote@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Fechamento Lote", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Fechamento Lote")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Fechamento Lote", tipo=Unidade.Tipo.EDUCACAO)
        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Fechamento 8º Ano",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_8,
            ano_referencia=2026,
            ativo=True,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="8A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_8,
            matriz_curricular=self.matriz,
            ativo=True,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Fechamento Lote")
        Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        self.periodo = PeriodoLetivo.objects.create(
            ano_letivo=2026,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=1,
            inicio=date(2026, 2, 16),
            fim=date(2026, 5, 4),
            ativo=True,
        )

    def _payload(self, action: str):
        return {
            "_action": action,
            "ano_letivo": "2026",
            "periodo": str(self.periodo.pk),
            "secretaria": str(self.secretaria.pk),
            "unidade": str(self.unidade.pk),
            "media_corte": "6.00",
            "frequencia_corte": "75.00",
            "somente_com_matriculas": "on",
            "observacao": "Fechamento em lote para validação.",
        }

    def test_fluxo_fechamento_e_reabertura_em_lote(self):
        resp_preview = self.client.post(
            reverse("educacao:fechamento_periodo_lote"),
            data=self._payload("preview"),
            follow=True,
        )
        self.assertEqual(resp_preview.status_code, 200)
        self.assertContains(resp_preview, "Prévia do lote")

        resp_fechar = self.client.post(
            reverse("educacao:fechamento_periodo_lote"),
            data=self._payload("fechar"),
            follow=True,
        )
        self.assertEqual(resp_fechar.status_code, 200)
        self.assertTrue(
            FechamentoPeriodoTurma.objects.filter(turma=self.turma, periodo=self.periodo).exists()
        )

        resp_reabrir = self.client.post(
            reverse("educacao:fechamento_periodo_lote"),
            data=self._payload("reabrir"),
            follow=True,
        )
        self.assertEqual(resp_reabrir.status_code, 200)
        self.assertFalse(
            FechamentoPeriodoTurma.objects.filter(turma=self.turma, periodo=self.periodo).exists()
        )


class AlunoIngressoProcessoSeletivoTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_ingresso_processo",
            password="123456",
            email="admin_ingresso_processo@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Ingresso", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Ingresso")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Ingresso", tipo=Unidade.Tipo.EDUCACAO)
        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Ingresso 4º Ano",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_4,
            ano_referencia=2026,
            ativo=True,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="4A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_4,
            matriz_curricular=self.matriz,
            ativo=True,
        )

    def test_cria_ingressante_com_processo_seletivo(self):
        resp = self.client.post(
            reverse("educacao:aluno_create"),
            data={
                "nome": "Aluno Processo Seletivo",
                "turma": str(self.turma.pk),
                "origem_ingresso": "PROCESSO_SELETIVO",
                "processo_numero": "PROC-PS-2026-0001",
                "processo_assunto": "Ingresso por processo seletivo",
                "edital_referencia": "Edital 01/2026",
                "observacao_ingresso": "Aprovado na primeira chamada.",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        aluno = Aluno.objects.filter(nome="Aluno Processo Seletivo").first()
        self.assertIsNotNone(aluno)

        matricula = Matricula.objects.filter(aluno=aluno, turma=self.turma).first()
        self.assertIsNotNone(matricula)

        processo = ProcessoAdministrativo.objects.filter(
            municipio=self.municipio,
            numero="PROC-PS-2026-0001",
        ).first()
        self.assertIsNotNone(processo)
        self.assertEqual(processo.status, ProcessoAdministrativo.Status.CONCLUIDO)

        self.assertTrue(
            MatriculaMovimentacao.objects.filter(
                matricula=matricula,
                tipo=MatriculaMovimentacao.Tipo.CRIACAO,
                motivo__icontains="PROC-PS-2026-0001",
            ).exists()
        )


class OperacoesLoteViewTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_operacoes_lote",
            password="123456",
            email="admin_operacoes_lote@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.municipio = Municipio.objects.create(nome="Cidade Operações", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Operações")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Operações", tipo=Unidade.Tipo.EDUCACAO)
        self.matriz = MatrizCurricular.objects.create(
            unidade=self.unidade,
            nome="Matriz Operações",
            etapa_base=MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=MatrizCurricular.SerieAno.FUNDAMENTAL_3,
            ano_referencia=2026,
            ativo=True,
        )
        self.turma = Turma.objects.create(
            unidade=self.unidade,
            nome="3A",
            ano_letivo=2026,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
            serie_ano=Turma.SerieAno.FUNDAMENTAL_3,
            matriz_curricular=self.matriz,
            ativo=True,
        )
        self.aluno = Aluno.objects.create(nome="Aluno Foto Lote", cpf="11122233344")
        self.matricula = Matricula.objects.create(aluno=self.aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)

    def _base_payload(self):
        return {
            "turma": str(self.turma.pk),
            "estrategia_foto": "ALUNO_ID",
        }

    def test_aplicar_fotos_zip_por_id_aluno(self):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00"
            b"\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        buffer = BytesIO()
        with ZipFile(buffer, "w") as zf:
            zf.writestr(f"{self.aluno.id}.png", png_bytes)
        zip_upload = SimpleUploadedFile("fotos.zip", buffer.getvalue(), content_type="application/zip")

        payload = self._base_payload()
        payload["_action"] = "aplicar_fotos"

        resp = self.client.post(
            reverse("educacao:operacoes_lote"),
            data={**payload, "arquivo_zip": zip_upload},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.aluno.refresh_from_db()
        self.assertTrue(bool(self.aluno.foto))

    def test_gera_carometro_pdf(self):
        with patch("apps.educacao.views_operacoes_lote.export_pdf_template") as export_mock:
            export_mock.return_value = HttpResponse(b"%PDF-1.4", content_type="application/pdf")
            payload = self._base_payload()
            payload["_action"] = "carometro_pdf"
            resp = self.client.post(reverse("educacao:operacoes_lote"), data=payload)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp["Content-Type"], "application/pdf")
            export_mock.assert_called_once()


class MinicursoFlowTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin_minicurso_flow",
            password="123456",
            email="admin_minicurso_flow@local",
        )
        profile = getattr(self.admin, "profile", None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

        self.prof = user_model.objects.create_user(
            username="prof_minicurso",
            password="123456",
            email="prof_minicurso@local",
        )
        if getattr(self.prof, "profile", None):
            self.prof.profile.role = "EDU_PROF"
            self.prof.profile.ativo = True
            self.prof.profile.must_change_password = False
            self.prof.profile.save(update_fields=["role", "ativo", "must_change_password"])

        self.municipio = Municipio.objects.create(nome="Cidade Minicurso", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED Minicurso")
        self.unidade = Unidade.objects.create(secretaria=self.secretaria, nome="Escola Minicurso", tipo=Unidade.Tipo.EDUCACAO)
        self.aluno = Aluno.objects.create(nome="Aluno Minicurso")

    def test_fluxo_completo_minicurso(self):
        resp_curso = self.client.post(
            reverse("educacao:minicurso_curso_create"),
            data={
                "nome": "Minicurso Robótica",
                "codigo": "MINI-ROBO-01",
                "modalidade_oferta": Curso.ModalidadeOferta.FIC,
                "eixo_tecnologico": "Tecnologia",
                "carga_horaria": "40",
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp_curso.status_code, 200)
        curso = Curso.objects.filter(codigo="MINI-ROBO-01").first()
        self.assertIsNotNone(curso)

        resp_turma = self.client.post(
            reverse("educacao:minicurso_turma_create"),
            data={
                "curso": str(curso.pk),
                "unidade": str(self.unidade.pk),
                "nome": "Turma Robótica A",
                "ano_letivo": "2026",
                "turno": Turma.Turno.TARDE,
                "professores": [str(self.prof.pk)],
                "ativo": "on",
            },
            follow=True,
        )
        self.assertEqual(resp_turma.status_code, 200)
        turma = Turma.objects.filter(nome="Turma Robótica A", curso=curso).first()
        self.assertIsNotNone(turma)
        self.assertEqual(turma.modalidade, Turma.Modalidade.ATIVIDADE_COMPLEMENTAR)

        resp_matricula = self.client.post(
            reverse("educacao:minicurso_matricula_create"),
            data={
                "aluno": str(self.aluno.pk),
                "curso": str(curso.pk),
                "turma": str(turma.pk),
                "data_matricula": "2026-03-16",
                "observacao": "Matrícula de teste no fluxo.",
            },
            follow=True,
        )
        self.assertEqual(resp_matricula.status_code, 200)
        matricula = MatriculaCurso.objects.filter(aluno=self.aluno, curso=curso, turma=turma).first()
        self.assertIsNotNone(matricula)

        resp_cert = self.client.post(
            reverse("educacao:minicurso_certificado_emitir"),
            data={
                "matricula_curso": str(matricula.pk),
                "data_emissao": "2026-07-20",
                "titulo": "Certificado de Robótica",
                "resultado_final": "Aprovado",
            },
            follow=True,
        )
        self.assertEqual(resp_cert.status_code, 200)
        certificado = AlunoCertificado.objects.filter(
            aluno=self.aluno,
            curso=curso,
            tipo=AlunoCertificado.Tipo.CERTIFICADO_CURSO,
        ).first()
        self.assertIsNotNone(certificado)
