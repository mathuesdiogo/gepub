from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from urllib.parse import quote_plus


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

    class TipoEducacional(models.TextChoices):
        NAO_APLICA = "NAO_APLICA", "Não se aplica"
        ESCOLA = "ESCOLA", "Escola"
        CRECHE = "CRECHE", "Creche"
        CMEI = "CMEI", "CMEI"
        LABORATORIO = "LABORATORIO", "Sala/Laboratório"
        BIBLIOTECA = "BIBLIOTECA", "Biblioteca Escolar"
        POLO = "POLO", "Polo educacional"
        OUTRA = "OUTRA", "Outra unidade educacional"

    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.PROTECT,
        related_name="unidades",
        null=True,
        blank=True,
    )

    nome = models.CharField(max_length=180, default="", blank=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.EDUCACAO)
    tipo_educacional = models.CharField(
        "Identificação educacional",
        max_length=20,
        choices=TipoEducacional.choices,
        default=TipoEducacional.NAO_APLICA,
        db_index=True,
    )

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


class Address(models.Model):
    class EntityType(models.TextChoices):
        SECRETARIA = "SECRETARIA", "Secretaria"
        UNIDADE = "UNIDADE", "Unidade"
        SETOR = "SETOR", "Setor"
        GARAGEM = "GARAGEM", "Garagem"
        ESCOLA = "ESCOLA", "Escola"
        UBS = "UBS", "UBS"
        ALMOXARIFADO = "ALMOXARIFADO", "Almoxarifado"
        OUTROS = "OUTROS", "Outros"

    class GeocodeProvider(models.TextChoices):
        GOOGLE = "google", "Google"
        OSM = "osm", "OpenStreetMap"
        MANUAL = "manual", "Manual"
        NONE = "none", "Não definido"

    class GeocodeStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        OK = "ok", "OK"
        FAILED = "failed", "Falhou"
        MANUAL = "manual", "Manual"

    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    entity_id = models.PositiveIntegerField()
    label = models.CharField(max_length=80, blank=True, default="Principal")
    is_primary = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)

    cep = models.CharField(max_length=9, blank=True, default="")
    logradouro = models.CharField(max_length=180, blank=True, default="")
    numero = models.CharField(max_length=30, blank=True, default="")
    complemento = models.CharField(max_length=120, blank=True, default="")
    bairro = models.CharField(max_length=120, blank=True, default="")
    cidade = models.CharField(max_length=120, blank=True, default="")
    estado = models.CharField(max_length=2, blank=True, default="")
    pais = models.CharField(max_length=2, blank=True, default="BR")
    reference_point = models.CharField(max_length=220, blank=True, default="")
    coverage_area = models.CharField(max_length=220, blank=True, default="")
    opening_hours = models.CharField(max_length=120, blank=True, default="")

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geocode_provider = models.CharField(
        max_length=20,
        choices=GeocodeProvider.choices,
        default=GeocodeProvider.NONE,
    )
    geocode_status = models.CharField(
        max_length=20,
        choices=GeocodeStatus.choices,
        default=GeocodeStatus.PENDING,
    )
    maps_url = models.URLField(max_length=520, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="org_addresses_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="org_addresses_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ["entity_type", "entity_id", "-is_primary", "id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "is_active"]),
            models.Index(fields=["entity_type", "entity_id", "is_primary"]),
            models.Index(fields=["is_public", "is_active"]),
            models.Index(fields=["geocode_status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "entity_id", "is_primary"],
                condition=models.Q(is_active=True, is_primary=True),
                name="uniq_primary_active_address_per_entity",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entity_type}#{self.entity_id} • {self.label or 'Principal'}"

    def clean(self):
        self.label = (self.label or "").strip() or "Principal"
        self.cep = (self.cep or "").strip()
        self.logradouro = (self.logradouro or "").strip()
        self.numero = (self.numero or "").strip() or "S/N"
        self.complemento = (self.complemento or "").strip()
        self.bairro = (self.bairro or "").strip()
        self.cidade = (self.cidade or "").strip()
        self.estado = (self.estado or "").strip().upper()
        self.pais = (self.pais or "BR").strip().upper()[:2] or "BR"
        self.reference_point = (self.reference_point or "").strip()
        self.coverage_area = (self.coverage_area or "").strip()
        self.opening_hours = (self.opening_hours or "").strip()

        required_fields = {
            "logradouro": self.logradouro,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "estado": self.estado,
        }
        errors: dict[str, str] = {}
        for field, value in required_fields.items():
            if not value:
                errors[field] = "Campo obrigatório."

        if self.cep:
            digits = "".join(ch for ch in self.cep if ch.isdigit())
            if len(digits) != 8:
                errors["cep"] = "CEP inválido. Use o formato NNNNN-NNN."
            else:
                self.cep = f"{digits[:5]}-{digits[5:]}"

        has_lat = self.latitude is not None
        has_lng = self.longitude is not None
        if has_lat != has_lng:
            errors["latitude"] = "Latitude e longitude devem ser preenchidas juntas."
            errors["longitude"] = "Latitude e longitude devem ser preenchidas juntas."

        if self.latitude is not None and not (-90 <= float(self.latitude) <= 90):
            errors["latitude"] = "Latitude fora do intervalo válido."
        if self.longitude is not None and not (-180 <= float(self.longitude) <= 180):
            errors["longitude"] = "Longitude fora do intervalo válido."

        if errors:
            raise ValidationError(errors)

    def compose_query(self) -> str:
        parts = [
            self.logradouro,
            self.numero,
            self.bairro,
            self.cidade,
            self.estado,
            self.cep,
            "Brasil" if (self.pais or "BR") == "BR" else self.pais,
        ]
        return ", ".join(part for part in parts if part)

    def formatted_address(self) -> str:
        line1 = " ".join(part for part in [self.logradouro, self.numero] if part)
        line2_parts = [self.complemento, self.bairro, f"{self.cidade}/{self.estado}".strip("/"), self.cep]
        line2 = " • ".join(part for part in line2_parts if part)
        return "\n".join(part for part in [line1, line2] if part)

    def _build_maps_url(self) -> str:
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        query = quote_plus(self.compose_query())
        return f"https://www.google.com/maps/search/?api=1&query={query}" if query else ""

    @property
    def directions_url(self) -> str:
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps/dir/?api=1&destination={self.latitude},{self.longitude}"
        query = quote_plus(self.compose_query())
        return f"https://www.google.com/maps/dir/?api=1&destination={query}" if query else ""

    def save(self, *args, **kwargs):
        self.full_clean()
        self.maps_url = self._build_maps_url()
        super().save(*args, **kwargs)


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


class LocalEstrutural(models.Model):
    class TipoLocal(models.TextChoices):
        SETOR = "SETOR", "Setor"
        SALA = "SALA", "Sala"
        LABORATORIO = "LABORATORIO", "Laboratório"
        DEPOSITO = "DEPOSITO", "Depósito"
        ALMOXARIFADO = "ALMOXARIFADO", "Almoxarifado interno"
        SECRETARIA = "SECRETARIA", "Secretaria interna"
        COORDENACAO = "COORDENACAO", "Coordenação"
        CONSULTORIO = "CONSULTORIO", "Consultório"
        RECEPCAO = "RECEPCAO", "Recepção"
        BLOCO = "BLOCO", "Bloco"
        OUTRO = "OUTRO", "Outro"

    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        related_name="locais_estruturais",
    )
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.PROTECT,
        related_name="locais_estruturais",
    )
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="locais_estruturais",
    )
    local_pai = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="filhos",
        null=True,
        blank=True,
    )

    nome = models.CharField(max_length=160)
    tipo_local = models.CharField(max_length=30, choices=TipoLocal.choices, default=TipoLocal.SETOR)
    codigo = models.CharField(max_length=40, blank=True, default="")
    responsavel = models.CharField(max_length=180, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)

    # Campo opcional para migração assistida dos setores legados para locais estruturais.
    legacy_setor = models.OneToOneField(
        "org.Setor",
        on_delete=models.SET_NULL,
        related_name="local_estrutural",
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Local estrutural"
        verbose_name_plural = "Locais estruturais"
        ordering = ["unidade__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "local_pai", "nome"],
                name="uniq_local_estrutural_unidade_pai_nome",
            ),
            models.UniqueConstraint(
                fields=["municipio", "codigo"],
                condition=~models.Q(codigo=""),
                name="uniq_local_estrutural_codigo_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "secretaria", "unidade"]),
            models.Index(fields=["tipo_local", "status"]),
            models.Index(fields=["nome"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["local_pai"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.unidade})"

    @property
    def nivel(self) -> int:
        level = 0
        current = self.local_pai
        while current:
            level += 1
            current = current.local_pai
        return level

    @property
    def caminho(self) -> str:
        nomes: list[str] = [self.nome]
        current = self.local_pai
        while current:
            nomes.append(current.nome)
            current = current.local_pai
        return " / ".join(reversed(nomes))

    def clean(self):
        errors: dict[str, str] = {}

        if self.unidade_id and self.secretaria_id and self.unidade.secretaria_id != self.secretaria_id:
            errors["unidade"] = "A unidade deve pertencer à secretaria selecionada."

        if self.secretaria_id and self.municipio_id and self.secretaria.municipio_id != self.municipio_id:
            errors["secretaria"] = "A secretaria deve pertencer ao município selecionado."

        if self.local_pai_id:
            if self.pk and self.local_pai_id == self.pk:
                errors["local_pai"] = "Um local não pode ser pai de si mesmo."
            elif self.local_pai.unidade_id != self.unidade_id:
                errors["local_pai"] = "O local pai deve pertencer à mesma unidade."

            ancestor = self.local_pai
            visited: set[int] = {self.pk} if self.pk else set()
            while ancestor:
                if ancestor.pk in visited:
                    errors["local_pai"] = "Hierarquia inválida: ciclo detectado."
                    break
                visited.add(ancestor.pk)
                ancestor = ancestor.local_pai

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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


class MunicipioOnboardingWizard(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="onboarding_wizard",
    )
    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="onboarding_wizards",
    )
    current_step = models.PositiveSmallIntegerField(default=1)
    total_steps = models.PositiveSmallIntegerField(default=9)
    draft_data = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sessão de onboarding municipal"
        verbose_name_plural = "Sessões de onboarding municipal"
        indexes = [
            models.Index(fields=["municipio", "completed_at"]),
            models.Index(fields=["current_step"]),
        ]

    def __str__(self) -> str:
        who = getattr(self.user, "username", None) or f"user#{self.user_id}"
        return f"{who} • etapa {self.current_step}/{self.total_steps}"

    @property
    def is_completed(self) -> bool:
        return bool(self.completed_at)


class MunicipioThemeConfig(models.Model):
    class ThemeChoice(models.TextChoices):
        KASSYA = "kassya", "Kassya"
        INCLUSAO = "inclusao", "Inclusão"
        INSTITUCIONAL = "institucional", "Institucional"

    municipio = models.OneToOneField(
        Municipio,
        on_delete=models.CASCADE,
        related_name="theme_config",
    )
    default_theme = models.CharField(
        max_length=30,
        choices=ThemeChoice.choices,
        default=ThemeChoice.KASSYA,
    )
    lock_theme_for_users = models.BooleanField(default=False)
    allow_user_theme_override = models.BooleanField(default=True)
    token_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text="Override de tokens CSS por tenant. Ex.: {'--gp-primary': '#0055aa'}",
    )
    ds_version = models.CharField(max_length=20, default="GEPUB DS v2.0")
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Configuração de tema do município"
        verbose_name_plural = "Configurações de tema dos municípios"
        ordering = ["municipio__nome"]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.default_theme}"
