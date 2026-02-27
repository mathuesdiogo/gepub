from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from apps.core.security import derive_cpf_security_fields, mask_cpf, resolve_cpf_digits


class Curso(models.Model):
    class ModalidadeOferta(models.TextChoices):
        REGULAR = "REGULAR", "Ensino Regular"
        EDUCACAO_INFANTIL = "EDUCACAO_INFANTIL", "Educação Infantil"
        EJA = "EJA", "Educação de Jovens e Adultos (EJA)"
        TECNICA = "TECNICA", "Educação Profissional Técnica"
        FIC = "FIC", "Formação Inicial e Continuada (FIC)"
        SUPERIOR = "SUPERIOR", "Educação Superior"
        LIVRE = "LIVRE", "Curso Livre"

    nome = models.CharField(max_length=180)
    codigo = models.CharField(max_length=40, blank=True, default="")
    modalidade_oferta = models.CharField(
        max_length=30,
        choices=ModalidadeOferta.choices,
        default=ModalidadeOferta.REGULAR,
        db_index=True,
    )
    eixo_tecnologico = models.CharField(max_length=120, blank=True, default="")
    carga_horaria = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["nome", "codigo"],
                name="uniq_curso_nome_codigo",
            )
        ]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["modalidade_oferta"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome if not self.codigo else f"{self.nome} ({self.codigo})"


class CursoDisciplina(models.Model):
    class TipoAula(models.TextChoices):
        TEORICA = "TEORICA", "Teórica"
        PRATICA = "PRATICA", "Prática"
        LABORATORIO = "LABORATORIO", "Laboratório"
        OFICINA = "OFICINA", "Oficina"
        PROJETO = "PROJETO", "Projeto"
        PERFORMANCE = "PERFORMANCE", "Performance"
        OUTRA = "OUTRA", "Outra"

    curso = models.ForeignKey(
        "educacao.Curso",
        on_delete=models.CASCADE,
        related_name="disciplinas",
    )
    nome = models.CharField(max_length=160)
    tipo_aula = models.CharField(
        max_length=20,
        choices=TipoAula.choices,
        default=TipoAula.TEORICA,
    )
    carga_horaria = models.PositiveIntegerField(default=0)
    ordem = models.PositiveIntegerField(default=1)
    obrigatoria = models.BooleanField(default=True)
    ementa = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Disciplina do curso"
        verbose_name_plural = "Disciplinas do curso"
        ordering = ["curso__nome", "ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["curso", "nome"],
                name="uniq_disciplina_nome_por_curso",
            )
        ]
        indexes = [
            models.Index(fields=["curso", "ordem"]),
            models.Index(fields=["curso", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.curso.nome} • {self.nome}"


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

    class Modalidade(models.TextChoices):
        REGULAR = "REGULAR", "Ensino Regular"
        EDUCACAO_INFANTIL = "EDUCACAO_INFANTIL", "Educação Infantil"
        EJA = "EJA", "Educação de Jovens e Adultos (EJA)"
        EDUCACAO_PROFISSIONAL = "EDUCACAO_PROFISSIONAL", "Educação Profissional"
        EDUCACAO_ESPECIAL = "EDUCACAO_ESPECIAL", "Educação Especial"
        ATIVIDADE_COMPLEMENTAR = "ATIVIDADE_COMPLEMENTAR", "Atividade Complementar"

    class Etapa(models.TextChoices):
        CRECHE = "CRECHE", "Creche"
        PRE_ESCOLA = "PRE_ESCOLA", "Pré-escola"
        FUNDAMENTAL_ANOS_INICIAIS = "FUNDAMENTAL_ANOS_INICIAIS", "Ensino Fundamental (Anos Iniciais)"
        FUNDAMENTAL_ANOS_FINAIS = "FUNDAMENTAL_ANOS_FINAIS", "Ensino Fundamental (Anos Finais)"
        ENSINO_MEDIO = "ENSINO_MEDIO", "Ensino Médio"
        EJA_FUNDAMENTAL = "EJA_FUNDAMENTAL", "EJA - Ensino Fundamental"
        EJA_MEDIO = "EJA_MEDIO", "EJA - Ensino Médio"
        TECNICO_INTEGRADO = "TECNICO_INTEGRADO", "Técnico Integrado"
        TECNICO_CONCOMITANTE = "TECNICO_CONCOMITANTE", "Técnico Concomitante"
        TECNICO_SUBSEQUENTE = "TECNICO_SUBSEQUENTE", "Técnico Subsequente"
        FIC = "FIC", "Formação Inicial e Continuada (FIC)"
        AEE = "AEE", "Atendimento Educacional Especializado (AEE)"

    class FormaOferta(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "Presencial"
        HIBRIDO = "HIBRIDO", "Híbrido"
        EAD = "EAD", "Educação a Distância"

    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    turno = models.CharField(max_length=20, choices=Turno.choices, default=Turno.MANHA)
    modalidade = models.CharField(
        max_length=40,
        choices=Modalidade.choices,
        default=Modalidade.REGULAR,
        db_index=True,
    )
    etapa = models.CharField(
        max_length=40,
        choices=Etapa.choices,
        default=Etapa.FUNDAMENTAL_ANOS_INICIAIS,
        db_index=True,
    )
    forma_oferta = models.CharField(
        max_length=20,
        choices=FormaOferta.choices,
        default=FormaOferta.PRESENCIAL,
    )
    curso = models.ForeignKey(
        "educacao.Curso",
        on_delete=models.SET_NULL,
        related_name="turmas",
        null=True,
        blank=True,
    )
    classe_especial = models.BooleanField(
        default=False,
        help_text="Marque quando a turma for de classe especial.",
    )
    bilingue_surdos = models.BooleanField(
        default=False,
        help_text="Marque quando a turma for bilíngue de surdos.",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        ordering = ["-ano_letivo", "nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ano_letivo"]),
            models.Index(fields=["modalidade"]),
            models.Index(fields=["etapa"]),
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
    cpf_enc = models.TextField(blank=True, default="")
    cpf_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    cpf_last4 = models.CharField(max_length=4, blank=True, default="")
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
        cpf_digits = resolve_cpf_digits(self.cpf, self.cpf_enc)
        cpf_enc, cpf_hash, cpf_last4 = derive_cpf_security_fields(cpf_digits)
        if cpf_digits:
            if cpf_enc:
                self.cpf_enc = cpf_enc
            if cpf_hash:
                self.cpf_hash = cpf_hash
        else:
            self.cpf_enc = ""
            self.cpf_hash = ""
        self.cpf_last4 = cpf_last4
        self.cpf = mask_cpf(cpf_digits)

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

    @property
    def cpf_digits(self) -> str:
        return resolve_cpf_digits(self.cpf, self.cpf_enc)


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
    resultado_final = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Resultado final da matrícula (aprovado, reprovado, curso em andamento etc.).",
    )
    concluinte = models.BooleanField(default=False)
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
            models.Index(fields=["resultado_final"]),
            models.Index(fields=["data_matricula"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} → {self.turma} ({self.situacao})"


class MatriculaMovimentacao(models.Model):
    class Tipo(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        REMANEJAMENTO = "REMANEJAMENTO", "Remanejamento"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferência"
        CANCELAMENTO = "CANCELAMENTO", "Cancelamento"
        REATIVACAO = "REATIVACAO", "Reativação"
        SITUACAO = "SITUACAO", "Mudança de situação"

    matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.CASCADE,
        related_name="movimentacoes",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="movimentacoes_matricula",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_matricula",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.SITUACAO)

    turma_origem = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.PROTECT,
        related_name="movimentacoes_origem",
        null=True,
        blank=True,
    )
    turma_destino = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.PROTECT,
        related_name="movimentacoes_destino",
        null=True,
        blank=True,
    )

    situacao_anterior = models.CharField(max_length=20, blank=True, default="")
    situacao_nova = models.CharField(max_length=20, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação de matrícula"
        verbose_name_plural = "Movimentações de matrícula"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["aluno"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} • {self.get_tipo_display()} • {self.criado_em:%d/%m/%Y %H:%M}"


class MatriculaCurso(models.Model):
    class Situacao(models.TextChoices):
        MATRICULADO = "MATRICULADO", "Matriculado"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        TRANCADO = "TRANCADO", "Trancado"
        CANCELADO = "CANCELADO", "Cancelado"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="matriculas_cursos",
    )
    curso = models.ForeignKey(
        "educacao.Curso",
        on_delete=models.PROTECT,
        related_name="matriculas_alunos",
    )
    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matriculas_cursos",
        help_text="Opcional: turma/oferta específica deste curso.",
    )
    data_matricula = models.DateField(default=timezone.localdate)
    data_conclusao = models.DateField(null=True, blank=True)
    situacao = models.CharField(
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.MATRICULADO,
    )
    nota_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    frequencia_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    observacao = models.TextField(blank=True, default="")
    cadastrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matriculas_cursos_registradas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Matrícula em curso"
        verbose_name_plural = "Matrículas em cursos"
        ordering = ["-data_matricula", "-id"]
        indexes = [
            models.Index(fields=["aluno", "situacao"]),
            models.Index(fields=["curso", "situacao"]),
            models.Index(fields=["data_matricula"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.curso.nome} • {self.get_situacao_display()}"


class CoordenacaoEnsino(models.Model):
    coordenador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="coordenacoes_ensino",
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="coordenacoes_ensino",
    )
    modalidade = models.CharField(
        max_length=40,
        choices=Turma.Modalidade.choices,
        default=Turma.Modalidade.REGULAR,
    )
    etapa = models.CharField(
        max_length=40,
        choices=Turma.Etapa.choices,
        blank=True,
        default="",
    )
    ativo = models.BooleanField(default=True)
    inicio = models.DateField(default=timezone.localdate)
    fim = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Coordenação de ensino"
        verbose_name_plural = "Coordenações de ensino"
        ordering = ["unidade__nome", "modalidade", "coordenador__username"]
        indexes = [
            models.Index(fields=["unidade", "modalidade", "ativo"]),
        ]

    def __str__(self) -> str:
        base = f"{self.unidade} • {self.get_modalidade_display()}"
        etapa = self.get_etapa_display() if self.etapa else ""
        return f"{base} • {etapa}" if etapa else base


class AlunoDocumento(models.Model):
    class Tipo(models.TextChoices):
        CERTIDAO_NASCIMENTO = "CERTIDAO_NASCIMENTO", "Certidão de nascimento"
        CPF = "CPF", "CPF"
        RG = "RG", "RG"
        COMPROVANTE_RESIDENCIA = "COMPROVANTE_RESIDENCIA", "Comprovante de residência"
        CARTAO_VACINA = "CARTAO_VACINA", "Cartão de vacina"
        LAUDO = "LAUDO", "Laudo"
        BOLETIM = "BOLETIM", "Boletim"
        HISTORICO = "HISTORICO", "Histórico escolar"
        DECLARACAO = "DECLARACAO", "Declaração"
        CERTIFICADO = "CERTIFICADO", "Certificado"
        TRANSFERENCIA = "TRANSFERENCIA", "Documento de transferência"
        OUTRO = "OUTRO", "Outro"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="documentos",
    )
    tipo = models.CharField(max_length=40, choices=Tipo.choices, default=Tipo.OUTRO)
    titulo = models.CharField(max_length=180)
    numero_documento = models.CharField(max_length=80, blank=True, default="")
    arquivo = models.FileField(upload_to="educacao/documentos/alunos/%Y/%m/", blank=True, null=True)
    data_emissao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True, default="")
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_aluno_enviados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Documento do aluno"
        verbose_name_plural = "Documentos do aluno"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["aluno", "tipo"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} • {self.titulo}"


