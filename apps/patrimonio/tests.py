from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.org.models import LocalEstrutural, Municipio, Secretaria, Unidade

from .models import BemPatrimonial, MovimentacaoPatrimonial


class PatrimonioNovoModeloTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Patrimônio", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Administração")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Sede",
            tipo=Unidade.Tipo.ADMINISTRACAO,
        )
        self.local = LocalEstrutural.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            nome="Sala TI",
            tipo_local=LocalEstrutural.TipoLocal.SALA,
        )

    def _create_bem(self, tombamento: str, descricao: str = "Notebook") -> BemPatrimonial:
        return BemPatrimonial.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            local_estrutural=self.local,
            numero_tombamento=tombamento,
            descricao=descricao,
        )

    def test_tombamento_unico_por_municipio(self):
        self._create_bem("TMB-001")
        with self.assertRaises(ValidationError):
            self._create_bem("TMB-001", descricao="Desktop")

    def test_baixa_marca_bem_inativo_sem_apagar(self):
        bem = self._create_bem("TMB-002")
        bem.situacao = BemPatrimonial.Situacao.BAIXADO
        bem.save()
        bem.refresh_from_db()
        self.assertFalse(bem.ativo)

    def test_movimentacao_nao_permite_mesmo_local_origem_destino(self):
        bem = self._create_bem("TMB-003")
        mov = MovimentacaoPatrimonial(
            bem=bem,
            tipo_movimentacao=MovimentacaoPatrimonial.TipoMovimentacao.TRANSFERENCIA_INTERNA,
            local_origem=self.local,
            local_destino=self.local,
        )
        with self.assertRaises(ValidationError):
            mov.full_clean()
