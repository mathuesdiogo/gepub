from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.models import AlunoArquivo, AlunoAviso
from apps.core.rbac import scope_filter_matriculas
from apps.core.services_auditoria import registrar_auditoria
from apps.nee.models import AcompanhamentoNEE, AlunoNecessidade, ApoioMatricula, PlanoClinicoNEE
from apps.ouvidoria.models import OuvidoriaCadastro, OuvidoriaResposta
from apps.processos.models import ProcessoAdministrativo
from apps.saude.models import AgendamentoSaude, AtendimentoSaude, PacienteSaude

from .models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    Matricula,
    RenovacaoMatricula,
    RenovacaoMatriculaOferta,
    RenovacaoMatriculaPedido,
    Turma,
)
from .models_beneficios import (
    BeneficioCampanhaAluno,
    BeneficioEdital,
    BeneficioEditalInscricao,
    BeneficioEntrega,
    BeneficioTipo,
)
from .models_biblioteca import BibliotecaEmprestimo
from .models_calendario import CalendarioEducacionalEvento
from .models_diario import Aula, Frequencia, JustificativaFaltaPedido, Nota
from .models_horarios import AulaHorario
from .models_informatica import (
    InformaticaAlertaFrequencia,
    InformaticaAulaDiario,
    InformaticaAvaliacao,
    InformaticaEncontroSemanal,
    InformaticaFrequencia,
    InformaticaMatricula,
    InformaticaNota,
    InformaticaTurma,
)
from .models_programas import ProgramaComplementarParticipacao
from .models_periodos import PeriodoLetivo
from .services_academico import classify_resultado
from .views_portal import _codigo_aluno_canonico, _resolve_aluno_by_codigo


def _nota_lancada_q(prefix: str = ""):
    return Q(**{f"{prefix}valor__isnull": False}) | ~Q(**{f"{prefix}conceito": ""})


class DocumentoSolicitacaoForm(forms.Form):
    TIPO_CHOICES = [
        ("DECLARACAO_MATRICULA", "Declaração de matrícula"),
        ("DECLARACAO_FREQUENCIA", "Declaração de frequência"),
        ("HISTORICO_ESCOLAR", "Histórico escolar"),
        ("COMPROVANTE_ESCOLAR", "Comprovante escolar"),
        ("CARTEIRA_ESTUDANTIL", "Carteira estudantil"),
        ("DOCUMENTO_PERSONALIZADO", "Documento personalizado"),
    ]

    tipo = forms.ChoiceField(choices=TIPO_CHOICES, label="Tipo de documento")
    descricao = forms.CharField(
        label="Observações",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Detalhes adicionais (opcional)"}),
    )


class ProcessoAlunoForm(forms.Form):
    TIPO_CHOICES = [
        ("TRANSFERENCIA", "Transferência"),
        ("REVISAO_NOTA", "Revisão de nota"),
        ("SOLICITACAO_ESPECIAL", "Solicitação especial"),
        ("BOLSA_BENEFICIO", "Bolsa ou benefício"),
    ]

    tipo = forms.ChoiceField(choices=TIPO_CHOICES, label="Tipo de processo")
    assunto = forms.CharField(label="Assunto", max_length=180)
    descricao = forms.CharField(label="Descrição", widget=forms.Textarea(attrs={"rows": 3}), required=True)


class AtualizarDadosAlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = ["telefone", "email", "endereco"]
        widgets = {
            "endereco": forms.Textarea(attrs={"rows": 2}),
        }


class _AulaFaltaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: Aula) -> str:
        turma_nome = getattr(getattr(getattr(obj, "diario", None), "turma", None), "nome", "Turma")
        professor_nome = getattr(getattr(obj.diario, "professor", None), "get_full_name", lambda: "")() or getattr(
            getattr(obj.diario, "professor", None),
            "username",
            "Professor",
        )
        componente = str(getattr(obj, "componente", None) or "Componente não informado")
        data = obj.data.strftime("%d/%m/%Y") if obj.data else "—"
        return f"{data} • {turma_nome} • {componente} • Prof. {professor_nome}"


class _TurmaCursoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: Turma) -> str:
        matriz_nome = getattr(getattr(obj, "matriz_curricular", None), "nome", "")
        serie_nome = obj.get_serie_ano_display() if hasattr(obj, "get_serie_ano_display") else ""
        atividade_nome = getattr(getattr(obj, "curso", None), "nome", "")
        if matriz_nome:
            label = f"{obj.nome} ({obj.ano_letivo}) • {serie_nome} • Matriz: {matriz_nome}"
        else:
            label = f"{obj.nome} ({obj.ano_letivo})"
        if atividade_nome:
            label += f" • Atividade extra: {atividade_nome}"
        return label


class JustificativaFaltaForm(forms.Form):
    turma = _TurmaCursoChoiceField(
        queryset=Turma.objects.none(),
        label="Turma",
        required=True,
        empty_label="Selecione a turma",
    )
    aula = _AulaFaltaChoiceField(
        queryset=Aula.objects.none(),
        label="Aula com falta lançada",
        required=True,
        empty_label="Selecione a aula",
    )
    motivo = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 3}), max_length=800)
    anexo = forms.FileField(label="Anexo (PDF/JPG/PNG)", required=False)

    def __init__(self, *args, aluno: Aluno, turma_ids: list[int], **kwargs):
        super().__init__(*args, **kwargs)
        turma_qs = Turma.objects.select_related("curso", "matriz_curricular").filter(id__in=turma_ids).order_by("-ano_letivo", "nome")
        self.fields["turma"].queryset = turma_qs

        selected_turma = None
        if self.is_bound:
            raw_turma = self.data.get(self.add_prefix("turma"))
            if raw_turma and str(raw_turma).isdigit():
                selected_turma = int(raw_turma)

        aulas_qs = (
            Aula.objects.select_related("diario", "diario__turma", "diario__professor", "componente")
            .filter(
                frequencias__aluno=aluno,
                frequencias__status=Frequencia.Status.FALTA,
                diario__turma_id__in=turma_ids,
            )
            .order_by("-data", "-id")
            .distinct()
        )
        if selected_turma:
            aulas_qs = aulas_qs.filter(diario__turma_id=selected_turma)
        self.fields["aula"].queryset = aulas_qs

    def clean(self):
        cleaned = super().clean()
        turma = cleaned.get("turma")
        aula = cleaned.get("aula")
        if turma and aula and aula.diario.turma_id != turma.id:
            self.add_error("aula", "A aula selecionada não pertence à turma informada.")
        return cleaned


class _InformaticaFrequenciaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: InformaticaFrequencia) -> str:
        turma_codigo = getattr(getattr(obj, "aula", None), "turma", None)
        turma_codigo = getattr(turma_codigo, "codigo", "Turma")
        encontro = getattr(getattr(obj, "aula", None), "encontro", None)
        faixa = "Horário não definido"
        if encontro and encontro.hora_inicio and encontro.hora_fim:
            faixa = f"{encontro.hora_inicio.strftime('%H:%M')}-{encontro.hora_fim.strftime('%H:%M')}"
        data = obj.aula.data_aula.strftime("%d/%m/%Y") if obj.aula and obj.aula.data_aula else "—"
        return f"{data} • {turma_codigo} • {faixa}"


class JustificativaFaltaInformaticaForm(forms.Form):
    frequencia = _InformaticaFrequenciaChoiceField(
        queryset=InformaticaFrequencia.objects.none(),
        label="Aula de Informática com falta",
        required=True,
        empty_label="Selecione a falta",
    )
    motivo = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 3}), max_length=800)

    def __init__(self, *args, aluno: Aluno, **kwargs):
        super().__init__(*args, **kwargs)
        faltas_qs = (
            InformaticaFrequencia.objects.select_related(
                "aula",
                "aula__turma",
                "aula__encontro",
            )
            .filter(
                aluno=aluno,
                presente=False,
                aula__turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
            )
            .order_by("-aula__data_aula", "-id")
        )
        self.fields["frequencia"].queryset = faltas_qs


class ApoioEstudantilForm(forms.Form):
    tipo = forms.ChoiceField(
        label="Tipo de apoio",
        choices=[
            ("REFORCO_ESCOLAR", "Reforço escolar"),
            ("ATENDIMENTO_PEDAGOGICO", "Atendimento pedagógico"),
            ("APOIO_PSICOLOGICO", "Apoio psicológico"),
            ("ATENDIMENTO_SOCIAL", "Atendimento social"),
        ],
    )
    descricao = forms.CharField(label="Descrição", widget=forms.Textarea(attrs={"rows": 3}), required=True)


class ChamadoAlunoForm(forms.Form):
    categoria = forms.ChoiceField(
        label="Categoria",
        choices=[
            ("SISTEMA", "Sistema"),
            ("DOCUMENTOS", "Documentos"),
            ("ACADEMICO", "Problemas acadêmicos"),
            ("ADMINISTRATIVO", "Problemas administrativos"),
        ],
    )
    assunto = forms.CharField(label="Assunto", max_length=180)
    descricao = forms.CharField(label="Descrição", widget=forms.Textarea(attrs={"rows": 3}), required=True)


class CadastroSolicitacaoForm(forms.Form):
    tipo = forms.ChoiceField(
        label="Solicitação cadastral",
        choices=[
            ("ATUALIZAR_DADOS", "Editar dados"),
            ("ATUALIZAR_ENDERECO", "Editar endereço"),
            ("ATUALIZAR_RESPONSAVEL", "Editar responsável"),
        ],
    )
    descricao = forms.CharField(label="Descrição", widget=forms.Textarea(attrs={"rows": 2}), required=True)


class RenovacaoPedidoAlunoForm(forms.Form):
    oferta_id = forms.IntegerField(required=True)
    prioridade = forms.IntegerField(required=True, min_value=1, max_value=6)
    observacao_aluno = forms.CharField(required=False, max_length=500)


