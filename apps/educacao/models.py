from django.conf import settings
from django.core.exceptions import ValidationError
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


class MatrizCurricular(models.Model):
    class EtapaBase(models.TextChoices):
        EDUCACAO_INFANTIL = "EDUCACAO_INFANTIL", "Educação Infantil"
        FUNDAMENTAL_ANOS_INICIAIS = "FUNDAMENTAL_ANOS_INICIAIS", "Ensino Fundamental (Anos Iniciais)"
        FUNDAMENTAL_ANOS_FINAIS = "FUNDAMENTAL_ANOS_FINAIS", "Ensino Fundamental (Anos Finais)"

    class SerieAno(models.TextChoices):
        INFANTIL_BERCARIO = "INFANTIL_BERCARIO", "Berçário"
        INFANTIL_MATERNAL_I = "INFANTIL_MATERNAL_I", "Maternal I"
        INFANTIL_MATERNAL_II = "INFANTIL_MATERNAL_II", "Maternal II"
        INFANTIL_JARDIM_I = "INFANTIL_JARDIM_I", "Jardim I"
        INFANTIL_JARDIM_II = "INFANTIL_JARDIM_II", "Jardim II"
        FUNDAMENTAL_1 = "FUNDAMENTAL_1", "1º ano"
        FUNDAMENTAL_2 = "FUNDAMENTAL_2", "2º ano"
        FUNDAMENTAL_3 = "FUNDAMENTAL_3", "3º ano"
        FUNDAMENTAL_4 = "FUNDAMENTAL_4", "4º ano"
        FUNDAMENTAL_5 = "FUNDAMENTAL_5", "5º ano"
        FUNDAMENTAL_6 = "FUNDAMENTAL_6", "6º ano"
        FUNDAMENTAL_7 = "FUNDAMENTAL_7", "7º ano"
        FUNDAMENTAL_8 = "FUNDAMENTAL_8", "8º ano"
        FUNDAMENTAL_9 = "FUNDAMENTAL_9", "9º ano"

    nome = models.CharField(max_length=180)
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="matrizes_curriculares",
    )
    etapa_base = models.CharField(max_length=40, choices=EtapaBase.choices, db_index=True)
    serie_ano = models.CharField(max_length=40, choices=SerieAno.choices, db_index=True)
    ano_referencia = models.PositiveIntegerField(default=timezone.localdate().year, db_index=True)
    carga_horaria_anual = models.PositiveIntegerField(default=800)
    dias_letivos_previstos = models.PositiveSmallIntegerField(default=200)
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Matriz curricular"
        verbose_name_plural = "Matrizes curriculares"
        ordering = ["-ano_referencia", "etapa_base", "serie_ano", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "etapa_base", "serie_ano", "ano_referencia", "nome"],
                name="uniq_matriz_unidade_etapa_serie_ano_nome",
            )
        ]
        indexes = [
            models.Index(fields=["unidade", "ativo"]),
            models.Index(fields=["etapa_base", "serie_ano"]),
            models.Index(fields=["ano_referencia"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} • {self.get_serie_ano_display()} • {self.ano_referencia}"


class MatrizComponente(models.Model):
    matriz = models.ForeignKey(
        "educacao.MatrizCurricular",
        on_delete=models.CASCADE,
        related_name="componentes",
    )
    componente = models.ForeignKey(
        "educacao.ComponenteCurricular",
        on_delete=models.PROTECT,
        related_name="matrizes",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    carga_horaria_anual = models.PositiveIntegerField(default=0)
    aulas_semanais = models.PositiveSmallIntegerField(default=0)
    obrigatoria = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Componente da matriz"
        verbose_name_plural = "Componentes da matriz"
        ordering = ["matriz", "ordem", "componente__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["matriz", "componente"],
                name="uniq_matriz_componente",
            )
        ]
        indexes = [
            models.Index(fields=["matriz", "ordem"]),
            models.Index(fields=["matriz", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.matriz} • {self.componente}"


class MatrizComponenteRelacao(models.Model):
    class Tipo(models.TextChoices):
        PRE_REQUISITO = "PRE_REQUISITO", "Pré-requisito"
        CO_REQUISITO = "CO_REQUISITO", "Co-requisito"
        EQUIVALENCIA = "EQUIVALENCIA", "Equivalência"

    origem = models.ForeignKey(
        "educacao.MatrizComponente",
        on_delete=models.CASCADE,
        related_name="relacoes_origem",
    )
    destino = models.ForeignKey(
        "educacao.MatrizComponente",
        on_delete=models.CASCADE,
        related_name="relacoes_destino",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_index=True)
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Relação entre componentes da matriz"
        verbose_name_plural = "Relações entre componentes da matriz"
        ordering = ["tipo", "origem__ordem", "destino__ordem", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["origem", "destino", "tipo"],
                name="uniq_matriz_comp_relacao",
            )
        ]
        indexes = [
            models.Index(fields=["origem", "tipo"]),
            models.Index(fields=["destino", "tipo"]),
            models.Index(fields=["ativo"]),
        ]

    def clean(self):
        errors = {}
        if self.origem_id and self.destino_id:
            if self.origem_id == self.destino_id:
                errors["destino"] = "O componente de destino não pode ser o mesmo da origem."
            if self.origem.matriz_id != self.destino.matriz_id:
                errors["destino"] = "Origem e destino devem pertencer à mesma matriz curricular."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.get_tipo_display()}: {self.origem} -> {self.destino}"


class MatrizComponenteEquivalenciaGrupo(models.Model):
    matriz = models.ForeignKey(
        "educacao.MatrizCurricular",
        on_delete=models.CASCADE,
        related_name="grupos_equivalencia",
    )
    nome = models.CharField(max_length=120)
    minimo_componentes = models.PositiveSmallIntegerField(
        default=1,
        help_text="Quantidade mínima de componentes equivalentes aceitos para validação.",
    )
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Grupo de equivalência da matriz"
        verbose_name_plural = "Grupos de equivalência da matriz"
        ordering = ["nome", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["matriz", "nome"],
                name="uniq_matriz_equiv_grupo_nome",
            ),
        ]
        indexes = [
            models.Index(fields=["matriz", "ativo"]),
        ]

    def clean(self):
        errors = {}
        if self.minimo_componentes < 1:
            errors["minimo_componentes"] = "Informe pelo menos 1 componente mínimo."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.matriz} • {self.nome}"


