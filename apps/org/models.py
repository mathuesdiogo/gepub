from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Municipio(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    uf = models.CharField(max_length=2, default="MA")
    slug_site = models.SlugField(
        "Slug do portal",
        max_length=90,
        unique=True,
        null=True,
        blank=True,
        help_text="Usado no domínio público: slug.gepub.com.br",
    )
    dominio_personalizado = models.CharField(
        "Domínio personalizado",
        max_length=190,
        blank=True,
        default="",
        help_text="Opcional. Ex.: prefeitura.seumunicipio.gov.br",
    )

    # Dados da Prefeitura
    cnpj_prefeitura = models.CharField("CNPJ da Prefeitura", max_length=18, blank=True, default="")
    razao_social_prefeitura = models.CharField("Razão Social", max_length=180, blank=True, default="")
    nome_fantasia_prefeitura = models.CharField("Nome Fantasia", max_length=180, blank=True, default="")
    endereco_prefeitura = models.TextField("Endereço", blank=True, default="")
    telefone_prefeitura = models.CharField("Telefone", max_length=40, blank=True, default="")
    email_prefeitura = models.EmailField("E-mail", blank=True, default="")
    site_prefeitura = models.URLField("Site", blank=True, default="")
    nome_prefeito = models.CharField("Prefeito(a)", max_length=160, blank=True, default="")

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Município"
        verbose_name_plural = "Municípios"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["uf"]),
            models.Index(fields=["slug_site"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome}/{self.uf}"

    @property
    def dominio_publico(self) -> str:
        root = (getattr(settings, "GEPUB_PUBLIC_ROOT_DOMAIN", "") or "").strip().lower().strip(".")
        slug = (self.slug_site or "").strip().lower()
        if not slug or not root:
            return ""
        return f"{slug}.{root}"

    def _ensure_slug_site(self) -> None:
        raw_slug = (self.slug_site or "").strip().lower()
        if raw_slug:
            base = slugify(raw_slug).strip("-")
        else:
            base = slugify(self.nome or "").strip("-")
            if not base:
                base = "municipio"

        candidate = base[:90]
        i = 2
        qs = type(self).objects.exclude(pk=self.pk)
        while qs.filter(slug_site=candidate).exists():
            suffix = f"-{i}"
            candidate = f"{base[: max(1, 90 - len(suffix))]}{suffix}"
            i += 1
        self.slug_site = candidate

    def save(self, *args, **kwargs):
        self._ensure_slug_site()
        super().save(*args, **kwargs)


class Secretaria(models.Model):
    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        related_name="secretarias",
    )
    nome = models.CharField(max_length=160)
    sigla = models.CharField(max_length=30, blank=True, default="")
    tipo_modelo = models.CharField(max_length=40, blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Secretaria"
        verbose_name_plural = "Secretarias"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "nome"],
                name="uniq_secretaria_por_municipio",
            )
        ]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["tipo_modelo"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome

    @property
    def apps_ativos(self) -> list[str]:
        return list(self.modulos_ativos.filter(ativo=True).values_list("modulo", flat=True))


class Unidade(models.Model):
    """
    Unidade institucional da prefeitura.

    IMPORTANTE: aqui 'tipo' representa o MÓDULO/SECRETARIA (Educação, Saúde, etc.),
    pois é isso que permite o GEPUB ser multi-secretaria com base única.
    """
    class Tipo(models.TextChoices):
        ADMINISTRACAO = "ADMINISTRACAO", "Administração"
        EDUCACAO = "EDUCACAO", "Educação"
        SAUDE = "SAUDE", "Saúde"
        AGRICULTURA = "AGRICULTURA", "Agricultura"
        FINANCAS = "FINANCAS", "Finanças/Fazenda"
        PLANEJAMENTO = "PLANEJAMENTO", "Planejamento/Controle"
        TECNOLOGIA = "TECNOLOGIA", "Tecnologia/Inovação"
        MEIO_AMBIENTE = "MEIO_AMBIENTE", "Meio Ambiente"
        TRANSPORTE = "TRANSPORTE", "Transporte/Mobilidade"
        CULTURA = "CULTURA", "Cultura/Turismo/Esporte"
        DESENVOLVIMENTO = "DESENVOLVIMENTO", "Desenvolvimento Econômico"
        HABITACAO = "HABITACAO", "Habitação/Urbanismo"
        SERVICOS_PUBLICOS = "SERVICOS_PUBLICOS", "Serviços Públicos"
        INFRAESTRUTURA = "INFRAESTRUTURA", "Infraestrutura"
        ASSISTENCIA = "ASSISTENCIA", "Assistência Social"
        OUTROS = "OUTROS", "Outros"

    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.PROTECT,
        related_name="unidades",
        null=True,
        blank=True,
    )

    nome = models.CharField(max_length=180, default="", blank=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.EDUCACAO)

    # Identificadores / registros (opcionais)
    codigo_inep = models.CharField("Código INEP", max_length=32, blank=True, default="")
    cnpj = models.CharField("CNPJ", max_length=32, blank=True, default="")

    # Contato / endereço (opcionais)
    email = models.EmailField("E-mail", blank=True, default="")
    telefone = models.CharField("Telefone", max_length=40, blank=True, default="")
    endereco = models.TextField("Endereço", blank=True, default="")

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["secretaria", "nome"],
                name="uniq_unidade_por_secretaria",
            )
        ]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["codigo_inep"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome or f"Unidade #{self.pk}"


class Setor(models.Model):
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="setores",
    )
    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "nome"],
                name="uniq_setor_por_unidade",
            )
        ]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.unidade})"


