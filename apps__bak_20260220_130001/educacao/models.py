from django.conf import settings
from django.db import models
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile


class Turma(models.Model):
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="turmas",
    )

    # ✅ NOVO: vínculo professor ⇄ turma
    professores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="turmas_ministradas",
    )

    nome = models.CharField(max_length=160)
    ano_letivo = models.PositiveIntegerField(db_index=True)

    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    turno = models.CharField(max_length=20, choices=Turno.choices, default=Turno.MANHA)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        ordering = ["-ano_letivo", "nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ano_letivo"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.ano_letivo})"


class Aluno(models.Model):
    nome = models.CharField(max_length=180)

    # ✅ FOTO DO ALUNO
    foto = models.ImageField(
        upload_to="alunos/",
        blank=True,
        null=True,
        verbose_name="Foto",
    )

    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, blank=True, default="")
    nis = models.CharField(max_length=20, blank=True, default="")
    nome_mae = models.CharField(max_length=180, blank=True, default="")
    nome_pai = models.CharField(max_length=180, blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    endereco = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Aluno"
        verbose_name_plural = "Alunos"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["cpf"]),
            models.Index(fields=["nis"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Crop/resize automático da foto
        if self.foto:
            try:
                img = Image.open(self.foto)
                img = img.convert("RGB")

                w, h = img.size
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side))

                img = img.resize((512, 512), Image.LANCZOS)

                buf = BytesIO()
                img.save(buf, format="JPEG", quality=88, optimize=True)

                file_name = self.foto.name.rsplit(".", 1)[0] + ".jpg"
                self.foto.save(file_name, ContentFile(buf.getvalue()), save=False)

                super().save(update_fields=["foto"])
            except Exception:
                pass


class Matricula(models.Model):
    class Situacao(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        TRANSFERIDO = "TRANSFERIDO", "Transferido"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        EVADIDO = "EVADIDO", "Evadido"
        CANCELADO = "CANCELADO", "Cancelado"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="matriculas",
    )
    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.PROTECT,
        related_name="matriculas",
    )

    data_matricula = models.DateField(null=True, blank=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.ATIVA)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Matrícula"
        verbose_name_plural = "Matrículas"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "turma"],
                name="uniq_aluno_por_turma",
            )
        ]
        indexes = [
            models.Index(fields=["situacao"]),
            models.Index(fields=["data_matricula"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} → {self.turma} ({self.situacao})"
    

# Importa submódulos de models (sem wildcard) para registrar os models do app
from . import models_diario  # noqa: F401
from . import models_horarios  # noqa: F401
from . import models_periodos  # noqa: F401
from . import models_notas  # noqa: F401