class MatrizComponenteEquivalenciaItem(models.Model):
    grupo = models.ForeignKey(
        "educacao.MatrizComponenteEquivalenciaGrupo",
        on_delete=models.CASCADE,
        related_name="itens",
    )
    componente = models.ForeignKey(
        "educacao.MatrizComponente",
        on_delete=models.CASCADE,
        related_name="equivalencias",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Item de equivalência da matriz"
        verbose_name_plural = "Itens de equivalência da matriz"
        ordering = ["grupo", "ordem", "componente__ordem", "componente__componente__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["grupo", "componente"],
                name="uniq_grupo_equiv_componente",
            ),
        ]
        indexes = [
            models.Index(fields=["grupo", "ordem"]),
            models.Index(fields=["grupo", "ativo"]),
        ]

    def clean(self):
        errors = {}
        if self.grupo_id and self.componente_id:
            if self.grupo.matriz_id != self.componente.matriz_id:
                errors["componente"] = "O componente deve pertencer à mesma matriz do grupo de equivalência."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.grupo.nome} • {self.componente.componente.nome}"


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

    class SerieAno(models.TextChoices):
        INFANTIL_BERCARIO = "INFANTIL_BERCARIO", "Berçário"
        INFANTIL_MATERNAL_I = "INFANTIL_MATERNAL_I", "Maternal I"
        INFANTIL_MATERNAL_II = "INFANTIL_MATERNAL_II", "Maternal II"
        INFANTIL_JARDIM_I = "INFANTIL_JARDIM_I", "Jardim I"
        INFANTIL_JARDIM_II = "INFANTIL_JARDIM_II", "Jardim II"
        FUNDAMENTAL_1 = "FUNDAMENTAL_1", "1º ano"
        FUNDAMENTAL_2 = "FUNDAMENTAL_2", "2º ano"
        FUNDAMENTAL_3 = "FUNDAMENTAL_3", "3º ano"
        FUNDAMENTAL_4 = "FUNDAMENTAL_4", "4º ano"
        FUNDAMENTAL_5 = "FUNDAMENTAL_5", "5º ano"
        FUNDAMENTAL_6 = "FUNDAMENTAL_6", "6º ano"
        FUNDAMENTAL_7 = "FUNDAMENTAL_7", "7º ano"
        FUNDAMENTAL_8 = "FUNDAMENTAL_8", "8º ano"
        FUNDAMENTAL_9 = "FUNDAMENTAL_9", "9º ano"
        NAO_APLICA = "NAO_APLICA", "Não se aplica"

    SERIES_INFANTIL_CRECHE = {
        SerieAno.INFANTIL_BERCARIO,
        SerieAno.INFANTIL_MATERNAL_I,
        SerieAno.INFANTIL_MATERNAL_II,
    }
    SERIES_INFANTIL_PRE_ESCOLA = {
        SerieAno.INFANTIL_JARDIM_I,
        SerieAno.INFANTIL_JARDIM_II,
    }
    SERIES_FUNDAMENTAL_INICIAIS = {
        SerieAno.FUNDAMENTAL_1,
        SerieAno.FUNDAMENTAL_2,
        SerieAno.FUNDAMENTAL_3,
        SerieAno.FUNDAMENTAL_4,
        SerieAno.FUNDAMENTAL_5,
    }
    SERIES_FUNDAMENTAL_FINAIS = {
        SerieAno.FUNDAMENTAL_6,
        SerieAno.FUNDAMENTAL_7,
        SerieAno.FUNDAMENTAL_8,
        SerieAno.FUNDAMENTAL_9,
    }

    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    @classmethod
    def modalidades_motor_principal_choices(cls):
        return [
            (cls.Modalidade.EDUCACAO_INFANTIL, dict(cls.Modalidade.choices)[cls.Modalidade.EDUCACAO_INFANTIL]),
            (cls.Modalidade.REGULAR, dict(cls.Modalidade.choices)[cls.Modalidade.REGULAR]),
            (cls.Modalidade.ATIVIDADE_COMPLEMENTAR, dict(cls.Modalidade.choices)[cls.Modalidade.ATIVIDADE_COMPLEMENTAR]),
        ]

    @classmethod
    def etapas_motor_principal_choices(cls):
        return [
            (cls.Etapa.CRECHE, dict(cls.Etapa.choices)[cls.Etapa.CRECHE]),
            (cls.Etapa.PRE_ESCOLA, dict(cls.Etapa.choices)[cls.Etapa.PRE_ESCOLA]),
            (
                cls.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
                dict(cls.Etapa.choices)[cls.Etapa.FUNDAMENTAL_ANOS_INICIAIS],
            ),
            (
                cls.Etapa.FUNDAMENTAL_ANOS_FINAIS,
                dict(cls.Etapa.choices)[cls.Etapa.FUNDAMENTAL_ANOS_FINAIS],
            ),
            (cls.Etapa.AEE, dict(cls.Etapa.choices)[cls.Etapa.AEE]),
        ]

    @classmethod
    def series_motor_principal_choices(cls):
        allowed = set(cls.SERIES_INFANTIL_CRECHE | cls.SERIES_INFANTIL_PRE_ESCOLA | cls.SERIES_FUNDAMENTAL_INICIAIS | cls.SERIES_FUNDAMENTAL_FINAIS | {cls.SerieAno.NAO_APLICA})
        return [(value, label) for value, label in cls.SerieAno.choices if value in allowed]

    @classmethod
    def expected_serie_from_matriz(cls, matriz):
        serie_map = {
            MatrizCurricular.SerieAno.INFANTIL_BERCARIO: cls.SerieAno.INFANTIL_BERCARIO,
            MatrizCurricular.SerieAno.INFANTIL_MATERNAL_I: cls.SerieAno.INFANTIL_MATERNAL_I,
            MatrizCurricular.SerieAno.INFANTIL_MATERNAL_II: cls.SerieAno.INFANTIL_MATERNAL_II,
            MatrizCurricular.SerieAno.INFANTIL_JARDIM_I: cls.SerieAno.INFANTIL_JARDIM_I,
            MatrizCurricular.SerieAno.INFANTIL_JARDIM_II: cls.SerieAno.INFANTIL_JARDIM_II,
            MatrizCurricular.SerieAno.FUNDAMENTAL_1: cls.SerieAno.FUNDAMENTAL_1,
            MatrizCurricular.SerieAno.FUNDAMENTAL_2: cls.SerieAno.FUNDAMENTAL_2,
            MatrizCurricular.SerieAno.FUNDAMENTAL_3: cls.SerieAno.FUNDAMENTAL_3,
            MatrizCurricular.SerieAno.FUNDAMENTAL_4: cls.SerieAno.FUNDAMENTAL_4,
            MatrizCurricular.SerieAno.FUNDAMENTAL_5: cls.SerieAno.FUNDAMENTAL_5,
            MatrizCurricular.SerieAno.FUNDAMENTAL_6: cls.SerieAno.FUNDAMENTAL_6,
            MatrizCurricular.SerieAno.FUNDAMENTAL_7: cls.SerieAno.FUNDAMENTAL_7,
            MatrizCurricular.SerieAno.FUNDAMENTAL_8: cls.SerieAno.FUNDAMENTAL_8,
            MatrizCurricular.SerieAno.FUNDAMENTAL_9: cls.SerieAno.FUNDAMENTAL_9,
        }
        return serie_map.get(getattr(matriz, "serie_ano", None))

    @classmethod
    def expected_etapa_from_matriz(cls, matriz):
        if getattr(matriz, "etapa_base", None) == MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL:
            serie = cls.expected_serie_from_matriz(matriz)
            if serie in cls.SERIES_INFANTIL_CRECHE:
                return cls.Etapa.CRECHE
            return cls.Etapa.PRE_ESCOLA
        if getattr(matriz, "etapa_base", None) == MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_INICIAIS:
            return cls.Etapa.FUNDAMENTAL_ANOS_INICIAIS
        if getattr(matriz, "etapa_base", None) == MatrizCurricular.EtapaBase.FUNDAMENTAL_ANOS_FINAIS:
            return cls.Etapa.FUNDAMENTAL_ANOS_FINAIS
        return None

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
    serie_ano = models.CharField(
        max_length=40,
        choices=SerieAno.choices,
        default=SerieAno.FUNDAMENTAL_1,
        db_index=True,
    )
    matriz_curricular = models.ForeignKey(
        "educacao.MatrizCurricular",
        on_delete=models.SET_NULL,
        related_name="turmas",
        null=True,
        blank=True,
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
            models.Index(fields=["serie_ano"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.ano_letivo})"

    def clean(self):
        errors = {}

        if self.modalidade == self.Modalidade.ATIVIDADE_COMPLEMENTAR:
            if not self.curso_id:
                errors["curso"] = "Para atividade complementar, selecione o curso/atividade extracurricular."
            if self.matriz_curricular_id:
                errors["matriz_curricular"] = "Atividade complementar não usa matriz curricular principal."
            self.serie_ano = self.SerieAno.NAO_APLICA
        else:
            if not self.matriz_curricular_id:
                errors["matriz_curricular"] = "Selecione a matriz curricular da turma."
            if self.curso_id:
                errors["curso"] = "Turma regular não deve usar curso extracurricular."

        if self.matriz_curricular_id:
            matriz = self.matriz_curricular
            if self.unidade_id and matriz.unidade_id != self.unidade_id:
                errors["matriz_curricular"] = "A matriz selecionada pertence a outra unidade."

            expected_serie = self.expected_serie_from_matriz(matriz)
            if expected_serie and self.serie_ano not in {expected_serie, self.SerieAno.NAO_APLICA}:
                errors["serie_ano"] = "A série/ano não corresponde à matriz curricular selecionada."

            expected_etapa = self.expected_etapa_from_matriz(matriz)
            if expected_etapa and self.etapa != expected_etapa:
                errors["etapa"] = "A etapa da turma não corresponde à etapa da matriz curricular."

        if errors:
            raise ValidationError(errors)


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
        TRANCADO = "TRANCADO", "Trancado"
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
        TRANCAMENTO = "TRANCAMENTO", "Trancamento"
        REATIVACAO = "REATIVACAO", "Reativação"
        DESFAZER = "DESFAZER", "Desfazer procedimento"
        SITUACAO = "SITUACAO", "Mudança de situação"

    class TipoTrancamento(models.TextChoices):
        VOLUNTARIO = "VOLUNTARIO", "Voluntário"
        COMPULSORIO = "COMPULSORIO", "Compulsório"
        INTERCAMBIO = "INTERCAMBIO", "Intercâmbio"
        OUTRO = "OUTRO", "Outro"

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
    movimentacao_desfeita = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="desfeita_por",
    )

    situacao_anterior = models.CharField(max_length=20, blank=True, default="")
    situacao_nova = models.CharField(max_length=20, blank=True, default="")
    data_referencia = models.DateField(null=True, blank=True)
    tipo_trancamento = models.CharField(max_length=20, choices=TipoTrancamento.choices, blank=True, default="")
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


