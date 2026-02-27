from django.contrib import admin

from .models import Chart, Dashboard, Dataset, DatasetColumn, DatasetVersion, ExportJob, QueryCache


class DatasetColumnInline(admin.TabularInline):
    model = DatasetColumn
    extra = 0


@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ("dataset", "numero", "fonte", "status", "criado_em", "processado_em")
    list_filter = ("fonte", "status", "criado_em")
    search_fields = ("dataset__nome", "logs")
    inlines = [DatasetColumnInline]


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "categoria", "status", "visibilidade", "criado_em")
    list_filter = ("municipio", "status", "visibilidade", "categoria")
    search_fields = ("nome", "descricao", "categoria")


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("nome", "dataset", "tema", "ativo", "atualizado_em")
    list_filter = ("tema", "ativo")
    search_fields = ("nome", "dataset__nome")


@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = ("titulo", "dashboard", "tipo", "ordem", "ativo")
    list_filter = ("tipo", "ativo")
    search_fields = ("titulo", "dashboard__nome")


@admin.register(QueryCache)
class QueryCacheAdmin(admin.ModelAdmin):
    list_display = ("dataset", "chave", "hits", "expira_em", "criado_em")
    list_filter = ("dataset",)
    search_fields = ("dataset__nome", "chave")


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("dataset", "formato", "status", "solicitado_por", "criado_em", "concluido_em")
    list_filter = ("formato", "status", "criado_em")
    search_fields = ("dataset__nome", "log")