def _apply_gp_form_classes(form):
    for field in form.fields.values():
        widget = field.widget
        current = (widget.attrs.get("class") or "").strip()
        if isinstance(widget, forms.Select):
            extra = "gp-select"
        elif isinstance(widget, forms.Textarea):
            extra = "gp-textarea"
        elif isinstance(widget, forms.CheckboxInput):
            extra = "gp-checkbox__input"
        else:
            extra = "gp-input"
        widget.attrs["class"] = f"{current} {extra}".strip()


def _matriculas_aluno(user, aluno: Aluno):
    qs = (
        Matricula.objects.select_related(
            "turma",
            "turma__curso",
            "turma__matriz_curricular",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno=aluno)
        .order_by("-turma__ano_letivo", "-id")
    )
    return list(scope_filter_matriculas(user, qs))


def _student_scope(matriculas):
    turma_ids = [m.turma_id for m in matriculas if m.turma_id]
    unidade_ids = [m.turma.unidade_id for m in matriculas if getattr(m.turma, "unidade_id", None)]
    secretaria_ids = [
        m.turma.unidade.secretaria_id
        for m in matriculas
        if getattr(getattr(m.turma, "unidade", None), "secretaria_id", None)
    ]
    municipio_ids = [
        m.turma.unidade.secretaria.municipio_id
        for m in matriculas
        if getattr(getattr(getattr(m.turma, "unidade", None), "secretaria", None), "municipio_id", None)
    ]
    return {
        "turma_ids": list(dict.fromkeys(turma_ids)),
        "unidade_ids": list(dict.fromkeys(unidade_ids)),
        "secretaria_ids": list(dict.fromkeys(secretaria_ids)),
        "municipio_ids": list(dict.fromkeys(municipio_ids)),
    }


def _resolve_contexto_aluno(request, codigo: str):
    aluno, profile_link = _resolve_aluno_by_codigo(request.user, codigo)
    matriculas = _matriculas_aluno(request.user, aluno)
    scope_ids = _student_scope(matriculas)

    matricula_ref = next((m for m in matriculas if m.situacao == Matricula.Situacao.ATIVA), None)
    if not matricula_ref and matriculas:
        matricula_ref = matriculas[0]

    unidade_ref = getattr(getattr(matricula_ref, "turma", None), "unidade", None)
    secretaria_ref = getattr(unidade_ref, "secretaria", None)
    municipio_ref = getattr(secretaria_ref, "municipio", None)

    code_value = (codigo or "").strip() or str(aluno.pk)
    codigo_canonico = _codigo_aluno_canonico(request.user, aluno)

    return {
        "aluno": aluno,
        "profile_link": profile_link,
        "matriculas": matriculas,
        "matricula_ref": matricula_ref,
        "unidade_ref": unidade_ref,
        "secretaria_ref": secretaria_ref,
        "municipio_ref": municipio_ref,
        "scope_ids": scope_ids,
        "code_value": code_value,
        "codigo_canonico": codigo_canonico,
    }


def _student_nav(codigo: str):
    return [
        {"key": "inicio", "label": "Início", "url": reverse("core:dashboard"), "icon": "fa-solid fa-house"},
        {
            "key": "documentos",
            "label": "Documentos / Processos",
            "url": reverse("educacao:aluno_documentos_processos", args=[codigo]),
            "icon": "fa-solid fa-folder-open",
        },
        {
            "key": "ensino",
            "label": "Ensino",
            "url": reverse("educacao:aluno_ensino", args=[codigo]),
            "icon": "fa-solid fa-graduation-cap",
        },
        {
            "key": "ensino_renovacao",
            "label": "Renovação de Matrícula",
            "url": reverse("educacao:aluno_ensino_renovacao", args=[codigo]),
            "icon": "fa-solid fa-arrows-rotate",
        },
        {
            "key": "pesquisa",
            "label": "Pesquisa",
            "url": reverse("educacao:aluno_pesquisa", args=[codigo]),
            "icon": "fa-solid fa-microscope",
        },
        {
            "key": "servicos",
            "label": "Central de Serviços",
            "url": reverse("educacao:aluno_central_servicos", args=[codigo]),
            "icon": "fa-solid fa-headset",
        },
        {
            "key": "atividades",
            "label": "Atividades Estudantis",
            "url": reverse("educacao:aluno_atividades", args=[codigo]),
            "icon": "fa-solid fa-calendar-days",
        },
        {
            "key": "saude",
            "label": "Saúde",
            "url": reverse("educacao:aluno_saude", args=[codigo]),
            "icon": "fa-solid fa-heart-pulse",
        },
        {
            "key": "comunicacao",
            "label": "Comunicação Social",
            "url": reverse("educacao:aluno_comunicacao", args=[codigo]),
            "icon": "fa-solid fa-bullhorn",
        },
    ]


def _base_context(ctx: dict, *, page_title: str, page_subtitle: str, nav_key: str):
    aluno = ctx["aluno"]
    codigo = ctx["codigo_canonico"]
    actions = [
        {
            "label": "Meu perfil",
            "url": reverse("accounts:meu_perfil"),
            "icon": "fa-solid fa-user",
            "variant": "gp-button--ghost",
        },
        {
            "label": "Histórico completo",
            "url": reverse("educacao:historico_aluno", args=[aluno.pk]),
            "icon": "fa-solid fa-scroll",
            "variant": "gp-button--ghost",
        },
    ]
    return {
        "aluno": aluno,
        "code_value": ctx["code_value"],
        "hide_module_menu": True,
        "student_nav": _student_nav(codigo),
        "student_nav_active": nav_key,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "actions": actions,
    }


def _next_numero_processo(municipio, prefix: str) -> str:
    hoje = timezone.localdate().strftime("%Y%m%d")
    base = f"{prefix}-{hoje}-"
    seq = ProcessoAdministrativo.objects.filter(municipio=municipio, numero__startswith=base).count() + 1
    numero = f"{base}{seq:04d}"
    while ProcessoAdministrativo.objects.filter(municipio=municipio, numero=numero).exists():
        seq += 1
        numero = f"{base}{seq:04d}"
    return numero


def _next_protocolo_ouvidoria(municipio) -> str:
    hoje = timezone.localdate().strftime("%Y%m%d")
    base = f"ALN-{hoje}-"
    seq = OuvidoriaCadastro.objects.filter(municipio=municipio, protocolo__startswith=base).count() + 1
    protocolo = f"{base}{seq:04d}"
    while OuvidoriaCadastro.objects.filter(municipio=municipio, protocolo=protocolo).exists():
        seq += 1
        protocolo = f"{base}{seq:04d}"
    return protocolo


def _create_processo_aluno(
    *,
    request,
    ctx: dict,
    tipo: str,
    assunto: str,
    descricao: str,
):
    municipio = ctx["municipio_ref"]
    if municipio is None:
        messages.error(request, "Não foi possível identificar o município do aluno para iniciar o processo.")
        return None

    numero = _next_numero_processo(municipio, "ALUNO")
    processo = ProcessoAdministrativo.objects.create(
        municipio=municipio,
        secretaria=ctx["secretaria_ref"],
        unidade=ctx["unidade_ref"],
        numero=numero,
        tipo=tipo,
        assunto=assunto,
        solicitante_nome=ctx["aluno"].nome,
        descricao=descricao,
        status=ProcessoAdministrativo.Status.ABERTO,
        data_abertura=timezone.localdate(),
        criado_por=request.user,
    )
    registrar_auditoria(
        municipio=municipio,
        modulo="EDUCACAO",
        evento="PROCESSO_ALUNO_CRIADO",
        entidade="ProcessoAdministrativo",
        entidade_id=processo.pk,
        usuario=request.user if getattr(request.user, "is_authenticated", False) else None,
        depois={
            "numero": processo.numero,
            "tipo": processo.tipo,
            "status": processo.status,
            "assunto": processo.assunto,
            "solicitante": processo.solicitante_nome,
        },
        observacao="Processo aberto via Área do Aluno.",
    )
    return processo


def _status_publico_processo(status: str) -> str:
    mapping = {
        ProcessoAdministrativo.Status.ABERTO: "Em análise",
        ProcessoAdministrativo.Status.EM_TRAMITACAO: "Em análise",
        ProcessoAdministrativo.Status.CONCLUIDO: "Aprovado",
        ProcessoAdministrativo.Status.ARQUIVADO: "Reprovado",
    }
    return mapping.get(status, status or "Em análise")


def _status_publico_justificativa(status: str) -> str:
    mapping = {
        JustificativaFaltaPedido.Status.PENDENTE: "Em análise",
        JustificativaFaltaPedido.Status.DEFERIDO: "Deferida",
        JustificativaFaltaPedido.Status.INDEFERIDO: "Indeferida",
    }
    return mapping.get(status, status or "Em análise")


def _scoped_avisos_aluno(ctx: dict):
    scope = ctx["scope_ids"]
    aluno = ctx["aluno"]
    return (
        AlunoAviso.objects.filter(ativo=True)
        .filter(
            Q(aluno_id=aluno.pk)
            | Q(turma_id__in=scope["turma_ids"])
            | Q(unidade_id__in=scope["unidade_ids"])
            | Q(secretaria_id__in=scope["secretaria_ids"])
            | Q(municipio_id__in=scope["municipio_ids"])
        )
        .select_related("autor")
        .order_by("-criado_em")
    )