class RenovacaoMatricula(models.Model):
    class Etapa(models.TextChoices):
        AGENDADA = "AGENDADA", "Agendada"
        AGUARDANDO_MATRICULA = "AGUARDANDO_MATRICULA", "Aguardando matrícula"
        AGUARDANDO_PROCESSAMENTO = "AGUARDANDO_PROCESSAMENTO", "Aguardando processamento"
        PROCESSADA = "PROCESSADA", "Processada"
        INATIVA = "INATIVA", "Inativa"

    descricao = models.CharField(max_length=220)
    ano_letivo = models.PositiveIntegerField(db_index=True)
    periodo_letivo = models.ForeignKey(
        "educacao.PeriodoLetivo",
        on_delete=models.SET_NULL,
        related_name="renovacoes_matricula",
        null=True,
        blank=True,
    )
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="renovacoes_matricula",
    )
    data_inicio = models.DateField(db_index=True)
    data_fim = models.DateField(db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)
    observacao = models.TextField(blank=True, default="")
    processado_em = models.DateTimeField(null=True, blank=True, db_index=True)
    processado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renovacoes_matricula_processadas",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renovacoes_matricula_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Renovação de matrícula"
        verbose_name_plural = "Renovações de matrícula"
        ordering = ["-ano_letivo", "-data_inicio", "-id"]
        indexes = [
            models.Index(fields=["secretaria", "ano_letivo"]),
            models.Index(fields=["secretaria", "ativo"]),
            models.Index(fields=["data_inicio", "data_fim"]),
        ]

    def clean(self):
        errors = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            errors["data_fim"] = "A data de término deve ser igual ou posterior à data de início."
        if self.periodo_letivo_id and self.periodo_letivo.ano_letivo != self.ano_letivo:
            errors["periodo_letivo"] = "O período letivo precisa pertencer ao mesmo ano letivo da renovação."
        if errors:
            raise ValidationError(errors)

    def etapa_atual(self, ref_date=None) -> str:
        if not self.ativo:
            return self.Etapa.INATIVA
        if self.processado_em:
            return self.Etapa.PROCESSADA
        today = ref_date or timezone.localdate()
        if today < self.data_inicio:
            return self.Etapa.AGENDADA
        if self.data_inicio <= today <= self.data_fim:
            return self.Etapa.AGUARDANDO_MATRICULA
        return self.Etapa.AGUARDANDO_PROCESSAMENTO

    @property
    def etapa_display(self) -> str:
        etapa = self.etapa_atual()
        return dict(self.Etapa.choices).get(etapa, etapa)

    @property
    def janela_aberta(self) -> bool:
        return self.etapa_atual() == self.Etapa.AGUARDANDO_MATRICULA

    def __str__(self) -> str:
        return f"{self.descricao} • {self.ano_letivo}"


