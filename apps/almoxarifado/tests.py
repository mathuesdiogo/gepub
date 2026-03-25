from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.org.models import LocalEstrutural, Municipio, Secretaria, Unidade

from .models import AlmoxarifadoLocal, EstoqueSaldo, MovimentacaoEstoque, ProdutoEstoque, RequisicaoEstoque


class AlmoxarifadoNovoModeloTestCase(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Cidade Estoque", uf="MA")
        self.secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Educação")
        self.unidade = Unidade.objects.create(
            secretaria=self.secretaria,
            nome="Escola Central",
            tipo=Unidade.Tipo.EDUCACAO,
            tipo_educacional=Unidade.TipoEducacional.ESCOLA,
        )
        self.local = LocalEstrutural.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            nome="Depósito",
            tipo_local=LocalEstrutural.TipoLocal.DEPOSITO,
        )
        self.almox = AlmoxarifadoLocal.objects.create(
            municipio=self.municipio,
            secretaria=self.secretaria,
            unidade=self.unidade,
            local_estrutural=self.local,
            nome="Almox Escola Central",
        )
        self.produto = ProdutoEstoque.objects.create(
            municipio=self.municipio,
            codigo_interno="PAPEL-A4",
            nome="Papel A4",
            categoria="Expediente",
        )

    def test_estoque_saldo_calcula_disponivel(self):
        saldo = EstoqueSaldo.objects.create(
            produto=self.produto,
            almoxarifado_local=self.almox,
            quantidade_atual=10,
            quantidade_reservada=2,
        )
        self.assertEqual(float(saldo.quantidade_disponivel), 8.0)

    def test_movimentacao_saida_exige_origem(self):
        mov = MovimentacaoEstoque(
            municipio=self.municipio,
            tipo_movimentacao=MovimentacaoEstoque.TipoMovimentacao.SAIDA,
            produto=self.produto,
            quantidade=1,
        )
        with self.assertRaises(ValidationError):
            mov.full_clean()

    def test_requisicao_local_deve_pertencer_unidade(self):
        outra_secretaria = Secretaria.objects.create(municipio=self.municipio, nome="Saúde")
        outra_unidade = Unidade.objects.create(
            secretaria=outra_secretaria,
            nome="UBS Centro",
            tipo=Unidade.Tipo.SAUDE,
        )
        local_outra = LocalEstrutural.objects.create(
            municipio=self.municipio,
            secretaria=outra_secretaria,
            unidade=outra_unidade,
            nome="Farmácia",
            tipo_local=LocalEstrutural.TipoLocal.DEPOSITO,
        )
        req = RequisicaoEstoque(
            municipio=self.municipio,
            numero="REQ-001",
            secretaria=self.secretaria,
            unidade_solicitante=self.unidade,
            local_solicitante=local_outra,
            produto=self.produto,
            quantidade=1,
        )
        with self.assertRaises(ValidationError):
            req.full_clean()