def _scoped_arquivos_aluno(ctx: dict):
    scope = ctx["scope_ids"]
    aluno = ctx["aluno"]
    return (
        AlunoArquivo.objects.filter(ativo=True)
        .filter(
            Q(aluno_id=aluno.pk)
            | Q(turma_id__in=scope["turma_ids"])
            | Q(unidade_id__in=scope["unidade_ids"])
            | Q(secretaria_id__in=scope["secretaria_ids"])
            | Q(municipio_id__in=scope["municipio_ids"])
        )
        .select_related("autor")
        .order_by("-criado_em")
    )


def _student_informatica_context(aluno: Aluno):
    hoje = timezone.localdate()
    matriculas = list(
        InformaticaMatricula.objects.select_related(
            "turma",
            "turma__curso",
            "turma__laboratorio",
            "turma__laboratorio__unidade",
        )
        .filter(
            aluno=aluno,
            status=InformaticaMatricula.Status.MATRICULADO,
            turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
        )
        .order_by("-id")
    )
    turma_ids = [m.turma_id for m in matriculas if m.turma_id]
    if not turma_ids:
        return {
            "matriculas": [],
            "turma_ids": [],
            "proximas_aulas": [],
            "faltas_em_aberto": 0,
            "faltas_justificadas": 0,
            "alertas_ativos": 0,
            "encontros_semanais": [],
        }

    proximas_aulas = list(
        InformaticaAulaDiario.objects.select_related("turma", "encontro")
        .filter(
            turma_id__in=turma_ids,
            data_aula__gte=hoje,
        )
        .exclude(status=InformaticaAulaDiario.Status.CANCELADA)
        .order_by("data_aula", "encontro__hora_inicio", "id")[:24]
    )
    faltas_qs = InformaticaFrequencia.objects.filter(
        aluno=aluno,
        aula__turma_id__in=turma_ids,
        presente=False,
    )
    faltas_em_aberto = faltas_qs.filter(Q(justificativa__isnull=True) | Q(justificativa="")).count()
    faltas_justificadas = faltas_qs.exclude(Q(justificativa__isnull=True) | Q(justificativa="")).count()
    alertas_ativos = InformaticaAlertaFrequencia.objects.filter(
        ativo=True,
        matricula__aluno=aluno,
        matricula__status=InformaticaMatricula.Status.MATRICULADO,
        matricula__turma_id__in=turma_ids,
    ).count()

    encontros_semanais = list(
        InformaticaEncontroSemanal.objects.select_related("turma")
        .filter(
            turma_id__in=turma_ids,
            ativo=True,
            turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
        )
        .order_by("dia_semana", "hora_inicio", "turma__codigo")
    )
    return {
        "matriculas": matriculas,
        "turma_ids": turma_ids,
        "proximas_aulas": proximas_aulas,
        "faltas_em_aberto": faltas_em_aberto,
        "faltas_justificadas": faltas_justificadas,
        "alertas_ativos": alertas_ativos,
        "encontros_semanais": encontros_semanais,
    }


