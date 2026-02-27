from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("", views.index, name="index"),
    path("exercicios/", views.exercicio_list, name="exercicio_list"),
    path("exercicios/novo/", views.exercicio_create, name="exercicio_create"),
    path("exercicios/<int:pk>/editar/", views.exercicio_update, name="exercicio_update"),

    path("unidades-gestoras/", views.ug_list, name="ug_list"),
    path("unidades-gestoras/nova/", views.ug_create, name="ug_create"),

    path("contas/", views.conta_list, name="conta_list"),
    path("contas/nova/", views.conta_create, name="conta_create"),

    path("conciliacao/extratos/", views.extrato_list, name="extrato_list"),
    path("conciliacao/extratos/novo/", views.extrato_create, name="extrato_create"),
    path("conciliacao/extratos/<int:pk>/", views.extrato_detail, name="extrato_detail"),
    path("conciliacao/extratos/<int:pk>/auto/", views.extrato_auto, name="extrato_auto"),
    path("conciliacao/itens/<int:item_pk>/ajuste/", views.extrato_ajuste, name="extrato_ajuste"),
    path("conciliacao/itens/<int:item_pk>/desfazer/", views.extrato_desfazer, name="extrato_desfazer"),

    path("fontes/", views.fonte_list, name="fonte_list"),
    path("fontes/nova/", views.fonte_create, name="fonte_create"),

    path("dotacoes/", views.dotacao_list, name="dotacao_list"),
    path("dotacoes/nova/", views.dotacao_create, name="dotacao_create"),

    path("creditos-adicionais/", views.credito_list, name="credito_list"),
    path("creditos-adicionais/novo/", views.credito_create, name="credito_create"),

    path("restos-a-pagar/", views.resto_list, name="resto_list"),
    path("restos-a-pagar/novo/", views.resto_create, name="resto_create"),
    path("restos-a-pagar/<int:pk>/", views.resto_detail, name="resto_detail"),
    path("restos-a-pagar/<int:resto_pk>/pagar/", views.resto_pagamento_create, name="resto_pagamento_create"),

    path("empenhos/", views.empenho_list, name="empenho_list"),
    path("empenhos/novo/", views.empenho_create, name="empenho_create"),
    path("empenhos/<int:pk>/", views.empenho_detail, name="empenho_detail"),
    path("empenhos/<int:empenho_pk>/liquidar/", views.liquidacao_create, name="liquidacao_create"),
    path("liquidacoes/<int:liquidacao_pk>/pagar/", views.pagamento_create, name="pagamento_create"),

    path("receitas/", views.receita_list, name="receita_list"),
    path("receitas/nova/", views.receita_create, name="receita_create"),

    path("logs/", views.log_list, name="log_list"),
]