class RenovacaoMatriculaOferta(models.Model):
    renovacao = models.ForeignKey(
        "educacao.RenovacaoMatricula",
        on_delete=models.CASCADE,
        related_name="ofertas",
    )
    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.PROTECT,
        related_name="renovacoes_ofertadas",
    )
    diario = models.ForeignKey(
        "educacao.DiarioTurma",
        on_delete=models.SET_NULL,
        related_name="renovacoes_ofertadas",
        null=True,
        blank=True,
    )
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Oferta de renovação"
        verbose_name_plural = "Ofertas de renovação"
        ordering = ["turma__nome", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["renovacao", "turma"],
                name="uniq_renovacao_oferta_turma",
            ),
        ]
        indexes = [
            models.Index(fields=["renovacao", "ativo"]),
            models.Index(fields=["turma"]),
        ]

    def clean(self):
        errors = {}
        if self.renovacao_id and self.turma_id:
            turma_unidade = getattr(self.turma, "unidade", None)
            turma_secretaria_id = getattr(turma_unidade, "secretaria_id", None)
            if turma_secretaria_id and turma_secretaria_id != self.renovacao.secretaria_id:
                errors["turma"] = "A turma deve pertencer à mesma secretaria da renovação."
            if self.turma.ano_letivo != self.renovacao.ano_letivo:
                errors["turma"] = "A turma deve pertencer ao mesmo ano letivo da renovação."
        if self.diario_id and self.diario.turma_id != self.turma_id:
            errors["diario"] = "O diário selecionado deve pertencer à turma informada."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.renovacao.descricao} • {self.turma.nome}"


