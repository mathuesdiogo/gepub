from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def current_year() -> int:
    return timezone.localdate().year


class MatriculaInstitucional(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        INATIVA = "INATIVA", "Inativa"
        TRANSFERIDA = "TRANSFERIDA", "Transferida"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"
        BLOQUEADA = "BLOQUEADA", "Bloqueada"

    aluno = models.OneToOneField(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="matricula_institucional",
    )
    numero_matricula = models.CharField(max_length=40, unique=True, db_index=True)
    ano_referencia = models.PositiveIntegerField(default=current_year, db_index=True)
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.PROTECT,
        related_name="matriculas_institucionais",
        null=True,
        blank=True,
    )
    unidade_origem = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="matriculas_institucionais",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA, db_index=True)
    data_geracao = models.DateTimeField(auto_now_add=True)
    data_ativacao = models.DateField(default=timezone.localdate)
    data_encerramento = models.DateField(null=True, blank=True)
    motivo_encerramento = models.TextField(blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matriculas_institucionais_criadas",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Matrícula institucional"
        verbose_name_plural = "Matrículas institucionais"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["numero_matricula"]),
            models.Index(fields=["status"]),
            models.Index(fields=["ano_referencia"]),
            models.Index(fields=["municipio", "status"]),
        ]

    def clean(self):
        errors = {}
        if self.data_encerramento and self.data_ativacao and self.data_encerramento < self.data_ativacao:
            errors["data_encerramento"] = "A data de encerramento não pode ser anterior à data de ativação."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.numero_matricula = (self.numero_matricula or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.numero_matricula} • {self.aluno.nome}"


class MatriculaInstitucionalHistorico(models.Model):
    matricula_institucional = models.ForeignKey(
        "educacao.MatriculaInstitucional",
        on_delete=models.CASCADE,
        related_name="historico_status",
    )
    status_anterior = models.CharField(max_length=20, blank=True, default="")
    status_novo = models.CharField(max_length=20, choices=MatriculaInstitucional.Status.choices, db_index=True)
    contexto = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matriculas_institucionais_historico",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Histórico da matrícula institucional"
        verbose_name_plural = "Históricos da matrícula institucional"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["matricula_institucional", "criado_em"]),
            models.Index(fields=["status_novo"]),
            models.Index(fields=["contexto"]),
        ]

    def __str__(self) -> str:
        return f"{self.matricula_institucional.numero_matricula} • {self.status_novo}"


class BibliotecaEscolar(models.Model):
    class Tipo(models.TextChoices):
        PRINCIPAL = "PRINCIPAL", "Biblioteca principal"
        SALA_LEITURA = "SALA_LEITURA", "Sala de leitura"
        ACERVO_COMPLEMENTAR = "ACERVO_COMPLEMENTAR", "Acervo complementar"
        INFANTIL = "INFANTIL", "Biblioteca infantil"
        TECNICA = "TECNICA", "Biblioteca técnica"
        LABORATORIO = "LABORATORIO", "Biblioteca de laboratório"

    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        INATIVA = "INATIVA", "Inativa"

    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="bibliotecas_escolares",
    )
    nome = models.CharField(max_length=180)
    codigo = models.CharField(max_length=40, blank=True, default="")
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.PRINCIPAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA, db_index=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bibliotecas_escolares_responsavel",
    )
    limite_emprestimos_ativos = models.PositiveSmallIntegerField(default=3)
    dias_prazo_emprestimo = models.PositiveSmallIntegerField(default=7)
    permitir_emprestimo_com_atraso = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Biblioteca escolar"
        verbose_name_plural = "Bibliotecas escolares"
        ordering = ["unidade__nome", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["unidade", "nome"], name="uniq_biblioteca_por_unidade_nome"),
        ]
        indexes = [
            models.Index(fields=["unidade", "status"]),
            models.Index(fields=["codigo"]),
        ]

    def clean(self):
        errors = {}
        if self.unidade_id and getattr(self.unidade, "tipo", None) != "EDUCACAO":
            errors["unidade"] = "A biblioteca escolar deve estar vinculada a uma unidade de Educação."
        if self.limite_emprestimos_ativos < 1:
            errors["limite_emprestimos_ativos"] = "Informe ao menos 1 empréstimo ativo permitido."
        if self.dias_prazo_emprestimo < 1:
            errors["dias_prazo_emprestimo"] = "Informe ao menos 1 dia como prazo de empréstimo."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.nome} • {self.unidade.nome}"