class AlunoCertificado(models.Model):
    class Tipo(models.TextChoices):
        DECLARACAO_MATRICULA = "DECLARACAO_MATRICULA", "Declaração de matrícula"
        HISTORICO_ESCOLAR = "HISTORICO_ESCOLAR", "Histórico escolar"
        CERTIFICADO_CONCLUSAO = "CERTIFICADO_CONCLUSAO", "Certificado de conclusão"
        CERTIFICADO_CURSO = "CERTIFICADO_CURSO", "Certificado de curso"
        DECLARACAO_TRANSFERENCIA = "DECLARACAO_TRANSFERENCIA", "Declaração de transferência"
        OUTRO = "OUTRO", "Outro"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="certificados",
    )
    matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificados",
    )
    curso = models.ForeignKey(
        "educacao.Curso",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificados_emitidos",
    )
    tipo = models.CharField(max_length=40, choices=Tipo.choices, default=Tipo.CERTIFICADO_CONCLUSAO)
    titulo = models.CharField(max_length=180)
    codigo_verificacao = models.CharField(max_length=24, unique=True, blank=True, default="")
    data_emissao = models.DateField(default=timezone.localdate)
    carga_horaria = models.PositiveIntegerField(default=0)
    resultado_final = models.CharField(max_length=60, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    arquivo_pdf = models.FileField(upload_to="educacao/certificados/%Y/%m/", blank=True, null=True)
    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificados_emitidos",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Certificado do aluno"
        verbose_name_plural = "Certificados do aluno"
        ordering = ["-data_emissao", "-id"]
        indexes = [
            models.Index(fields=["aluno", "tipo"]),
            models.Index(fields=["codigo_verificacao"]),
            models.Index(fields=["ativo"]),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo_verificacao:
            self.codigo_verificacao = uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.aluno} • {self.titulo}"


class CarteiraEstudantil(models.Model):
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="carteiras_estudantis",
    )
    matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carteiras_estudantis",
    )
    codigo_verificacao = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    codigo_estudante = models.CharField(max_length=40, blank=True, default="", db_index=True)
    dados_snapshot = models.JSONField(default=dict, blank=True)
    emitida_em = models.DateTimeField(auto_now_add=True)
    validade = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    emitida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carteiras_estudantis_emitidas",
    )

    class Meta:
        verbose_name = "Carteira estudantil"
        verbose_name_plural = "Carteiras estudantis"
        ordering = ["-emitida_em", "-id"]
        indexes = [
            models.Index(fields=["aluno", "ativa"]),
            models.Index(fields=["codigo_estudante"]),
            models.Index(fields=["validade"]),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo_estudante:
            if self.matricula_id:
                self.codigo_estudante = f"MAT-{self.matricula_id:06d}"
            else:
                self.codigo_estudante = f"ALU-{self.aluno_id:06d}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.aluno} • {self.codigo_estudante}"


# Importa submódulos de models (sem wildcard) para registrar os models do app
from . import models_diario  # noqa: F401
from . import models_horarios  # noqa: F401
from . import models_periodos  # noqa: F401
from . import models_notas  # noqa: F401
from . import models_assistencia  # noqa: F401
from . import models_calendario  # noqa: F401
