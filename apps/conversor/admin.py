from django.contrib import admin

from .models import ConversionJob, ConversionJobInput


class ConversionJobInputInline(admin.TabularInline):
    model = ConversionJobInput
    extra = 0


@admin.register(ConversionJob)
class ConversionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "municipio", "tipo", "status", "criado_por", "criado_em", "concluido_em")
    list_filter = ("tipo", "status", "municipio")
    search_fields = ("logs", "input_file", "output_file")
    inlines = [ConversionJobInputInline]


@admin.register(ConversionJobInput)
class ConversionJobInputAdmin(admin.ModelAdmin):
    list_display = ("job", "ordem", "arquivo")
    list_filter = ("job__tipo",)