@login_required
@require_perm("educacao.view")
def aluno_documentos_processos(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)

    doc_form = DocumentoSolicitacaoForm(request.POST or None, prefix="doc")
    proc_form = ProcessoAlunoForm(request.POST or None, prefix="proc")
    _apply_gp_form_classes(doc_form)
    _apply_gp_form_classes(proc_form)

    if request.method == "POST":
        form_kind = (request.POST.get("form_kind") or "").strip()
        if form_kind == "documento" and doc_form.is_valid():
            tipo_value = doc_form.cleaned_data["tipo"]
            tipo_label = dict(DocumentoSolicitacaoForm.TIPO_CHOICES).get(tipo_value, tipo_value)
            descricao = (doc_form.cleaned_data.get("descricao") or "").strip()
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo=f"DOCUMENTO - {tipo_label}",
                assunto=f"Solicitação de {tipo_label}",
                descricao=descricao or "Solicitação registrada pelo portal do aluno.",
            )
            messages.success(request, "Solicitação de documento registrada e enviada para análise da escola.")
            return redirect(reverse("educacao:aluno_documentos_processos", args=[ctx["codigo_canonico"]]))

        if form_kind == "processo" and proc_form.is_valid():
            tipo_value = proc_form.cleaned_data["tipo"]
            tipo_label = dict(ProcessoAlunoForm.TIPO_CHOICES).get(tipo_value, tipo_value)
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo=f"PROCESSO ALUNO - {tipo_label}",
                assunto=proc_form.cleaned_data["assunto"],
                descricao=proc_form.cleaned_data["descricao"],
            )
            messages.success(request, "Processo aberto com sucesso.")
            return redirect(reverse("educacao:aluno_documentos_processos", args=[ctx["codigo_canonico"]]))

    aluno = ctx["aluno"]
    processos_qs = ProcessoAdministrativo.objects.none()
    if ctx["municipio_ref"] is not None:
        processos_qs = (
            ProcessoAdministrativo.objects.filter(municipio=ctx["municipio_ref"])
            .filter(Q(criado_por=request.user) | Q(solicitante_nome__iexact=aluno.nome))
            .order_by("-criado_em", "-id")
        )

    documentos_processos = list(processos_qs.filter(tipo__istartswith="DOCUMENTO -")[:20])
    processos_aluno = list(processos_qs.exclude(tipo__istartswith="DOCUMENTO -")[:30])
    for p in documentos_processos:
        p.status_publico = _status_publico_processo(p.status)
    for p in processos_aluno:
        p.status_publico = _status_publico_processo(p.status)

    documentos_gerados = list(
        AlunoDocumento.objects.filter(aluno=aluno, ativo=True)
        .select_related("enviado_por")
        .order_by("-criado_em", "-id")[:20]
    )
    certificados = list(
        AlunoCertificado.objects.filter(aluno=aluno, ativo=True)
        .select_related("emitido_por")
        .order_by("-data_emissao", "-id")[:20]
    )

    links_rapidos = [
        {
            "titulo": "Declaração de matrícula/frequência",
            "url": reverse("educacao:declaracao_vinculo_pdf", args=[aluno.pk]),
        },
        {
            "titulo": "Histórico escolar (PDF)",
            "url": reverse("educacao:historico_aluno", args=[aluno.pk]) + "?export=pdf",
        },
        {
            "titulo": "Carteira estudantil",
            "url": reverse("educacao:carteira_emitir_pdf", args=[aluno.pk]),
        },
    ]

    context = {
        **_base_context(
            ctx,
            page_title="Documentos e Processos",
            page_subtitle="Solicite documentos, acompanhe status e baixe arquivos oficiais.",
            nav_key="documentos",
        ),
        "doc_form": doc_form,
        "proc_form": proc_form,
        "documentos_processos": documentos_processos,
        "processos_aluno": processos_aluno,
        "documentos_gerados": documentos_gerados,
        "certificados": certificados,
        "links_rapidos": links_rapidos,
    }
    return render(request, "educacao/aluno_area/documentos_processos.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino(request, codigo: str):
    return aluno_ensino_dados(request, codigo)


def _ensino_page_base_context(ctx: dict, *, subtitle: str):
    context = _base_context(
        ctx,
        page_title="Ensino",
        page_subtitle=subtitle,
        nav_key="ensino",
    )
    actions = list(context.get("actions", []))
    actions.append(
        {
            "label": "Programas Complementares",
            "url": reverse("educacao:aluno_ensino_programas", args=[ctx["codigo_canonico"]]),
            "icon": "fa-solid fa-shapes",
            "variant": "gp-button--outline",
        }
    )
    context["actions"] = actions
    return context


@login_required
@require_perm("educacao.view")
def aluno_ensino_renovacao(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    hoje = timezone.localdate()

    secretaria_ids = {
        getattr(getattr(getattr(m, "turma", None), "unidade", None), "secretaria_id", None)
        for m in ctx["matriculas"]
        if getattr(getattr(getattr(m, "turma", None), "unidade", None), "secretaria_id", None)
    }
    secretaria_ids = {sid for sid in secretaria_ids if sid is not None}

    renovacoes_abertas = list(
        RenovacaoMatricula.objects.select_related("secretaria", "periodo_letivo")
        .prefetch_related(
            "ofertas",
            "ofertas__turma",
            "ofertas__turma__unidade",
        )
        .filter(
            secretaria_id__in=secretaria_ids,
            ativo=True,
            processado_em__isnull=True,
            data_inicio__lte=hoje,
            data_fim__gte=hoje,
        )
        .order_by("data_fim", "id")
    )
    renovacoes_map = {r.id: r for r in renovacoes_abertas}

    if request.method == "POST":
        form_kind = (request.POST.get("form_kind") or "").strip()

        if form_kind == "pedido_renovacao":
            pedido_form = RenovacaoPedidoAlunoForm(request.POST)
            renovacao_id_raw = (request.POST.get("renovacao_id") or "").strip()

            if not renovacao_id_raw.isdigit() or int(renovacao_id_raw) not in renovacoes_map:
                messages.error(request, "Renovação inválida ou fora da janela de matrícula.")
                return redirect(reverse("educacao:aluno_ensino_renovacao", args=[ctx["codigo_canonico"]]))

            renovacao = renovacoes_map[int(renovacao_id_raw)]
            if not pedido_form.is_valid():
                messages.error(request, "Corrija os dados do pedido para continuar.")
                return redirect(reverse("educacao:aluno_ensino_renovacao", args=[ctx["codigo_canonico"]]))

            oferta_id = pedido_form.cleaned_data["oferta_id"]
            oferta = RenovacaoMatriculaOferta.objects.select_related("turma").filter(
                renovacao=renovacao,
                ativo=True,
                pk=oferta_id,
            ).first()
            if not oferta:
                messages.error(request, "Oferta selecionada não está disponível para esta renovação.")
                return redirect(reverse("educacao:aluno_ensino_renovacao", args=[ctx["codigo_canonico"]]))

            origem_matricula = (
                Matricula.objects.filter(
                    aluno=aluno,
                    turma__ano_letivo=renovacao.ano_letivo,
                )
                .order_by("-id")
                .first()
            )

            pedido, created = RenovacaoMatriculaPedido.objects.get_or_create(
                renovacao=renovacao,
                aluno=aluno,
                oferta=oferta,
                defaults={
                    "prioridade": pedido_form.cleaned_data["prioridade"],
                    "observacao_aluno": pedido_form.cleaned_data.get("observacao_aluno") or "",
                    "origem_matricula": origem_matricula,
                },
            )
            if not created:
                pedido.prioridade = pedido_form.cleaned_data["prioridade"]
                pedido.observacao_aluno = pedido_form.cleaned_data.get("observacao_aluno") or ""
                pedido.origem_matricula = origem_matricula
                pedido.status = RenovacaoMatriculaPedido.Status.PENDENTE
                pedido.processado_em = None
                pedido.processado_por = None
                pedido.observacao_processamento = ""
                pedido.matricula_resultante = None
                pedido.save(
                    update_fields=[
                        "prioridade",
                        "observacao_aluno",
                        "origem_matricula",
                        "status",
                        "processado_em",
                        "processado_por",
                        "observacao_processamento",
                        "matricula_resultante",
                        "atualizado_em",
                    ]
                )
            processo = pedido.processo_administrativo
            if processo is None:
                processo = _create_processo_aluno(
                    request=request,
                    ctx=ctx,
                    tipo="RENOVACAO_MATRICULA",
                    assunto=f"Renovação de matrícula • {renovacao.descricao}",
                    descricao=(
                        f"Pedido de renovação para turma {oferta.turma.nome} "
                        f"(prioridade {pedido.prioridade}). "
                        f"{(pedido.observacao_aluno or '').strip()}"
                    ).strip(),
                )
                if processo is not None:
                    pedido.processo_administrativo = processo
                    pedido.save(update_fields=["processo_administrativo", "atualizado_em"])
            elif processo.status in {
                ProcessoAdministrativo.Status.CONCLUIDO,
                ProcessoAdministrativo.Status.ARQUIVADO,
            }:
                processo.status = ProcessoAdministrativo.Status.ABERTO
                processo.save(update_fields=["status", "atualizado_em"])

            municipio_ref = ctx.get("municipio_ref")
            if municipio_ref is not None:
                registrar_auditoria(
                    municipio=municipio_ref,
                    modulo="EDUCACAO",
                    evento="RENOVACAO_PEDIDO_ATUALIZADO" if not created else "RENOVACAO_PEDIDO_CRIADO",
                    entidade="RenovacaoMatriculaPedido",
                    entidade_id=pedido.pk,
                    usuario=request.user if getattr(request.user, "is_authenticated", False) else None,
                    depois={
                        "renovacao_id": renovacao.id,
                        "aluno_id": aluno.id,
                        "oferta_id": oferta.id,
                        "prioridade": pedido.prioridade,
                        "status": pedido.status,
                        "processo_id": pedido.processo_administrativo_id,
                    },
                    observacao="Pedido submetido pela Área do Aluno.",
                )
            messages.success(request, "Pedido de renovação registrado com sucesso.")
            return redirect(reverse("educacao:aluno_ensino_renovacao", args=[ctx["codigo_canonico"]]))

        if form_kind == "cancelar_pedido_renovacao":
            pedido_id = (request.POST.get("pedido_id") or "").strip()
            if pedido_id.isdigit():
                pedido = RenovacaoMatriculaPedido.objects.filter(
                    pk=int(pedido_id),
                    aluno=aluno,
                    status=RenovacaoMatriculaPedido.Status.PENDENTE,
                    renovacao__processado_em__isnull=True,
                    renovacao__data_inicio__lte=hoje,
                    renovacao__data_fim__gte=hoje,
                ).first()
                if pedido:
                    if pedido.processo_administrativo_id:
                        processo = pedido.processo_administrativo
                        if processo.status != ProcessoAdministrativo.Status.ARQUIVADO:
                            processo.status = ProcessoAdministrativo.Status.ARQUIVADO
                            processo.save(update_fields=["status", "atualizado_em"])
                    municipio_ref = ctx.get("municipio_ref")
                    if municipio_ref is not None:
                        registrar_auditoria(
                            municipio=municipio_ref,
                            modulo="EDUCACAO",
                            evento="RENOVACAO_PEDIDO_CANCELADO",
                            entidade="RenovacaoMatriculaPedido",
                            entidade_id=pedido.pk,
                            usuario=request.user if getattr(request.user, "is_authenticated", False) else None,
                            antes={
                                "status": pedido.status,
                                "processo_id": pedido.processo_administrativo_id,
                            },
                            observacao="Pedido pendente cancelado pelo aluno.",
                        )
                    pedido.delete()
                    messages.success(request, "Pedido pendente removido.")
            return redirect(reverse("educacao:aluno_ensino_renovacao", args=[ctx["codigo_canonico"]]))

    pedidos = list(
        RenovacaoMatriculaPedido.objects.select_related(
            "renovacao",
            "oferta",
            "oferta__turma",
            "processado_por",
            "matricula_resultante",
        )
        .filter(aluno=aluno, renovacao_id__in=[r.id for r in renovacoes_abertas])
        .order_by("renovacao__data_fim", "prioridade", "id")
    )
    pedidos_por_renovacao: dict[int, list[RenovacaoMatriculaPedido]] = {}
    for pedido in pedidos:
        pedidos_por_renovacao.setdefault(pedido.renovacao_id, []).append(pedido)

    for renovacao in renovacoes_abertas:
        renovacao.ofertas_ativas = [of for of in renovacao.ofertas.all() if of.ativo]
        renovacao.meus_pedidos = pedidos_por_renovacao.get(renovacao.id, [])

    context = {
        **_base_context(
            ctx,
            page_title="Ensino",
            page_subtitle="Escolha suas turmas de preferência durante a janela de renovação e acompanhe o processamento.",
            nav_key="ensino_renovacao",
        ),
        "renovacoes_abertas": renovacoes_abertas,
    }
    return render(request, "educacao/aluno_area/ensino_renovacao.html", context)


def _resolver_periodo_referencia_ensino(ctx: dict, request):
    matriculas = ctx["matriculas"]
    anos_letivos = sorted(
        {
            m.turma.ano_letivo
            for m in matriculas
            if getattr(getattr(m, "turma", None), "ano_letivo", None) is not None
        },
        reverse=True,
    )
    periodos_disponiveis = list(
        PeriodoLetivo.objects.filter(ativo=True, ano_letivo__in=anos_letivos).order_by("-ano_letivo", "-inicio", "-numero", "-id")
    )

    periodos_map = {p.pk: p for p in periodos_disponiveis}
    periodo_ref = None
    periodo_param = (request.GET.get("periodo") or "").strip()
    if periodo_param.isdigit():
        periodo_ref = periodos_map.get(int(periodo_param))

    today = timezone.localdate()
    if periodo_ref is None and periodos_disponiveis:
        ano_ref = getattr(getattr(ctx["matricula_ref"], "turma", None), "ano_letivo", None)
        periodos_ano_ref = [p for p in periodos_disponiveis if ano_ref is not None and p.ano_letivo == ano_ref]

        periodo_em_andamento = next((p for p in periodos_ano_ref if p.inicio <= today <= p.fim), None)
        if periodo_em_andamento:
            periodo_ref = periodo_em_andamento
        elif periodos_ano_ref:
            periodos_ano_ref.sort(key=lambda p: p.numero)
            periodo_ref = periodos_ano_ref[0]
        else:
            periodo_ref = periodos_disponiveis[0]

    periodo_ref_label = "Não definido"
    if periodo_ref is not None:
        periodo_ref_label = f"{periodo_ref.ano_letivo}/{periodo_ref.numero}"

    return periodos_disponiveis, periodo_ref, periodo_ref_label, anos_letivos


def _filtrar_notas_por_periodo(*, aluno: Aluno, turma_ids: list[int], periodo_ref: PeriodoLetivo | None, anos_letivos: list[int]):
    notas_qs = Nota.objects.select_related(
        "avaliacao",
        "avaliacao__diario",
        "avaliacao__diario__turma",
        "avaliacao__periodo",
    ).filter(
        aluno=aluno,
        avaliacao__diario__turma_id__in=turma_ids,
    )

    if periodo_ref is not None:
        notas_qs = notas_qs.filter(
            Q(avaliacao__periodo=periodo_ref)
            | Q(
                avaliacao__periodo__isnull=True,
                avaliacao__data__gte=periodo_ref.inicio,
                avaliacao__data__lte=periodo_ref.fim,
            )
        )
    elif anos_letivos:
        notas_qs = notas_qs.filter(avaliacao__diario__ano_letivo=anos_letivos[0])
    return notas_qs


def _ensino_editais_e_inscricoes(ctx: dict, aluno: Aluno):
    editais_educacao = []
    inscricoes_map = {}
    if ctx["municipio_ref"] is not None:
        editais_educacao = list(
            BeneficioEdital.objects.select_related("beneficio")
            .filter(
                municipio=ctx["municipio_ref"],
                area=BeneficioTipo.Area.EDUCACAO,
                status__in=[
                    BeneficioEdital.Status.PUBLICADO,
                    BeneficioEdital.Status.INSCRICOES_ENCERRADAS,
                    BeneficioEdital.Status.EM_ANALISE,
                    BeneficioEdital.Status.RESULTADO_PRELIMINAR,
                    BeneficioEdital.Status.RESULTADO_FINAL,
                ],
            )
            .order_by("-criado_em", "-id")[:20]
        )
        inscricoes_map = {
            i.edital_id: i
            for i in BeneficioEditalInscricao.objects.filter(aluno=aluno, edital_id__in=[e.pk for e in editais_educacao])
        }
    return editais_educacao, inscricoes_map


@login_required
@require_perm("educacao.view")
def aluno_ensino_dados(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    return redirect(reverse("educacao:aluno_meus_dados", args=[ctx["codigo_canonico"]]))


@login_required
@require_perm("educacao.view")
def aluno_ensino_justificativa(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    turma_ids = ctx["scope_ids"]["turma_ids"]
    informatica_ctx = _student_informatica_context(aluno)
    form_kind = (request.POST.get("form_kind") or "").strip() if request.method == "POST" else ""
    initial_turma = getattr(getattr(ctx.get("matricula_ref"), "turma", None), "id", None)
    falta_form = JustificativaFaltaForm(
        request.POST if form_kind == "justificativa" else None,
        request.FILES or None,
        prefix="falta",
        aluno=aluno,
        turma_ids=turma_ids,
        initial={"turma": initial_turma} if initial_turma else None,
    )
    falta_info_form = JustificativaFaltaInformaticaForm(
        request.POST if form_kind == "justificativa_informatica" else None,
        prefix="falta_info",
        aluno=aluno,
    )
    _apply_gp_form_classes(falta_form)
    _apply_gp_form_classes(falta_info_form)

    if request.method == "POST":
        if form_kind == "justificativa" and falta_form.is_valid():
            aula = falta_form.cleaned_data["aula"]
            motivo = falta_form.cleaned_data["motivo"]
            anexo = falta_form.cleaned_data.get("anexo")
            pedido, created = JustificativaFaltaPedido.objects.get_or_create(
                aula=aula,
                aluno=aluno,
                defaults={
                    "motivo": motivo,
                    "anexo": anexo,
                },
            )

            if not created:
                if pedido.status == JustificativaFaltaPedido.Status.DEFERIDO:
                    messages.info(request, "Esta falta já foi deferida e registrada como justificada.")
                    return redirect(reverse("educacao:aluno_ensino_justificativa", args=[ctx["codigo_canonico"]]))

                pedido.motivo = motivo
                if anexo:
                    pedido.anexo = anexo
                pedido.status = JustificativaFaltaPedido.Status.PENDENTE
                pedido.parecer = ""
                pedido.analisado_em = None
                pedido.analisado_por = None
                pedido.save(
                    update_fields=[
                        "motivo",
                        "anexo",
                        "status",
                        "parecer",
                        "analisado_em",
                        "analisado_por",
                        "atualizado_em",
                    ]
                )
                messages.success(request, "Pedido de justificativa atualizado e reenviado para análise.")
            else:
                messages.success(request, "Justificativa registrada e encaminhada para análise do professor.")

            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo="JUSTIFICATIVA DE FALTA",
                assunto=f"Solicitação de justificativa: {aula.data.strftime('%d/%m/%Y') if aula.data else 'aula'}",
                descricao=motivo,
            )
            return redirect(reverse("educacao:aluno_ensino_justificativa", args=[ctx["codigo_canonico"]]))

        if form_kind == "justificativa_informatica" and falta_info_form.is_valid():
            freq = falta_info_form.cleaned_data["frequencia"]
            motivo = (falta_info_form.cleaned_data.get("motivo") or "").strip()
            observacao_atual = (freq.observacao or "").strip()
            nota_aluno = f"Justificativa enviada pelo aluno em {timezone.localdate().strftime('%d/%m/%Y')}."
            freq.justificativa = motivo[:220]
            freq.observacao = f"{observacao_atual}\n{nota_aluno}".strip()
            freq.save(update_fields=["justificativa", "observacao"])
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo="JUSTIFICATIVA DE FALTA - INFORMÁTICA",
                assunto=(
                    f"Justificativa de falta (Informática) - "
                    f"{freq.aula.data_aula.strftime('%d/%m/%Y') if freq.aula and freq.aula.data_aula else 'aula'}"
                ),
                descricao=motivo,
            )
            messages.success(request, "Justificativa de falta da Informática enviada com sucesso.")
            return redirect(reverse("educacao:aluno_ensino_justificativa", args=[ctx["codigo_canonico"]]))

    pedidos = list(
        JustificativaFaltaPedido.objects.select_related(
            "aula",
            "aula__diario",
            "aula__diario__turma",
            "aula__diario__professor",
            "aula__componente",
            "analisado_por",
        )
        .filter(aluno=aluno)
        .order_by("-criado_em", "-id")[:80]
    )
    for p in pedidos:
        p.status_publico = _status_publico_justificativa(p.status)

    faltas_em_aberto = (
        Frequencia.objects.filter(
            aluno=aluno,
            status=Frequencia.Status.FALTA,
            aula__diario__turma_id__in=turma_ids,
        )
        .values("aula_id")
        .distinct()
        .count()
    )
    pedidos_informatica = list(
        InformaticaFrequencia.objects.select_related(
            "aula",
            "aula__turma",
            "aula__encontro",
        )
        .filter(
            aluno=aluno,
            aula__turma_id__in=informatica_ctx["turma_ids"],
            presente=False,
        )
        .order_by("-aula__data_aula", "-id")[:80]
    )
    for freq in pedidos_informatica:
        if freq.justificativa:
            freq.status_publico = "Justificativa enviada"
        else:
            freq.status_publico = "Pendente de justificativa"

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Selecione turma e aula com falta lançada, envie justificativa e acompanhe a decisão do professor.",
        ),
        "falta_form": falta_form,
        "falta_info_form": falta_info_form,
        "pedidos": pedidos,
        "faltas_em_aberto": faltas_em_aberto,
        "pedidos_informatica": pedidos_informatica,
        "faltas_informatica_em_aberto": informatica_ctx["faltas_em_aberto"],
        "faltas_informatica_justificadas": informatica_ctx["faltas_justificadas"],
    }
    return render(request, "educacao/aluno_area/ensino_justificativa.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_boletins(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    turma_ids = ctx["scope_ids"]["turma_ids"]
    matriculas = ctx["matriculas"]
    informatica_ctx = _student_informatica_context(aluno)
    periodos_disponiveis, periodo_ref, periodo_ref_label, anos_letivos = _resolver_periodo_referencia_ensino(ctx, request)
    notas_qs = _filtrar_notas_por_periodo(
        aluno=aluno,
        turma_ids=turma_ids,
        periodo_ref=periodo_ref,
        anos_letivos=anos_letivos,
    )
    notas_lancadas_qs = notas_qs.filter(_nota_lancada_q())
    media_periodo = notas_lancadas_qs.aggregate(media=Avg("valor")).get("media")
    notas_total = notas_qs.count()
    notas_lancadas_total = notas_lancadas_qs.count()

    ano_ref = periodo_ref.ano_letivo if periodo_ref is not None else (anos_letivos[0] if anos_letivos else None)
    matriculas_ano = [m for m in matriculas if ano_ref is None or m.turma.ano_letivo == ano_ref]
    turmas_ref: dict[int, Turma] = {}
    for m in matriculas_ano:
        if m.turma_id and m.turma_id not in turmas_ref:
            turmas_ref[m.turma_id] = m.turma

    rows_boletim = []
    for turma in turmas_ref.values():
        notas_turma_qs = notas_qs.filter(avaliacao__diario__turma_id=turma.id)
        notas_turma_lancadas_qs = notas_turma_qs.filter(_nota_lancada_q())
        media_turma = notas_turma_lancadas_qs.aggregate(media=Avg("valor")).get("media")
        avaliacoes_turma_total = notas_turma_qs.values("avaliacao_id").distinct().count()
        notas_turma_lancadas = notas_turma_lancadas_qs.count()

        aulas_qs = Aula.objects.filter(diario__turma_id=turma.id)
        if periodo_ref is not None:
            aulas_qs = aulas_qs.filter(
                Q(periodo=periodo_ref)
                | Q(periodo__isnull=True, data__gte=periodo_ref.inicio, data__lte=periodo_ref.fim)
            )
        elif ano_ref:
            aulas_qs = aulas_qs.filter(data__year=ano_ref)

        total_aulas = aulas_qs.values("id").distinct().count()
        freq_pct = None
        if total_aulas:
            presencas = Frequencia.objects.filter(
                aluno=aluno,
                aula__in=aulas_qs,
                status__in=[Frequencia.Status.PRESENTE, Frequencia.Status.JUSTIFICADA],
            ).count()
            freq_pct = round((presencas / total_aulas) * 100, 1)

        situacao = classify_resultado(
            media=media_turma,
            frequencia=freq_pct,
            media_corte=Decimal("6.00"),
            frequencia_corte=Decimal("75.00"),
        )

        rows_boletim.append(
            {
                "turma": turma.nome,
                "ano_periodo": periodo_ref_label if periodo_ref is not None else str(getattr(turma, "ano_letivo", "—")),
                "media": media_turma,
                "frequencia": freq_pct,
                "situacao": situacao,
                "avaliacoes_total": avaliacoes_turma_total,
                "notas_lancadas": notas_turma_lancadas,
            }
        )

    rows_boletim_informatica = []
    for matricula_info in informatica_ctx["matriculas"]:
        turma_info = matricula_info.turma
        avaliacoes_info_qs = InformaticaAvaliacao.objects.filter(
            turma=turma_info,
            ativo=True,
        )
        if periodo_ref is not None:
            avaliacoes_info_qs = avaliacoes_info_qs.filter(
                data__gte=periodo_ref.inicio,
                data__lte=periodo_ref.fim,
            )
        elif anos_letivos:
            avaliacoes_info_qs = avaliacoes_info_qs.filter(data__year=anos_letivos[0])

        notas_info_qs = InformaticaNota.objects.filter(
            aluno=aluno,
            avaliacao__in=avaliacoes_info_qs,
        )
        notas_info_lancadas = notas_info_qs.filter(_nota_lancada_q())
        media_info = notas_info_lancadas.aggregate(media=Avg("valor")).get("media")
        avaliacoes_info_total = avaliacoes_info_qs.count()
        notas_info_total = notas_info_lancadas.count()

        aulas_info_qs = InformaticaAulaDiario.objects.filter(
            turma=turma_info,
        ).exclude(status=InformaticaAulaDiario.Status.CANCELADA)
        if periodo_ref is not None:
            aulas_info_qs = aulas_info_qs.filter(
                data_aula__gte=periodo_ref.inicio,
                data_aula__lte=periodo_ref.fim,
            )
        elif anos_letivos:
            aulas_info_qs = aulas_info_qs.filter(data_aula__year=anos_letivos[0])

        total_aulas_info = aulas_info_qs.count()
        freq_pct_info = None
        if total_aulas_info:
            presencas = InformaticaFrequencia.objects.filter(
                aluno=aluno,
                aula__in=aulas_info_qs,
                presente=True,
            ).count()
            justificadas = InformaticaFrequencia.objects.filter(
                aluno=aluno,
                aula__in=aulas_info_qs,
                presente=False,
            ).exclude(Q(justificativa__isnull=True) | Q(justificativa="")).count()
            freq_pct_info = round(((presencas + justificadas) / total_aulas_info) * 100, 1)

        situacao_info = classify_resultado(
            media=media_info,
            frequencia=freq_pct_info,
            media_corte=Decimal("6.00"),
            frequencia_corte=Decimal("75.00"),
        )

        rows_boletim_informatica.append(
            {
                "turma": turma_info.codigo,
                "ano_periodo": periodo_ref_label if periodo_ref is not None else str(getattr(turma_info, "ano_letivo", "—")),
                "media": media_info,
                "frequencia": freq_pct_info,
                "situacao": situacao_info,
                "avaliacoes_total": avaliacoes_info_total,
                "notas_lancadas": notas_info_total,
            }
        )

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Boletim consolidado por período letivo, com situação acadêmica e frequência.",
        ),
        "periodos_disponiveis": periodos_disponiveis,
        "periodo_referencia": periodo_ref,
        "periodo_referencia_label": periodo_ref_label,
        "notas_lancadas_total": notas_lancadas_total,
        "notas_total": notas_total,
        "media_periodo": media_periodo,
        "rows_boletim": rows_boletim,
        "rows_boletim_informatica": rows_boletim_informatica,
    }
    return render(request, "educacao/aluno_area/ensino_boletins.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_avaliacoes(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    turma_ids = ctx["scope_ids"]["turma_ids"]
    informatica_ctx = _student_informatica_context(aluno)
    periodos_disponiveis, periodo_ref, periodo_ref_label, anos_letivos = _resolver_periodo_referencia_ensino(ctx, request)
    notas_qs = _filtrar_notas_por_periodo(
        aluno=aluno,
        turma_ids=turma_ids,
        periodo_ref=periodo_ref,
        anos_letivos=anos_letivos,
    )
    notas = list(notas_qs.order_by("avaliacao__data", "avaliacao__titulo", "id")[:200])
    notas_lancadas_total = notas_qs.filter(_nota_lancada_q()).count()
    notas_total = notas_qs.count()
    media_periodo = notas_qs.filter(_nota_lancada_q()).aggregate(media=Avg("valor")).get("media")
    notas_informatica_qs = InformaticaNota.objects.select_related("avaliacao", "avaliacao__turma").filter(
        aluno=aluno,
        avaliacao__turma_id__in=informatica_ctx["turma_ids"],
        avaliacao__ativo=True,
    )
    notas_informatica = list(notas_informatica_qs.order_by("avaliacao__data", "avaliacao__titulo", "id")[:200])
    notas_informatica_total = notas_informatica_qs.count()
    notas_informatica_lancadas = notas_informatica_qs.filter(_nota_lancada_q()).count()
    media_informatica = notas_informatica_qs.filter(_nota_lancada_q()).aggregate(media=Avg("valor")).get("media")

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Avaliações detalhadas por período letivo.",
        ),
        "periodos_disponiveis": periodos_disponiveis,
        "periodo_referencia": periodo_ref,
        "periodo_referencia_label": periodo_ref_label,
        "notas": notas,
        "notas_lancadas_total": notas_lancadas_total,
        "notas_total": notas_total,
        "media_periodo": media_periodo,
        "notas_informatica": notas_informatica,
        "notas_informatica_total": notas_informatica_total,
        "notas_informatica_lancadas": notas_informatica_lancadas,
        "media_informatica": media_informatica,
    }
    return render(request, "educacao/aluno_area/ensino_avaliacoes.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_disciplinas(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    disciplinas = []
    turma_ref = getattr(ctx["matricula_ref"], "turma", None)
    matriz_ref = getattr(turma_ref, "matriz_curricular", None)
    curso_extra_ref = getattr(turma_ref, "curso", None)

    if matriz_ref:
        disciplinas = list(
            matriz_ref.componentes.select_related("componente")
            .filter(ativo=True, componente__ativo=True)
            .order_by("ordem", "componente__nome")[:80]
        )
    elif curso_extra_ref:
        disciplinas = list(curso_extra_ref.disciplinas.filter(ativo=True).order_by("ordem", "nome")[:60])

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Componentes curriculares vinculados à matriz da turma.",
        ),
        "disciplinas": disciplinas,
        "usa_matriz_curricular": bool(matriz_ref),
    }
    return render(request, "educacao/aluno_area/ensino_disciplinas.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_horarios(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    turma_ids = ctx["scope_ids"]["turma_ids"]
    informatica_ctx = _student_informatica_context(ctx["aluno"])
    horarios = list(
        AulaHorario.objects.select_related("grade", "grade__turma", "professor")
        .filter(grade__turma_id__in=turma_ids)
        .order_by("dia", "inicio")[:120]
    )

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Locais e horários de aula por disciplina.",
        ),
        "horarios": horarios,
        "encontros_informatica": informatica_ctx["encontros_semanais"],
        "proximas_aulas_informatica": informatica_ctx["proximas_aulas"][:12],
    }
    return render(request, "educacao/aluno_area/ensino_horarios.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_mensagens(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    avisos = list(_scoped_avisos_aluno(ctx)[:60])
    informatica_ctx = _student_informatica_context(ctx["aluno"])
    avisos_informatica = []
    if informatica_ctx["faltas_em_aberto"] > 0:
        avisos_informatica.append(
            {
                "titulo": "Faltas de Informática pendentes de justificativa",
                "texto": (
                    f"Você possui {informatica_ctx['faltas_em_aberto']} falta(s) sem justificativa no Curso de Informática."
                ),
                "meta": "Acesse Ensino > Justificativa de Falta para enviar o motivo.",
            }
        )
    if informatica_ctx["alertas_ativos"] > 0:
        avisos_informatica.append(
            {
                "titulo": "Alerta de frequência em Informática",
                "texto": (
                    f"Há {informatica_ctx['alertas_ativos']} alerta(s) de frequência ativo(s) nas suas turmas de Informática."
                ),
                "meta": "Acompanhe presenças e frequência no seu painel.",
            }
        )
    for aula in informatica_ctx["proximas_aulas"][:5]:
        faixa = "Horário a confirmar"
        if aula.encontro and aula.encontro.hora_inicio and aula.encontro.hora_fim:
            faixa = f"{aula.encontro.hora_inicio.strftime('%H:%M')}-{aula.encontro.hora_fim.strftime('%H:%M')}"
        avisos_informatica.append(
            {
                "titulo": f"Próxima aula: {aula.turma.codigo}",
                "texto": f"{aula.data_aula.strftime('%d/%m/%Y')} • {faixa}",
                "meta": "Curso de Informática",
            }
        )

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Recados, comunicados e mensagens institucionais.",
        ),
        "avisos": avisos,
        "avisos_informatica": avisos_informatica,
    }
    return render(request, "educacao/aluno_area/ensino_mensagens.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_biblioteca(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    arquivos = list(_scoped_arquivos_aluno(ctx)[:60])
    emprestimos = list(
        BibliotecaEmprestimo.objects.select_related(
            "biblioteca",
            "livro",
            "exemplar",
            "matricula_institucional",
        )
        .filter(aluno=aluno)
        .order_by("-id")[:80]
    )
    emprestimos_ativos = [
        e for e in emprestimos if e.status in {BibliotecaEmprestimo.Status.ATIVO, BibliotecaEmprestimo.Status.RENOVADO, BibliotecaEmprestimo.Status.ATRASADO}
    ]
    emprestimos_atrasados = [e for e in emprestimos_ativos if e.em_atraso or e.status == BibliotecaEmprestimo.Status.ATRASADO]
    matricula_institucional = getattr(aluno, "matricula_institucional", None)

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Acompanhe seu histórico de biblioteca e materiais educacionais.",
        ),
        "matricula_institucional": matricula_institucional,
        "arquivos": arquivos,
        "emprestimos": emprestimos,
        "emprestimos_ativos_count": len(emprestimos_ativos),
        "emprestimos_atrasados_count": len(emprestimos_atrasados),
    }
    return render(request, "educacao/aluno_area/ensino_biblioteca.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_programas(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    filtro_programas = (request.GET.get("filtro") or "ativos").strip().lower()
    if filtro_programas not in {"ativos", "concluidos", "encerrados", "todos"}:
        filtro_programas = "ativos"
    participacoes = list(
        ProgramaComplementarParticipacao.objects.select_related(
            "programa",
            "oferta",
            "oferta__unidade",
            "matricula_institucional",
            "legacy_informatica_matricula",
        )
        .prefetch_related("frequencias", "oferta__horarios")
        .filter(aluno=aluno)
        .order_by("-id")[:120]
    )
    ativos = [p for p in participacoes if p.status == ProgramaComplementarParticipacao.Status.ATIVO]
    concluidos = [p for p in participacoes if p.status == ProgramaComplementarParticipacao.Status.CONCLUIDO]
    encerrados = [
        p
        for p in participacoes
        if p.status
        in {
            ProgramaComplementarParticipacao.Status.CANCELADO,
            ProgramaComplementarParticipacao.Status.DESLIGADO,
            ProgramaComplementarParticipacao.Status.SUSPENSO,
            ProgramaComplementarParticipacao.Status.TRANSFERIDO,
        }
    ]
    participacoes_visiveis = participacoes
    if filtro_programas == "ativos":
        participacoes_visiveis = ativos
    elif filtro_programas == "concluidos":
        participacoes_visiveis = concluidos
    elif filtro_programas == "encerrados":
        participacoes_visiveis = encerrados

    percentuais = [p.percentual_frequencia for p in participacoes if p.percentual_frequencia is not None]
    frequencia_media_geral = None
    if percentuais:
        frequencia_media_geral = float(sum(percentuais) / len(percentuais))

    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle=(
                "Acompanhe os programas complementares vinculados ao seu cadastro institucional "
                "(Informática, Ballet, Reforço e demais atividades)."
            ),
        ),
        "unidade_ref": ctx.get("unidade_ref"),
        "participacoes": participacoes,
        "participacoes_visiveis": participacoes_visiveis,
        "filtro_programas": filtro_programas,
        "ativos_count": len(ativos),
        "concluidos_count": len(concluidos),
        "encerrados_count": len(encerrados),
        "participacoes_visiveis_count": len(participacoes_visiveis),
        "frequencia_media_geral": frequencia_media_geral,
    }
    return render(request, "educacao/aluno_area/ensino_programas.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_apoio(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]
    apoio_form = ApoioEstudantilForm(request.POST or None, prefix="apoio")
    _apply_gp_form_classes(apoio_form)

    if request.method == "POST":
        form_kind = (request.POST.get("form_kind") or "").strip()
        if form_kind == "apoio" and apoio_form.is_valid():
            tipo = apoio_form.cleaned_data["tipo"]
            label = dict(ApoioEstudantilForm.base_fields["tipo"].choices).get(tipo, tipo)
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo=f"APOIO ESTUDANTIL - {label}",
                assunto=f"Solicitação de {label}",
                descricao=apoio_form.cleaned_data["descricao"],
            )
            messages.success(request, "Solicitação de apoio enviada para equipe responsável.")
            return redirect(reverse("educacao:aluno_ensino_apoio", args=[ctx["codigo_canonico"]]))

    apoios = list(
        ApoioMatricula.objects.select_related("matricula", "matricula__turma")
        .filter(matricula__aluno=aluno, ativo=True)
        .order_by("-id")[:60]
    )
    acompanhamentos_nee = list(AcompanhamentoNEE.objects.filter(aluno=aluno).order_by("-data", "-id")[:30])
    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Solicite acompanhamento pedagógico, social ou psicológico.",
        ),
        "apoio_form": apoio_form,
        "apoios": apoios,
        "acompanhamentos_nee": acompanhamentos_nee,
    }
    return render(request, "educacao/aluno_area/ensino_apoio.html", context)


