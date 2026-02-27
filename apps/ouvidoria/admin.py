from django.contrib import admin

from .models import OuvidoriaCadastro, OuvidoriaResposta, OuvidoriaTramitacao


@admin.register(OuvidoriaCadastro)
class OuvidoriaCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "protocolo", "assunto", "tipo", "prioridade", "status", "criado_em")
    list_filter = ("municipio", "status", "tipo", "prioridade")
    search_fields = ("protocolo", "assunto", "solicitante_nome")


@admin.register(OuvidoriaTramitacao)
class OuvidoriaTramitacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "chamado", "setor_origem", "setor_destino", "ciencia", "criado_em")
    list_filter = ("municipio", "ciencia")
    search_fields = ("chamado__protocolo", "despacho")


@admin.register(OuvidoriaResposta)
class OuvidoriaRespostaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "chamado", "publico", "criado_por", "criado_em")
    list_filter = ("municipio", "publico")
    search_fields = ("chamado__protocolo", "resposta")