class RenovacaoMatriculaPedido(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADO = "APROVADO", "Aprovado"
        REJEITADO = "REJEITADO", "Rejeitado"

    renovacao = models.ForeignKey(
        "educacao.RenovacaoMatricula",
        on_delete=models.CASCADE,
        related_name="pedidos",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="pedidos_renovacao_matricula",
    )
    oferta = models.ForeignKey(
        "educacao.RenovacaoMatriculaOferta",
        on_delete=models.PROTECT,
        related_name="pedidos",
    )
    prioridade = models.PositiveSmallIntegerField(default=1)
    observacao_aluno = models.TextField(blank=True, default="")
    origem_matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.SET_NULL,
        related_name="pedidos_renovacao_origem",
        null=True,
        blank=True,
    )
    processo_administrativo = models.ForeignKey(
        "processos.ProcessoAdministrativo",
        on_delete=models.SET_NULL,
        related_name="pedidos_renovacao",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    observacao_processamento = models.TextField(blank=True, default="")
    processado_em = models.DateTimeField(null=True, blank=True)
    processado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_renovacao_processados",
    )
    matricula_resultante = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.SET_NULL,
        related_name="pedidos_renovacao_resultantes",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido de renovação de matrícula"
        verbose_name_plural = "Pedidos de renovação de matrícula"
        ordering = ["status", "prioridade", "criado_em", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["renovacao", "aluno", "oferta"],
                name="uniq_renovacao_pedido_aluno_oferta",
            ),
        ]
        indexes = [
            models.Index(fields=["renovacao", "status"]),
            models.Index(fields=["aluno", "status"]),
            models.Index(fields=["renovacao", "prioridade"]),
        ]

    def clean(self):
        errors = {}
        if self.oferta_id and self.renovacao_id and self.oferta.renovacao_id != self.renovacao_id:
            errors["oferta"] = "A oferta selecionada deve pertencer à mesma renovação."
        if errors:
            raise ValidationError(errors)

    @property
    def turma(self):
        return getattr(self.oferta, "turma", None)

    def __str__(self) -> str:
        turma_nome = getattr(getattr(self.oferta, "turma", None), "nome", "Turma")
        return f"{self.aluno} • {turma_nome} • {self.get_status_display()}"