@login_required
@require_perm("educacao.view")
def aluno_ensino_seletivos(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]

    if request.method == "POST":
        form_kind = (request.POST.get("form_kind") or "").strip()
        if form_kind == "inscrever_edital":
            edital_id = (request.POST.get("edital_id") or "").strip()
            if edital_id.isdigit():
                edital = BeneficioEdital.objects.filter(pk=int(edital_id)).first()
                if edital:
                    _, created = BeneficioEditalInscricao.objects.get_or_create(
                        edital=edital,
                        aluno=aluno,
                        defaults={
                            "escola": ctx["unidade_ref"],
                            "turma": getattr(ctx["matricula_ref"], "turma", None),
                            "status": BeneficioEditalInscricao.Status.ENVIADA,
                            "dados_json": {"origem": "portal_aluno"},
                            "criado_por": request.user,
                            "atualizado_por": request.user,
                        },
                    )
                    if not created:
                        messages.info(request, "Você já está inscrito neste processo seletivo.")
                    else:
                        messages.success(request, "Inscrição realizada com sucesso.")
            return redirect(reverse("educacao:aluno_ensino_seletivos", args=[ctx["codigo_canonico"]]))

    editais_educacao, inscricoes_map = _ensino_editais_e_inscricoes(ctx, aluno)
    context = {
        **_ensino_page_base_context(
            ctx,
            subtitle="Participe de editais e acompanhe processos seletivos.",
        ),
        "editais_educacao": editais_educacao,
        "inscricoes_map": inscricoes_map,
    }
    return render(request, "educacao/aluno_area/ensino_seletivos.html", context)


