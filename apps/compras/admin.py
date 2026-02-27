from django.contrib import admin

from .models import ProcessoLicitatorio, RequisicaoCompra, RequisicaoCompraItem


class RequisicaoCompraItemInline(admin.TabularInline):
    model = RequisicaoCompraItem
    extra = 0


@admin.register(RequisicaoCompra)
class RequisicaoCompraAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "objeto", "status", "valor_estimado", "empenho")
    list_filter = ("municipio", "status")
    search_fields = ("numero", "objeto", "fornecedor_nome")
    inlines = [RequisicaoCompraItemInline]


@admin.register(ProcessoLicitatorio)
class ProcessoLicitatorioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero_processo", "modalidade", "status", "data_abertura")
    list_filter = ("municipio", "modalidade", "status")
    search_fields = ("numero_processo", "objeto", "vencedor_nome")