class BibliotecaLivro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    biblioteca = models.ForeignKey(
        "educacao.BibliotecaEscolar",
        on_delete=models.PROTECT,
        related_name="livros",
    )
    titulo = models.CharField(max_length=220)
    subtitulo = models.CharField(max_length=220, blank=True, default="")
    autor = models.CharField(max_length=180, blank=True, default="")
    editora = models.CharField(max_length=180, blank=True, default="")
    edicao = models.CharField(max_length=40, blank=True, default="")
    ano_publicacao = models.PositiveIntegerField(null=True, blank=True)
    isbn = models.CharField(max_length=40, blank=True, default="")
    categoria = models.CharField(max_length=120, blank=True, default="")
    assunto = models.CharField(max_length=140, blank=True, default="")
    idioma = models.CharField(max_length=60, blank=True, default="Português")
    descricao = models.TextField(blank=True, default="")
    capa = models.ImageField(upload_to="biblioteca/capas/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Livro da biblioteca"
        verbose_name_plural = "Livros da biblioteca"
        ordering = ["titulo", "id"]
        indexes = [
            models.Index(fields=["biblioteca", "status"]),
            models.Index(fields=["titulo"]),
            models.Index(fields=["autor"]),
            models.Index(fields=["isbn"]),
        ]

    def __str__(self) -> str:
        return self.titulo

    @property
    def exemplares_disponiveis(self) -> int:
        return self.exemplares.filter(status=BibliotecaExemplar.Status.DISPONIVEL).count()


class BibliotecaExemplar(models.Model):
    class Status(models.TextChoices):
        DISPONIVEL = "DISPONIVEL", "Disponível"
        EMPRESTADO = "EMPRESTADO", "Emprestado"
        RESERVADO = "RESERVADO", "Reservado"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        PERDIDO = "PERDIDO", "Perdido"
        BAIXADO = "BAIXADO", "Baixado"

    class CondicaoFisica(models.TextChoices):
        OTIMA = "OTIMA", "Ótima"
        BOA = "BOA", "Boa"
        REGULAR = "REGULAR", "Regular"
        DANIFICADO = "DANIFICADO", "Danificado"

    livro = models.ForeignKey(
        "educacao.BibliotecaLivro",
        on_delete=models.PROTECT,
        related_name="exemplares",
    )
    codigo_exemplar = models.CharField(max_length=40)
    tombo = models.CharField(max_length=40, blank=True, default="")
    localizacao_estante = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DISPONIVEL, db_index=True)
    condicao_fisica = models.CharField(
        max_length=20,
        choices=CondicaoFisica.choices,
        default=CondicaoFisica.BOA,
        db_index=True,
    )
    data_aquisicao = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exemplar da biblioteca"
        verbose_name_plural = "Exemplares da biblioteca"
        ordering = ["livro__titulo", "codigo_exemplar"]
        constraints = [
            models.UniqueConstraint(
                fields=["livro", "codigo_exemplar"],
                name="uniq_exemplar_por_livro_codigo",
            )
        ]
        indexes = [
            models.Index(fields=["livro", "status"]),
            models.Index(fields=["tombo"]),
            models.Index(fields=["codigo_exemplar"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo_exemplar} • {self.livro.titulo}"


class BibliotecaEmprestimo(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        DEVOLVIDO = "DEVOLVIDO", "Devolvido"
        ATRASADO = "ATRASADO", "Atrasado"
        PERDIDO = "PERDIDO", "Perdido"
        CANCELADO = "CANCELADO", "Cancelado"
        RENOVADO = "RENOVADO", "Renovado"

    biblioteca = models.ForeignKey(
        "educacao.BibliotecaEscolar",
        on_delete=models.PROTECT,
        related_name="emprestimos",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="emprestimos_biblioteca",
    )
    matricula_institucional = models.ForeignKey(
        "educacao.MatriculaInstitucional",
        on_delete=models.PROTECT,
        related_name="emprestimos_biblioteca",
    )
    livro = models.ForeignKey(
        "educacao.BibliotecaLivro",
        on_delete=models.PROTECT,
        related_name="emprestimos",
    )
    exemplar = models.ForeignKey(
        "educacao.BibliotecaExemplar",
        on_delete=models.PROTECT,
        related_name="emprestimos",
    )
    data_emprestimo = models.DateField(default=timezone.localdate, db_index=True)
    data_prevista_devolucao = models.DateField(db_index=True)
    data_devolucao_real = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO, db_index=True)
    renovacoes = models.PositiveSmallIntegerField(default=0)
    observacoes = models.TextField(blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emprestimos_biblioteca_registrados",
    )
    devolucao_registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emprestimos_biblioteca_devolvidos",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empréstimo da biblioteca"
        verbose_name_plural = "Empréstimos da biblioteca"
        ordering = ["-data_emprestimo", "-id"]
        indexes = [
            models.Index(fields=["biblioteca", "status"]),
            models.Index(fields=["aluno", "status"]),
            models.Index(fields=["matricula_institucional", "status"]),
            models.Index(fields=["exemplar", "status"]),
            models.Index(fields=["data_prevista_devolucao", "status"]),
        ]

    def clean(self):
        errors = {}
        if self.matricula_institucional_id and self.aluno_id:
            if self.matricula_institucional.aluno_id != self.aluno_id:
                errors["matricula_institucional"] = "A matrícula institucional informada não pertence ao aluno."
        if self.exemplar_id and self.livro_id and self.exemplar.livro_id != self.livro_id:
            errors["exemplar"] = "O exemplar informado não pertence ao livro selecionado."
        if self.data_devolucao_real and self.data_prevista_devolucao and self.data_devolucao_real < self.data_emprestimo:
            errors["data_devolucao_real"] = "A devolução real não pode ser anterior ao empréstimo."
        if errors:
            raise ValidationError(errors)

    @property
    def em_atraso(self) -> bool:
        if self.status not in {self.Status.ATIVO, self.Status.RENOVADO, self.Status.ATRASADO}:
            return False
        return bool(self.data_prevista_devolucao and self.data_prevista_devolucao < timezone.localdate())

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.exemplar.codigo_exemplar} • {self.get_status_display()}"


class BibliotecaReserva(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"
        EXPIRADA = "EXPIRADA", "Expirada"

    biblioteca = models.ForeignKey(
        "educacao.BibliotecaEscolar",
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="reservas_biblioteca",
    )
    matricula_institucional = models.ForeignKey(
        "educacao.MatriculaInstitucional",
        on_delete=models.PROTECT,
        related_name="reservas_biblioteca",
    )
    livro = models.ForeignKey(
        "educacao.BibliotecaLivro",
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    exemplar = models.ForeignKey(
        "educacao.BibliotecaExemplar",
        on_delete=models.PROTECT,
        related_name="reservas",
        null=True,
        blank=True,
    )
    data_reserva = models.DateField(default=timezone.localdate, db_index=True)
    data_expiracao = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA, db_index=True)
    observacoes = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_biblioteca_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reserva da biblioteca"
        verbose_name_plural = "Reservas da biblioteca"
        ordering = ["-data_reserva", "-id"]
        indexes = [
            models.Index(fields=["biblioteca", "status"]),
            models.Index(fields=["aluno", "status"]),
            models.Index(fields=["livro", "status"]),
            models.Index(fields=["exemplar", "status"]),
            models.Index(fields=["data_expiracao", "status"]),
        ]

    def clean(self):
        errors = {}
        if self.matricula_institucional_id and self.aluno_id:
            if self.matricula_institucional.aluno_id != self.aluno_id:
                errors["matricula_institucional"] = "A matrícula institucional não pertence ao aluno informado."
        if self.exemplar_id and self.livro_id and self.exemplar.livro_id != self.livro_id:
            errors["exemplar"] = "O exemplar informado não pertence ao livro selecionado."
        if self.data_expiracao and self.data_reserva and self.data_expiracao < self.data_reserva:
            errors["data_expiracao"] = "A data de expiração não pode ser anterior à data da reserva."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.livro.titulo} • {self.get_status_display()}"


class BibliotecaBloqueio(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        ENCERRADO = "ENCERRADO", "Encerrado"
        CANCELADO = "CANCELADO", "Cancelado"

    biblioteca = models.ForeignKey(
        "educacao.BibliotecaEscolar",
        on_delete=models.PROTECT,
        related_name="bloqueios",
        null=True,
        blank=True,
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="bloqueios_biblioteca",
    )
    matricula_institucional = models.ForeignKey(
        "educacao.MatriculaInstitucional",
        on_delete=models.PROTECT,
        related_name="bloqueios_biblioteca",
        null=True,
        blank=True,
    )
    motivo = models.TextField()
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bloqueios_biblioteca_criados",
    )
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bloqueio de biblioteca"
        verbose_name_plural = "Bloqueios de biblioteca"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["aluno", "status"]),
            models.Index(fields=["matricula_institucional", "status"]),
            models.Index(fields=["biblioteca", "status"]),
            models.Index(fields=["data_inicio", "data_fim"]),
        ]

    def clean(self):
        errors = {}
        if self.data_fim and self.data_inicio and self.data_fim < self.data_inicio:
            errors["data_fim"] = "A data final do bloqueio não pode ser anterior à data inicial."
        if self.matricula_institucional_id and self.aluno_id:
            if self.matricula_institucional.aluno_id != self.aluno_id:
                errors["matricula_institucional"] = "A matrícula institucional não pertence ao aluno informado."
        if errors:
            raise ValidationError(errors)

    def ativo_em(self, ref_date=None) -> bool:
        ref = ref_date or timezone.localdate()
        if self.status != self.Status.ATIVO:
            return False
        if self.data_inicio and ref < self.data_inicio:
            return False
        if self.data_fim and ref > self.data_fim:
            return False
        return True

    def __str__(self) -> str:
        base = self.biblioteca.nome if self.biblioteca_id else "Rede"
        return f"{self.aluno.nome} • {base} • {self.get_status_display()}"
