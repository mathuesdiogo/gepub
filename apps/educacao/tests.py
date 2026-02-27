from django.test import TestCase
from unittest.mock import patch
from django.urls import reverse
from datetime import date, time, timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile

from django.contrib.auth import get_user_model

from apps.accounts.models import Profile
from apps.educacao.forms_horarios import AulaHorarioForm
from apps.educacao.forms_diario import AulaForm
from apps.educacao.models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    CoordenacaoEnsino,
    Curso,
    CursoDisciplina,
    Matricula,
    MatriculaCurso,
    MatriculaMovimentacao,
    Turma,
)
from apps.educacao.models_horarios import GradeHorario, AulaHorario
from apps.educacao.models_notas import BNCCCodigo, ComponenteCurricular
from apps.educacao.models_diario import Aula, Avaliacao, DiarioTurma, Frequencia, Nota
from apps.educacao.models_periodos import FechamentoPeriodoTurma, PeriodoLetivo
from apps.educacao.models_assistencia import CardapioEscolar, RegistroRefeicaoEscolar, RegistroTransporteEscolar, RotaTransporteEscolar
from apps.educacao.models_calendario import CalendarioEducacionalEvento
from apps.educacao.services_matricula import registrar_movimentacao
from apps.org.models import Municipio, Secretaria, Unidade


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
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Portal do Aluno")


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