class Estagio(models.Model):
    class Tipo(models.TextChoices):
        OBRIGATORIO = "OBRIGATORIO", "Obrigatório"
        NAO_OBRIGATORIO = "NAO_OBRIGATORIO", "Não obrigatório"

    class Situacao(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        APROVADO = "APROVADO", "Aprovado"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        INDEFERIDO = "INDEFERIDO", "Indeferido"
        CANCELADO = "CANCELADO", "Cancelado"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="estagios",
    )
    matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estagios",
    )
    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estagios",
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="estagios_educacao",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OBRIGATORIO, db_index=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.RASCUNHO, db_index=True)
    concedente_nome = models.CharField(max_length=180)
    concedente_cnpj = models.CharField(max_length=18, blank=True, default="")
    supervisor_nome = models.CharField(max_length=140, blank=True, default="")
    orientador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estagios_orientados",
    )
    data_inicio_prevista = models.DateField(null=True, blank=True)
    data_fim_prevista = models.DateField(null=True, blank=True)
    data_inicio_real = models.DateField(null=True, blank=True)
    data_fim_real = models.DateField(null=True, blank=True)
    carga_horaria_total = models.PositiveIntegerField(default=0)
    carga_horaria_cumprida = models.PositiveIntegerField(default=0)
    equivalencia_solicitada = models.BooleanField(default=False)
    equivalencia_aprovada = models.BooleanField(default=False)
    termo_compromisso = models.FileField(upload_to="educacao/estagios/termos/%Y/%m/", blank=True, null=True)
    relatorio_final = models.FileField(upload_to="educacao/estagios/relatorios/%Y/%m/", blank=True, null=True)
    observacao = models.TextField(blank=True, default="")
    cadastrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estagios_cadastrados",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estagios_atualizados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estágio"
        verbose_name_plural = "Estágios"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["unidade", "situacao"]),
            models.Index(fields=["aluno", "tipo"]),
            models.Index(fields=["matricula"]),
            models.Index(fields=["turma"]),
            models.Index(fields=["criado_em"]),
            models.Index(fields=["ativo"]),
        ]

    def clean(self):
        errors = {}

        if self.matricula_id and self.aluno_id and self.matricula.aluno_id != self.aluno_id:
            errors["matricula"] = "A matrícula selecionada não pertence ao aluno informado."

        if self.turma_id and self.matricula_id and self.matricula.turma_id != self.turma_id:
            errors["turma"] = "A turma deve ser a mesma da matrícula vinculada."

        if self.turma_id and self.unidade_id and self.turma.unidade_id != self.unidade_id:
            errors["unidade"] = "A unidade deve ser a mesma da turma selecionada."

        if self.matricula_id and self.unidade_id:
            turma_matricula = getattr(self.matricula, "turma", None)
            if turma_matricula and turma_matricula.unidade_id != self.unidade_id:
                errors["unidade"] = "A unidade deve ser a mesma da matrícula vinculada."

        if self.data_inicio_prevista and self.data_fim_prevista and self.data_fim_prevista < self.data_inicio_prevista:
            errors["data_fim_prevista"] = "A data final prevista não pode ser anterior à data inicial prevista."

        if self.data_inicio_real and self.data_fim_real and self.data_fim_real < self.data_inicio_real:
            errors["data_fim_real"] = "A data final real não pode ser anterior à data inicial real."

        if self.carga_horaria_total and self.carga_horaria_cumprida > self.carga_horaria_total:
            errors["carga_horaria_cumprida"] = "A carga horária cumprida não pode ultrapassar a carga horária total."

        if self.equivalencia_aprovada and not self.equivalencia_solicitada:
            errors["equivalencia_aprovada"] = "Não é possível aprovar equivalência sem solicitação prévia."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.aluno} • {self.get_tipo_display()} • {self.get_situacao_display()}"


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
from . import models_beneficios  # noqa: F401
from . import models_informatica  # noqa: F401
