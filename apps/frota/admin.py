from django.contrib import admin

from .models import FrotaAbastecimento, FrotaCadastro, FrotaManutencao, FrotaViagem


@admin.register(FrotaCadastro)
class FrotaCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "placa", "nome", "situacao", "status")
    list_filter = ("municipio", "situacao", "status")
    search_fields = ("codigo", "placa", "nome", "marca_modelo")


@admin.register(FrotaAbastecimento)
class FrotaAbastecimentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "veiculo", "data_abastecimento", "litros", "valor_total", "quilometragem")
    list_filter = ("municipio", "data_abastecimento")
    search_fields = ("veiculo__codigo", "veiculo__placa", "posto")


@admin.register(FrotaManutencao)
class FrotaManutencaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "veiculo", "tipo", "status", "data_inicio", "data_fim", "valor_total")
    list_filter = ("municipio", "tipo", "status")
    search_fields = ("veiculo__codigo", "veiculo__placa", "descricao", "oficina")


@admin.register(FrotaViagem)
class FrotaViagemAdmin(admin.ModelAdmin):
    list_display = ("municipio", "veiculo", "motorista", "destino", "status", "data_saida", "data_retorno")
    list_filter = ("municipio", "status")
    search_fields = ("veiculo__codigo", "veiculo__placa", "destino", "motorista__username")
