from django.contrib import admin

from .models import AditivoContrato, ContratoAdministrativo, MedicaoContrato


class AditivoContratoInline(admin.TabularInline):
    model = AditivoContrato
    extra = 0


class MedicaoContratoInline(admin.TabularInline):
    model = MedicaoContrato
    extra = 0


@admin.register(ContratoAdministrativo)
class ContratoAdministrativoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "fornecedor_nome", "valor_total", "status", "vigencia_fim", "empenho")
    list_filter = ("municipio", "status")
    search_fields = ("numero", "objeto", "fornecedor_nome")
    inlines = [AditivoContratoInline, MedicaoContratoInline]


@admin.register(AditivoContrato)
class AditivoContratoAdmin(admin.ModelAdmin):
    list_display = ("contrato", "tipo", "numero", "data_ato", "valor_aditivo", "nova_vigencia_fim")
    list_filter = ("tipo", "data_ato")
    search_fields = ("contrato__numero", "numero")


@admin.register(MedicaoContrato)
class MedicaoContratoAdmin(admin.ModelAdmin):
    list_display = ("contrato", "numero", "competencia", "valor_medido", "status", "liquidacao")
    list_filter = ("status", "competencia")
    search_fields = ("contrato__numero", "numero", "competencia")