@login_required
@require_perm("educacao.view")
def aluno_pesquisa(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]

    if request.method == "POST" and (request.POST.get("form_kind") or "").strip() == "inscrever_pesquisa":
        edital_id = (request.POST.get("edital_id") or "").strip()
        if edital_id.isdigit():
            edital = BeneficioEdital.objects.filter(pk=int(edital_id)).first()
            if edital:
                _, created = BeneficioEditalInscricao.objects.get_or_create(
                    edital=edital,
                    aluno=aluno,
                    defaults={
                        "escola": ctx["unidade_ref"],
                        "turma": getattr(ctx["matricula_ref"], "turma", None),
                        "status": BeneficioEditalInscricao.Status.ENVIADA,
                        "dados_json": {"origem": "portal_aluno_pesquisa"},
                        "criado_por": request.user,
                        "atualizado_por": request.user,
                    },
                )
                if created:
                    messages.success(request, "Inscrição em edital de pesquisa realizada.")
                else:
                    messages.info(request, "Você já possui inscrição neste edital.")
        return redirect(reverse("educacao:aluno_pesquisa", args=[ctx["codigo_canonico"]]))

    editais_qs = BeneficioEdital.objects.none()
    if ctx["municipio_ref"] is not None:
        editais_qs = (
            BeneficioEdital.objects.select_related("beneficio")
            .filter(
                municipio=ctx["municipio_ref"],
                area=BeneficioTipo.Area.EDUCACAO,
                status__in=[
                    BeneficioEdital.Status.PUBLICADO,
                    BeneficioEdital.Status.INSCRICOES_ENCERRADAS,
                    BeneficioEdital.Status.EM_ANALISE,
                    BeneficioEdital.Status.RESULTADO_PRELIMINAR,
                    BeneficioEdital.Status.RESULTADO_FINAL,
                ],
            )
            .filter(Q(titulo__icontains="pesquisa") | Q(titulo__icontains="inov") | Q(texto__icontains="cient"))
            .order_by("-criado_em", "-id")
        )

    if not editais_qs.exists() and ctx["municipio_ref"] is not None:
        editais_qs = (
            BeneficioEdital.objects.select_related("beneficio")
            .filter(municipio=ctx["municipio_ref"], area=BeneficioTipo.Area.EDUCACAO)
            .order_by("-criado_em", "-id")
        )

    editais = list(editais_qs[:20])
    inscricoes = list(
        BeneficioEditalInscricao.objects.select_related("edital", "edital__beneficio")
        .filter(aluno=aluno, edital_id__in=[e.pk for e in editais])
        .order_by("-data_hora", "-id")
    )
    inscricoes_map = {i.edital_id: i for i in inscricoes}

    avaliacoes = []
    for ins in inscricoes:
        recursos = list(ins.recursos.all()[:1])
        avaliacoes.append(
            {
                "inscricao": ins,
                "status": ins.get_status_display(),
                "pontuacao": ins.pontuacao,
                "recurso": recursos[0] if recursos else None,
            }
        )

    context = {
        **_base_context(
            ctx,
            page_title="Pesquisa",
            page_subtitle="Editais, projetos e acompanhamento de avaliações.",
            nav_key="pesquisa",
        ),
        "editais": editais,
        "inscricoes": inscricoes,
        "inscricoes_map": inscricoes_map,
        "avaliacoes": avaliacoes,
    }
    return render(request, "educacao/aluno_area/pesquisa.html", context)