class SecretariaTemplate(models.Model):
    class Modulo(models.TextChoices):
        EDUCACAO = "educacao", "Educação"
        SAUDE = "saude", "Saúde/Clínico"
        OBRAS = "obras", "Obras/Engenharia"
        ADMINISTRACAO = "administracao", "Administração"
        FINANCAS = "financas", "Finanças/Fazenda"
        PLANEJAMENTO = "planejamento", "Planejamento/Controle Interno"
        AGRICULTURA = "agricultura", "Agricultura"
        TECNOLOGIA = "tecnologia", "Tecnologia/Inovação"
        ASSISTENCIA = "assistencia", "Assistência Social"
        MEIO_AMBIENTE = "meio_ambiente", "Meio Ambiente"
        TRANSPORTE = "transporte", "Transporte/Mobilidade"
        CULTURA = "cultura", "Cultura/Turismo/Esporte"
        DESENVOLVIMENTO = "desenvolvimento", "Desenvolvimento Econômico"
        HABITACAO = "habitacao", "Habitação/Urbanismo"
        SERVICOS_PUBLICOS = "servicos_publicos", "Serviços Públicos"
        OUTRO = "outro", "Outro"

    slug = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=140)
    descricao = models.TextField(blank=True, default="")
    modulo = models.CharField(max_length=20, choices=Modulo.choices, default=Modulo.OUTRO)
    ativo = models.BooleanField(default=True)

    criar_unidade_base = models.BooleanField(default=True)
    nome_unidade_base = models.CharField(max_length=140, default="Sede Administrativa")
    tipo_unidade_base = models.CharField(
        max_length=20,
        choices=Unidade.Tipo.choices,
        default=Unidade.Tipo.OUTROS,
    )

    perfis_padrao = models.JSONField(default=list, blank=True)
    onboarding_padrao = models.JSONField(default=list, blank=True)
    modulos_ativos_padrao = models.JSONField(default=list, blank=True)
    configuracoes_padrao = models.JSONField(default=list, blank=True)
    cadastros_base_padrao = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template de secretaria"
        verbose_name_plural = "Templates de secretaria"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["modulo", "ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome


class SecretariaTemplateItem(models.Model):
    class Tipo(models.TextChoices):
        SETOR = "SETOR", "Setor padrão"
        UNIDADE = "UNIDADE", "Unidade padrão"
        CARGO = "CARGO", "Cargo/Função padrão"

    template = models.ForeignKey(
        SecretariaTemplate,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.SETOR)
    nome = models.CharField(max_length=140)
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Item do template de secretaria"
        verbose_name_plural = "Itens do template de secretaria"
        ordering = ["template__nome", "ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "tipo", "nome"],
                name="uniq_item_template_tipo_nome",
            )
        ]
        indexes = [
            models.Index(fields=["tipo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.template.nome} • {self.get_tipo_display()} • {self.nome}"


class SecretariaConfiguracao(models.Model):
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.CASCADE,
        related_name="configuracoes",
    )
    chave = models.CharField(max_length=80)
    descricao = models.CharField(max_length=220, blank=True, default="")
    valor = models.JSONField(default=dict, blank=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secretaria_configuracoes_atualizadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração da secretaria"
        verbose_name_plural = "Configurações da secretaria"
        ordering = ["secretaria__nome", "chave"]
        constraints = [
            models.UniqueConstraint(
                fields=["secretaria", "chave"],
                name="uniq_secretaria_config_chave",
            )
        ]
        indexes = [
            models.Index(fields=["chave"]),
        ]

    def __str__(self) -> str:
        return f"{self.secretaria} • {self.chave}"


class SecretariaCadastroBase(models.Model):
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.CASCADE,
        related_name="cadastros_base",
    )
    categoria = models.CharField(max_length=60, default="GERAL")
    codigo = models.CharField(max_length=40, blank=True, default="")
    nome = models.CharField(max_length=180)
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cadastro-base da secretaria"
        verbose_name_plural = "Cadastros-base da secretaria"
        ordering = ["secretaria__nome", "categoria", "ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["secretaria", "categoria", "nome"],
                name="uniq_secretaria_cadastro_base",
            )
        ]
        indexes = [
            models.Index(fields=["categoria", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.secretaria} • {self.categoria} • {self.nome}"


class MunicipioModuloAtivo(models.Model):
    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.CASCADE,
        related_name="modulos_ativos",
    )
    modulo = models.CharField(max_length=30)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Módulo ativo do município"
        verbose_name_plural = "Módulos ativos do município"
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "modulo"],
                name="uniq_municipio_modulo_ativo",
            )
        ]
        indexes = [
            models.Index(fields=["modulo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.modulo}"


class SecretariaModuloAtivo(models.Model):
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.CASCADE,
        related_name="modulos_ativos",
    )
    modulo = models.CharField(max_length=30)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Módulo ativo da secretaria"
        verbose_name_plural = "Módulos ativos da secretaria"
        constraints = [
            models.UniqueConstraint(
                fields=["secretaria", "modulo"],
                name="uniq_secretaria_modulo_ativo",
            )
        ]
        indexes = [
            models.Index(fields=["modulo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.secretaria} • {self.modulo}"


class SecretariaProvisionamento(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_PROCESSAMENTO = "EM_PROCESSAMENTO", "Em processamento"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        ERRO = "ERRO", "Erro"

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.CASCADE,
        related_name="provisionamentos_secretarias",
    )
    template = models.ForeignKey(
        SecretariaTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provisionamentos",
    )
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provisionamentos",
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provisionamentos_secretarias_solicitados",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    log = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Provisionamento de secretaria"
        verbose_name_plural = "Provisionamentos de secretaria"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["status", "criado_em"]),
            models.Index(fields=["municipio", "template"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.template or 'Template removido'} • {self.status}"


class OnboardingStep(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_PROGRESSO = "EM_PROGRESSO", "Em progresso"
        CONCLUIDO = "CONCLUIDO", "Concluído"

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.CASCADE,
        related_name="onboarding_steps",
    )
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="onboarding_steps",
    )
    modulo = models.CharField(max_length=30)
    codigo = models.CharField(max_length=40)
    titulo = models.CharField(max_length=160)
    descricao = models.TextField(blank=True, default="")
    ordem = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    url_name = models.CharField(max_length=120, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Passo de onboarding"
        verbose_name_plural = "Passos de onboarding"
        ordering = ["modulo", "ordem", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "secretaria", "modulo", "codigo"],
                name="uniq_onboarding_step_scope",
            )
        ]
        indexes = [
            models.Index(fields=["municipio", "modulo", "status"]),
            models.Index(fields=["secretaria", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.modulo} • {self.titulo}"
