from django.db import models
from django.utils import timezone
from apps.org.models import Unidade


class ProfissionalSaude(models.Model):
    class Cargo(models.TextChoices):
        MEDICO = "MEDICO", "Médico"
        ENFERMEIRO = "ENFERMEIRO", "Enfermeiro"
        TECNICO = "TECNICO", "Técnico"
        AGENTE = "AGENTE", "Agente de Saúde"
        ADMIN = "ADMIN", "Administrativo"
        OUTROS = "OUTROS", "Outros"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="profissionais_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    nome = models.CharField(max_length=180)
    cpf = models.CharField(max_length=14, blank=True, default="")
    cargo = models.CharField(max_length=20, choices=Cargo.choices)
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Profissional de Saúde"
        verbose_name_plural = "Profissionais de Saúde"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["cargo"]),
            models.Index(fields=["ativo"]),
        ]


    def save(self, *args, **kwargs):
        # Mantém compatibilidade com telas antigas: preenche paciente_* a partir do aluno quando existir.
        if self.aluno_id:
            try:
                nome = getattr(self.aluno, "nome", "") or ""
                cpf = getattr(self.aluno, "cpf", "") or ""
                if nome and not (self.paciente_nome or "").strip():
                    self.paciente_nome = nome
                if cpf and not (self.paciente_cpf or "").strip():
                    self.paciente_cpf = cpf
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class AtendimentoSaude(models.Model):
    class Tipo(models.TextChoices):
        CONSULTA = "CONSULTA", "Consulta"
        PROCEDIMENTO = "PROCEDIMENTO", "Procedimento"
        VACINA = "VACINA", "Vacina"
        VISITA = "VISITA", "Visita domiciliar"
        TRIAGEM = "TRIAGEM", "Triagem"
        OUTROS = "OUTROS", "Outros"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="atendimentos_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    profissional = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="atendimentos",
    )

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="atendimentos_saude",
        null=True,
        blank=True,
    )

    data = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONSULTA)

    paciente_nome = models.CharField(max_length=180)
    paciente_cpf = models.CharField(max_length=14, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    cid = models.CharField("CID (opcional)", max_length=20, blank=True, default="")

    class Meta:
        verbose_name = "Atendimento"
        verbose_name_plural = "Atendimentos"
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["data"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["paciente_nome"]),
        ]


    def save(self, *args, **kwargs):
        # Mantém compatibilidade com telas antigas: preenche paciente_* a partir do aluno quando existir.
        if self.aluno_id:
            try:
                nome = getattr(self.aluno, "nome", "") or ""
                cpf = getattr(self.aluno, "cpf", "") or ""
                if nome and not (self.paciente_nome or "").strip():
                    self.paciente_nome = nome
                if cpf and not (self.paciente_cpf or "").strip():
                    self.paciente_cpf = cpf
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.paciente_nome} — {self.get_tipo_display()} ({self.data})"
