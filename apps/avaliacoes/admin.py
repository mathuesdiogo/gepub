from django.contrib import admin

from .models import AplicacaoAvaliacao, AvaliacaoProva, FolhaResposta, GabaritoProva, QuestaoProva


@admin.register(AvaliacaoProva)
class AvaliacaoProvaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "turma", "data_aplicacao", "tipo", "qtd_questoes", "municipio", "ativo")
    list_filter = ("tipo", "tem_versoes", "ativo", "municipio")
    search_fields = ("titulo", "disciplina", "turma__nome")


@admin.register(QuestaoProva)
class QuestaoProvaAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "numero", "tipo", "peso", "ativo")
    list_filter = ("tipo", "ativo")
    search_fields = ("avaliacao__titulo", "enunciado")


@admin.register(GabaritoProva)
class GabaritoProvaAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "versao", "atualizado_em", "integridade_ok")
    list_filter = ("versao",)
    search_fields = ("avaliacao__titulo",)


@admin.register(AplicacaoAvaliacao)
class AplicacaoAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "aluno", "versao", "status", "nota", "percentual")
    list_filter = ("status", "versao")
    search_fields = ("avaliacao__titulo", "aluno__nome")


@admin.register(FolhaResposta)
class FolhaRespostaAdmin(admin.ModelAdmin):
    list_display = ("aplicacao", "token", "versao", "integridade_ok", "atualizado_em")
    search_fields = ("token", "aplicacao__avaliacao__titulo", "aplicacao__aluno__nome")
