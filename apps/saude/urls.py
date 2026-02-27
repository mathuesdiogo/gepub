from django.urls import path
from . import views
from . import views_unidades
from . import views_profissionais
from . import views_atendimentos
from . import views_api
from . import views_relatorios
from . import views_agenda
from . import views_especialidades
from . import views_documentos
from . import views_prontuario
from . import views_regulacao
from . import views_expansao
from . import views_auditoria
from . import views_complementos

app_name = "saude"

urlpatterns = [
    path("", views.index, name="index"),

    path("unidades/", views_unidades.unidade_list, name="unidade_list"),
    path("unidades/nova/", views_unidades.unidade_create, name="unidade_create"),
    path("unidades/<int:pk>/", views_unidades.unidade_detail, name="unidade_detail"),
    path("unidades/<int:pk>/editar/", views_unidades.unidade_update, name="unidade_update"),

    path("profissionais/", views_profissionais.profissional_list, name="profissional_list"),
    path("profissionais/novo/", views_profissionais.profissional_create, name="profissional_create"),
    path("profissionais/<int:pk>/", views_profissionais.profissional_detail, name="profissional_detail"),
    path("profissionais/<int:pk>/editar/", views_profissionais.profissional_update, name="profissional_update"),

    path("especialidades/", views_especialidades.especialidade_list, name="especialidade_list"),
    path("especialidades/nova/", views_especialidades.especialidade_create, name="especialidade_create"),
    path("especialidades/<int:pk>/", views_especialidades.especialidade_detail, name="especialidade_detail"),
    path("especialidades/<int:pk>/editar/", views_especialidades.especialidade_update, name="especialidade_update"),

    path("agenda/", views_agenda.agenda_list, name="agenda_list"),
    path("agenda/nova/", views_agenda.agenda_create, name="agenda_create"),
    path("agenda/<int:pk>/", views_agenda.agenda_detail, name="agenda_detail"),
    path("agenda/<int:pk>/editar/", views_agenda.agenda_update, name="agenda_update"),
    path("agenda/grades/", views_regulacao.grade_list, name="grade_list"),
    path("agenda/grades/nova/", views_regulacao.grade_create, name="grade_create"),
    path("agenda/grades/<int:pk>/", views_regulacao.grade_detail, name="grade_detail"),
    path("agenda/grades/<int:pk>/editar/", views_regulacao.grade_update, name="grade_update"),
    path("agenda/bloqueios/", views_regulacao.bloqueio_list, name="bloqueio_list"),
    path("agenda/bloqueios/novo/", views_regulacao.bloqueio_create, name="bloqueio_create"),
    path("agenda/bloqueios/<int:pk>/", views_regulacao.bloqueio_detail, name="bloqueio_detail"),
    path("agenda/bloqueios/<int:pk>/editar/", views_regulacao.bloqueio_update, name="bloqueio_update"),
    path("agenda/fila-espera/", views_regulacao.fila_list, name="fila_list"),
    path("agenda/fila-espera/nova/", views_regulacao.fila_create, name="fila_create"),
    path("agenda/fila-espera/<int:pk>/", views_regulacao.fila_detail, name="fila_detail"),
    path("agenda/fila-espera/<int:pk>/editar/", views_regulacao.fila_update, name="fila_update"),

    path("atendimentos/", views_atendimentos.atendimento_list, name="atendimento_list"),
    path("atendimentos/novo/", views_atendimentos.atendimento_create, name="atendimento_create"),
    path("atendimentos/<int:pk>/", views_atendimentos.atendimento_detail, name="atendimento_detail"),
    path("atendimentos/<int:pk>/editar/", views_atendimentos.atendimento_update, name="atendimento_update"),
    path("atendimentos/<int:pk>/prontuario/", views_prontuario.prontuario_hub, name="prontuario_hub"),
    path("atendimentos/<int:atendimento_id>/documentos/", views_documentos.documento_list, name="documento_list"),
    path("atendimentos/<int:atendimento_id>/documentos/novo/", views_documentos.documento_create, name="documento_create"),
    path("documentos/<int:pk>/", views_documentos.documento_detail, name="documento_detail"),
    path("procedimentos/", views_expansao.procedimento_list, name="procedimento_list"),
    path("procedimentos/novo/", views_expansao.procedimento_create, name="procedimento_create"),
    path("procedimentos/<int:pk>/", views_expansao.procedimento_detail, name="procedimento_detail"),
    path("procedimentos/<int:pk>/editar/", views_expansao.procedimento_update, name="procedimento_update"),
    path("vacinacao/", views_expansao.vacinacao_list, name="vacinacao_list"),
    path("vacinacao/nova/", views_expansao.vacinacao_create, name="vacinacao_create"),
    path("vacinacao/<int:pk>/", views_expansao.vacinacao_detail, name="vacinacao_detail"),
    path("vacinacao/<int:pk>/editar/", views_expansao.vacinacao_update, name="vacinacao_update"),
    path("encaminhamentos/", views_expansao.encaminhamento_list, name="encaminhamento_list"),
    path("encaminhamentos/novo/", views_expansao.encaminhamento_create, name="encaminhamento_create"),
    path("encaminhamentos/<int:pk>/", views_expansao.encaminhamento_detail, name="encaminhamento_detail"),
    path("encaminhamentos/<int:pk>/editar/", views_expansao.encaminhamento_update, name="encaminhamento_update"),
    path("auditoria/prontuario/", views_auditoria.auditoria_prontuario_list, name="auditoria_prontuario_list"),
    path("cid/", views_complementos.cid_list, name="cid_list"),
    path("cid/novo/", views_complementos.cid_create, name="cid_create"),
    path("cid/<int:pk>/", views_complementos.cid_detail, name="cid_detail"),
    path("cid/<int:pk>/editar/", views_complementos.cid_update, name="cid_update"),
    path("programas/", views_complementos.programa_list, name="programa_list"),
    path("programas/novo/", views_complementos.programa_create, name="programa_create"),
    path("programas/<int:pk>/", views_complementos.programa_detail, name="programa_detail"),
    path("programas/<int:pk>/editar/", views_complementos.programa_update, name="programa_update"),
    path("pacientes/", views_complementos.paciente_list, name="paciente_list"),
    path("pacientes/novo/", views_complementos.paciente_create, name="paciente_create"),
    path("pacientes/<int:pk>/", views_complementos.paciente_detail, name="paciente_detail"),
    path("pacientes/<int:pk>/editar/", views_complementos.paciente_update, name="paciente_update"),
    path("checkins/", views_complementos.checkin_list, name="checkin_list"),
    path("checkins/novo/", views_complementos.checkin_create, name="checkin_create"),
    path("checkins/<int:pk>/", views_complementos.checkin_detail, name="checkin_detail"),
    path("checkins/<int:pk>/editar/", views_complementos.checkin_update, name="checkin_update"),
    path("medicamentos-uso/", views_complementos.medicamento_uso_list, name="medicamento_uso_list"),
    path("medicamentos-uso/novo/", views_complementos.medicamento_uso_create, name="medicamento_uso_create"),
    path("medicamentos-uso/<int:pk>/", views_complementos.medicamento_uso_detail, name="medicamento_uso_detail"),
    path("medicamentos-uso/<int:pk>/editar/", views_complementos.medicamento_uso_update, name="medicamento_uso_update"),
    path("dispensacoes/", views_complementos.dispensacao_list, name="dispensacao_list"),
    path("dispensacoes/nova/", views_complementos.dispensacao_create, name="dispensacao_create"),
    path("dispensacoes/<int:pk>/", views_complementos.dispensacao_detail, name="dispensacao_detail"),
    path("dispensacoes/<int:pk>/editar/", views_complementos.dispensacao_update, name="dispensacao_update"),
    path("exames/fluxo/", views_complementos.exame_coleta_list, name="exame_coleta_list"),
    path("exames/fluxo/novo/", views_complementos.exame_coleta_create, name="exame_coleta_create"),
    path("exames/fluxo/<int:pk>/", views_complementos.exame_coleta_detail, name="exame_coleta_detail"),
    path("exames/fluxo/<int:pk>/editar/", views_complementos.exame_coleta_update, name="exame_coleta_update"),
    path("internacoes/", views_complementos.internacao_list, name="internacao_list"),
    path("internacoes/nova/", views_complementos.internacao_create, name="internacao_create"),
    path("internacoes/<int:pk>/", views_complementos.internacao_detail, name="internacao_detail"),
    path("internacoes/<int:pk>/editar/", views_complementos.internacao_update, name="internacao_update"),

    # API (UX)
    path("api/profissionais-por-unidade/", views_api.api_profissionais_por_unidade, name="api_profissionais_por_unidade"),
    path("api/profissionais/suggest/", views_profissionais.api_profissionais_suggest, name="api_profissionais_suggest"),
    path("api/unidades/suggest/", views_unidades.api_unidades_suggest, name="api_unidades_suggest"),
    path("relatorios/mensal/", views_relatorios.relatorio_mensal, name="relatorio_mensal"),

]