@login_required
@require_perm("educacao.view")
def aluno_central_servicos(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]

    chamado_form = ChamadoAlunoForm(request.POST or None, prefix="ch")
    cadastro_form = CadastroSolicitacaoForm(request.POST or None, prefix="cad")
    _apply_gp_form_classes(chamado_form)
    _apply_gp_form_classes(cadastro_form)

    if request.method == "POST":
        form_kind = (request.POST.get("form_kind") or "").strip()

        if form_kind == "abrir_chamado" and chamado_form.is_valid():
            municipio = ctx["municipio_ref"]
            if municipio is None:
                messages.error(request, "Município não identificado para registrar o chamado.")
            else:
                categoria = chamado_form.cleaned_data["categoria"]
                tipo_map = {
                    "SISTEMA": OuvidoriaCadastro.Tipo.SUGESTAO,
                    "DOCUMENTOS": OuvidoriaCadastro.Tipo.ESIC,
                    "ACADEMICO": OuvidoriaCadastro.Tipo.RECLAMACAO,
                    "ADMINISTRATIVO": OuvidoriaCadastro.Tipo.RECLAMACAO,
                }
                prioridade_map = {
                    "SISTEMA": OuvidoriaCadastro.Prioridade.MEDIA,
                    "DOCUMENTOS": OuvidoriaCadastro.Prioridade.MEDIA,
                    "ACADEMICO": OuvidoriaCadastro.Prioridade.ALTA,
                    "ADMINISTRATIVO": OuvidoriaCadastro.Prioridade.MEDIA,
                }
                OuvidoriaCadastro.objects.create(
                    municipio=municipio,
                    secretaria=ctx["secretaria_ref"],
                    unidade=ctx["unidade_ref"],
                    protocolo=_next_protocolo_ouvidoria(municipio),
                    assunto=chamado_form.cleaned_data["assunto"],
                    tipo=tipo_map.get(categoria, OuvidoriaCadastro.Tipo.RECLAMACAO),
                    prioridade=prioridade_map.get(categoria, OuvidoriaCadastro.Prioridade.MEDIA),
                    descricao=chamado_form.cleaned_data["descricao"],
                    solicitante_nome=aluno.nome,
                    solicitante_email=aluno.email or (getattr(request.user, "email", "") or ""),
                    solicitante_telefone=aluno.telefone or "",
                    prazo_resposta=timezone.localdate() + timedelta(days=10),
                    status=OuvidoriaCadastro.Status.ABERTO,
                    criado_por=request.user,
                )
                messages.success(request, "Chamado aberto com sucesso na Central de Serviços.")
            return redirect(reverse("educacao:aluno_central_servicos", args=[ctx["codigo_canonico"]]))

        if form_kind == "solicitacao_cadastro" and cadastro_form.is_valid():
            tipo = dict(CadastroSolicitacaoForm.base_fields["tipo"].choices).get(cadastro_form.cleaned_data["tipo"], "Cadastro")
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo=f"CADASTRO - {tipo}",
                assunto=f"Solicitação cadastral: {tipo}",
                descricao=cadastro_form.cleaned_data["descricao"],
            )
            messages.success(request, "Solicitação cadastral enviada para análise.")
            return redirect(reverse("educacao:aluno_central_servicos", args=[ctx["codigo_canonico"]]))

    chamados = OuvidoriaCadastro.objects.none()
    respostas_texto = {}
    if ctx["municipio_ref"] is not None:
        chamados = (
            OuvidoriaCadastro.objects.filter(municipio=ctx["municipio_ref"])
            .filter(Q(criado_por=request.user) | Q(solicitante_nome__iexact=aluno.nome))
            .order_by("-criado_em", "-id")[:40]
        )
        respostas_texto = {
            r.chamado_id: r.resposta
            for r in OuvidoriaResposta.objects.filter(chamado_id__in=[c.pk for c in chamados]).order_by("-criado_em")
        }

    base_conhecimento = [
        {
            "titulo": "Como solicitar documentos",
            "descricao": "Abra uma solicitação na seção Documentos/Processos e acompanhe pelo status.",
        },
        {
            "titulo": "Como justificar falta",
            "descricao": "Na seção Ensino, envie o motivo e anexo para validação da secretaria escolar.",
        },
        {
            "titulo": "Como participar de editais",
            "descricao": "Use Ensino ou Pesquisa para se inscrever nos editais com critérios publicados.",
        },
        {
            "titulo": "Como registrar chamado",
            "descricao": "Registre o chamado nesta tela e acompanhe respostas pelo protocolo.",
        },
    ]

    context = {
        **_base_context(
            ctx,
            page_title="Central de Serviços",
            page_subtitle="Registrar chamados, consultar base de conhecimento e enviar solicitações cadastrais.",
            nav_key="servicos",
        ),
        "chamado_form": chamado_form,
        "cadastro_form": cadastro_form,
        "chamados": chamados,
        "respostas_texto": respostas_texto,
        "base_conhecimento": base_conhecimento,
    }
    return render(request, "educacao/aluno_area/central_servicos.html", context)


