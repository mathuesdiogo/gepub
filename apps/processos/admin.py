from django.contrib import admin

from .models import ProcessoAdministrativo, ProcessoAndamento


class ProcessoAndamentoInline(admin.TabularInline):
    model = ProcessoAndamento
    extra = 0


@admin.register(ProcessoAdministrativo)
class ProcessoAdministrativoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "tipo", "assunto", "status", "data_abertura")
    list_filter = ("municipio", "status", "tipo")
    search_fields = ("numero", "assunto", "solicitante_nome")
    inlines = [ProcessoAndamentoInline]


@admin.register(ProcessoAndamento)
class ProcessoAndamentoAdmin(admin.ModelAdmin):
    list_display = ("processo", "tipo", "setor_origem", "setor_destino", "data_evento")
    list_filter = ("tipo", "data_evento")
    search_fields = ("processo__numero", "despacho")
