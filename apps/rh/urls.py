from django.urls import path

from . import views
from . import views_workflows

app_name = "rh"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("servidores/", views.servidor_list, name="servidor_list"),
    path("servidores/novo/", views.servidor_create, name="servidor_create"),
    path("servidores/<int:pk>/editar/", views.servidor_update, name="servidor_update"),
    path("movimentacoes/", views.movimentacao_list, name="movimentacao_list"),
    path("movimentacoes/nova/", views.movimentacao_create, name="movimentacao_create"),
    path("movimentacoes/<int:pk>/aprovar/", views.movimentacao_aprovar, name="movimentacao_aprovar"),
    path("movimentacoes/<int:pk>/recusar/", views.movimentacao_recusar, name="movimentacao_recusar"),
    path("documentos/", views.documento_list, name="documento_list"),
    path("documentos/novo/", views.documento_create, name="documento_create"),
    path("remanejamento/", views_workflows.remanejamento_edital_list, name="remanejamento_edital_list"),
    path("remanejamento/novo/", views_workflows.remanejamento_edital_create, name="remanejamento_edital_create"),
    path("remanejamento/<int:pk>/", views_workflows.remanejamento_edital_detail, name="remanejamento_edital_detail"),
    path(
        "remanejamento/<int:edital_pk>/inscricoes/nova/",
        views_workflows.remanejamento_inscricao_create,
        name="remanejamento_inscricao_create",
    ),
    path(
        "remanejamento/inscricoes/<int:inscricao_pk>/cancelar/",
        views_workflows.remanejamento_inscricao_cancelar,
        name="remanejamento_inscricao_cancelar",
    ),
    path(
        "remanejamento/inscricoes/<int:inscricao_pk>/recurso/novo/",
        views_workflows.remanejamento_recurso_create,
        name="remanejamento_recurso_create",
    ),
    path(
        "remanejamento/recursos/<int:recurso_pk>/decidir/",
        views_workflows.remanejamento_recurso_decidir,
        name="remanejamento_recurso_decidir",
    ),
    path("substituicoes/", views_workflows.substituicao_list, name="substituicao_list"),
    path("substituicoes/nova/", views_workflows.substituicao_create, name="substituicao_create"),
    path("substituicoes/<int:pk>/", views_workflows.substituicao_detail, name="substituicao_detail"),
    path("substituicoes/<int:pk>/cancelar/", views_workflows.substituicao_cancelar, name="substituicao_cancelar"),
    path("pdp/", views_workflows.pdp_plano_list, name="pdp_plano_list"),
    path("pdp/novo/", views_workflows.pdp_plano_create, name="pdp_plano_create"),
    path("pdp/<int:pk>/", views_workflows.pdp_plano_detail, name="pdp_plano_detail"),
    path("pdp/<int:plano_pk>/necessidades/nova/", views_workflows.pdp_necessidade_create, name="pdp_necessidade_create"),
    path("pdp/necessidades/<int:pk>/status/", views_workflows.pdp_necessidade_status, name="pdp_necessidade_status"),
    path("pdp/<int:pk>/exportar-sipec/", views_workflows.pdp_plano_exportar_sipec, name="pdp_plano_exportar_sipec"),
]