@login_required
@require_perm("educacao.view")
def aluno_atividades(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]

    if request.method == "POST" and (request.POST.get("form_kind") or "").strip() == "evento_inscricao":
        evento_titulo = (request.POST.get("evento_titulo") or "").strip()[:120]
        if evento_titulo:
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo="EVENTO ESTUDANTIL",
                assunto=f"Inscrição em evento: {evento_titulo}",
                descricao=f"Aluno solicitou inscrição/confirmou presença no evento '{evento_titulo}'.",
            )
            messages.success(request, "Inscrição no evento registrada.")
        return redirect(reverse("educacao:aluno_atividades", args=[ctx["codigo_canonico"]]))

    eventos = CalendarioEducacionalEvento.objects.none()
    if ctx["secretaria_ref"] is not None:
        eventos = (
            CalendarioEducacionalEvento.objects.filter(
                ativo=True,
                secretaria=ctx["secretaria_ref"],
                data_fim__gte=timezone.localdate(),
            )
            .filter(Q(unidade__isnull=True) | Q(unidade=ctx["unidade_ref"]))
            .order_by("data_inicio", "titulo")[:30]
        )

    programas = list(
        BeneficioCampanhaAluno.objects.select_related("campanha", "campanha__beneficio")
        .filter(aluno=aluno)
        .order_by("-id")[:20]
    )
    entregas = list(
        BeneficioEntrega.objects.select_related("beneficio", "campanha")
        .filter(aluno=aluno)
        .order_by("-data_hora", "-id")[:20]
    )

    context = {
        **_base_context(
            ctx,
            page_title="Atividades Estudantis",
            page_subtitle="Eventos, programas, benefícios e acompanhamento de entregas.",
            nav_key="atividades",
        ),
        "eventos": eventos,
        "programas": programas,
        "entregas": entregas,
    }
    return render(request, "educacao/aluno_area/atividades.html", context)


@login_required
@require_perm("educacao.view")
def aluno_saude(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]

    paciente = PacienteSaude.objects.select_related("unidade_referencia", "programa").filter(aluno=aluno).first()

    agendamentos = list(
        AgendamentoSaude.objects.select_related("unidade", "profissional", "especialidade")
        .filter(aluno=aluno)
        .order_by("-inicio", "-id")[:30]
    )
    atendimentos = list(
        AtendimentoSaude.objects.select_related("unidade", "profissional")
        .filter(aluno=aluno)
        .order_by("-data", "-id")[:30]
    )

    nee_necessidades = list(AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno, ativo=True)[:20])
    nee_planos = list(PlanoClinicoNEE.objects.filter(aluno=aluno)[:5])
    nee_acompanhamentos = list(AcompanhamentoNEE.objects.filter(aluno=aluno).order_by("-data", "-id")[:20])

    context = {
        **_base_context(
            ctx,
            page_title="Saúde",
            page_subtitle="Agenda de atendimentos, histórico clínico educacional e acompanhamento NEE.",
            nav_key="saude",
        ),
        "paciente": paciente,
        "agendamentos": agendamentos,
        "atendimentos": atendimentos,
        "nee_necessidades": nee_necessidades,
        "nee_planos": nee_planos,
        "nee_acompanhamentos": nee_acompanhamentos,
    }
    return render(request, "educacao/aluno_area/saude.html", context)


@login_required
@require_perm("educacao.view")
def aluno_comunicacao(request, codigo: str):
    ctx = _resolve_contexto_aluno(request, codigo)
    aluno = ctx["aluno"]

    if request.method == "POST" and (request.POST.get("form_kind") or "").strip() == "enquete_voto":
        enquete = (request.POST.get("enquete") or "").strip()
        voto = (request.POST.get("voto") or "").strip()
        if enquete and voto:
            _create_processo_aluno(
                request=request,
                ctx=ctx,
                tipo="ENQUETE ESTUDANTIL",
                assunto=f"Voto em enquete: {enquete}",
                descricao=f"Resposta registrada pelo aluno: {voto}",
            )
            messages.success(request, "Participação na enquete registrada.")
        return redirect(reverse("educacao:aluno_comunicacao", args=[ctx["codigo_canonico"]]))

    avisos = list(_scoped_avisos_aluno(ctx)[:30])
    eventos = CalendarioEducacionalEvento.objects.none()
    if ctx["secretaria_ref"] is not None:
        eventos = (
            CalendarioEducacionalEvento.objects.filter(
                ativo=True,
                secretaria=ctx["secretaria_ref"],
                data_fim__gte=timezone.localdate(),
            )
            .filter(Q(unidade__isnull=True) | Q(unidade=ctx["unidade_ref"]))
            .order_by("data_inicio", "titulo")[:20]
        )

    matriculas_total = len(ctx["matriculas"])
    notas_qs = Nota.objects.filter(aluno=aluno)
    notas_total = notas_qs.count()
    notas_lancadas = notas_qs.filter(_nota_lancada_q()).count()

    relatorios = [
        {
            "titulo": "Desempenho escolar",
            "descricao": f"{notas_lancadas} nota(s) lançada(s) em {notas_total} registro(s).",
        },
        {
            "titulo": "Frequência e permanência",
            "descricao": f"{matriculas_total} matrícula(s) vinculada(s) ao aluno.",
        },
        {
            "titulo": "Evolução pedagógica",
            "descricao": "Acompanhe evolução por período no histórico completo.",
            "url": reverse("educacao:historico_aluno", args=[aluno.pk]),
        },
    ]

    enquetes = [
        {
            "titulo": "Prioridade para próximo evento escolar",
            "opcoes": ["Feira de ciências", "Semana cultural", "Gincana esportiva"],
        },
        {
            "titulo": "Canal preferido para comunicados",
            "opcoes": ["Aplicativo GEPUB", "E-mail", "Mural da escola"],
        },
    ]

    context = {
        **_base_context(
            ctx,
            page_title="Comunicação Social",
            page_subtitle="Enquetes, eventos institucionais e relatórios de acompanhamento do aluno.",
            nav_key="comunicacao",
        ),
        "avisos": avisos,
        "eventos": eventos,
        "relatorios": relatorios,
        "enquetes": enquetes,
    }
    return render(request, "educacao/aluno_area/comunicacao.html", context)
