from __future__ import annotations

from io import BytesIO
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image, ImageDraw

from apps.educacao.models import Aluno, Matricula, Turma
from apps.educacao.models_diario import Nota
from apps.org.models import Municipio, Secretaria, Unidade

from .models import AvaliacaoProva, GabaritoProva
from .omr import suggest_answers_from_omr_image
from .services import corrigir_folha_manual, ensure_aplicacoes_da_avaliacao


class AvaliacoesServicesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="prof_avaliacao", password="x")

        self.municipio = Municipio.objects.create(nome="Cidade Provas", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="SEMED")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Municipal 1",
            tipo=Unidade.Tipo.EDUCACAO,
        )
        self.turma = Turma.objects.create(unidade=self.unidade, nome="5A", ano_letivo=2026)

    def _create_aluno(self, nome: str):
        aluno = Aluno.objects.create(nome=nome)
        Matricula.objects.create(aluno=aluno, turma=self.turma, situacao=Matricula.Situacao.ATIVA)
        return aluno

    def test_sync_aplicacoes_with_versions_a_b(self):
        self._create_aluno("Ana")
        self._create_aluno("Bruno")
        self._create_aluno("Carla")

        avaliacao = AvaliacaoProva.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            turma=self.turma,
            titulo="Prova Bimestral",
            disciplina="Matematica",
            qtd_questoes=5,
            opcoes=5,
            tem_versoes=True,
            criado_por=self.user,
        )

        info = ensure_aplicacoes_da_avaliacao(avaliacao, actor=self.user)

        self.assertEqual(info["total"], 3)
        self.assertEqual(info["criadas"], 3)
        versoes = list(avaliacao.aplicacoes.order_by("aluno__nome").values_list("versao", flat=True))
        self.assertEqual(versoes, ["A", "B", "A"])

    def test_manual_correction_calculates_grade_and_launches_nota(self):
        aluno = self._create_aluno("Daniel")

        avaliacao = AvaliacaoProva.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            turma=self.turma,
            titulo="Prova Final",
            disciplina="Portugues",
            qtd_questoes=3,
            opcoes=5,
            tem_versoes=False,
            nota_maxima=Decimal("10.00"),
            criado_por=self.user,
        )
        ensure_aplicacoes_da_avaliacao(avaliacao, actor=self.user)

        gabarito = GabaritoProva.objects.get(avaliacao=avaliacao, versao="A")
        gabarito.respostas = {"1": "A", "2": "B", "3": "C"}
        gabarito.atualizado_por = self.user
        gabarito.save()

        aplicacao = avaliacao.aplicacoes.get(aluno=aluno)
        resultado = corrigir_folha_manual(
            aplicacao.folha,
            respostas_marcadas={"1": "A", "2": "D", "3": "C"},
            actor=self.user,
        )

        self.assertEqual(resultado["acertos"], 2)
        self.assertEqual(resultado["nota"], Decimal("6.67"))

        aplicacao.refresh_from_db()
        self.assertEqual(aplicacao.status, aplicacao.Status.CORRIGIDA)
        self.assertEqual(aplicacao.nota, Decimal("6.67"))
        self.assertIsNotNone(aplicacao.nota_diario)

        nota = Nota.objects.get(avaliacao=aplicacao.nota_diario.avaliacao, aluno=aluno)
        self.assertEqual(nota.valor, Decimal("6.67"))

    def test_public_validation_route_is_accessible_without_login(self):
        aluno = self._create_aluno("Eva")
        avaliacao = AvaliacaoProva.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            turma=self.turma,
            titulo="Prova Diagnostica",
            disciplina="Historia",
            qtd_questoes=2,
            opcoes=4,
            tem_versoes=False,
            criado_por=self.user,
        )
        ensure_aplicacoes_da_avaliacao(avaliacao, actor=self.user)
        folha = avaliacao.aplicacoes.get(aluno=aluno).folha

        response = self.client.get(reverse("avaliacoes:folha_validar", args=[folha.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Validação de Folha de Prova")

    def test_omr_detects_marked_answers_from_synthetic_image(self):
        qtd_questoes = 5
        opcoes = 4
        escolhas = ["A", "C", "D", "B", "A"]

        width, height = 1200, 1700
        img = Image.new("L", (width, height), color=255)
        draw = ImageDraw.Draw(img)

        left = int(width * 0.08)
        right = int(width * 0.92)
        top = int(height * 0.32)
        bottom = int(height * 0.92)
        row_h = (bottom - top) / float(qtd_questoes + 1)
        col_w = (right - left) / float(1 + opcoes)

        letters = ["A", "B", "C", "D"][:opcoes]
        for q_num, resposta in enumerate(escolhas, start=1):
            opt_idx = letters.index(resposta)
            cx = int(left + (opt_idx + 1.5) * col_w)
            cy = int(top + (q_num + 0.5) * row_h)
            r = 10
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)

        buf = BytesIO()
        img.save(buf, format="PNG")
        upload = SimpleUploadedFile("omr.png", buf.getvalue(), content_type="image/png")

        result = suggest_answers_from_omr_image(upload, qtd_questoes=qtd_questoes, opcoes=opcoes)
        self.assertEqual(result["respostas"], {str(idx + 1): val for idx, val in enumerate(escolhas)})
