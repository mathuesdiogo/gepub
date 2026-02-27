# apps/core/models.py
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid


def _current_year() -> int:
    return timezone.localdate().year


class AlunoAviso(models.Model):
    """
    Avisos que aparecem no dashboard do aluno.
    Escopo (um ou mais):
    - aluno (direto)
    - turma
    - unidade
    - secretaria
    - municipio
    """

    titulo = models.CharField(max_length=160)
    texto = models.TextField(blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="avisos_criados"
    )

    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")
    turma = models.ForeignKey("educacao.Turma", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")

    unidade = models.ForeignKey("org.Unidade", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")
    secretaria = models.ForeignKey("org.Secretaria", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")
    municipio = models.ForeignKey("org.Municipio", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo


class AlunoArquivo(models.Model):
    """
    Arquivos anexados (atividades/documentos) para o aluno.
    Mesmo escopo do aviso.
    """

    titulo = models.CharField(max_length=160)
    descricao = models.TextField(blank=True)
    arquivo = models.FileField(upload_to="portal_aluno/")

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="arquivos_criados"
    )

    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")
    turma = models.ForeignKey("educacao.Turma", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")

    unidade = models.ForeignKey("org.Unidade", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")
    secretaria = models.ForeignKey("org.Secretaria", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")
    municipio = models.ForeignKey("org.Municipio", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo
class DocumentoEmitido(models.Model):
    """
    Registro de documentos emitidos pelo sistema (validação pública).
    """

    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField(max_length=120)
    titulo = models.CharField(max_length=255)
    gerado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_emitidos",
    )
    gerado_em = models.DateTimeField(default=timezone.now)
    origem_url = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-gerado_em"]

    def __str__(self):
        return f"{self.tipo} — {self.codigo}"


class InstitutionalPageConfig(models.Model):
    nome = models.CharField(max_length=120, default="Página Institucional")
    ativo = models.BooleanField(default=True)

    marca_nome = models.CharField(max_length=80, default="GEPUB")
    marca_logo = models.ImageField(upload_to="institutional/brand/", blank=True, null=True)

    nav_metodo_label = models.CharField(max_length=30, default="Método")
    nav_planos_label = models.CharField(max_length=30, default="Planos")
    nav_servicos_label = models.CharField(max_length=30, default="Serviços")
    nav_simulador_label = models.CharField(max_length=30, default="Simulador")
    botao_login_label = models.CharField(max_length=40, default="Entrar")

    hero_kicker = models.CharField(max_length=140, default="UM SISTEMA SOB MEDIDA PARA PREFEITURAS")
    hero_titulo = models.TextField(
        default="Elaboramos a estratégia digital da sua gestão para integrar secretarias, "
        "acelerar resultados e ampliar controle público."
    )
    hero_descricao = models.TextField(
        default="O GEPUB conecta Educação, Saúde, NEE e estrutura administrativa em uma única "
        "plataforma SaaS, com onboarding automático, auditoria e gestão de planos por município."
    )
    hero_cta_primario_label = models.CharField(max_length=50, default="SIMULAR PLANO")
    hero_cta_primario_link = models.CharField(max_length=120, default="#simulador")
    hero_cta_secundario_label = models.CharField(max_length=50, default="VER PLANOS")
    hero_cta_secundario_link = models.CharField(max_length=120, default="#planos")

    oferta_tag = models.CharField(max_length=140, default="ESTRUTURA PRONTA PARA LICITAÇÃO")
    oferta_titulo = models.TextField(
        default="Essa pode ser a virada da sua gestão: um SaaS único para substituir "
        "contratos fragmentados e reduzir retrabalho entre secretarias."
    )
    oferta_descricao = models.TextField(
        default="Contratação em formato público com licença SaaS, implantação, migração, "
        "treinamento, suporte e manutenção, com vigência mínima de 12 meses e reajuste anual INPC/IPCA."
    )

    metodo_kicker = models.CharField(max_length=80, default="MÉTODO GEPUB")
    metodo_titulo = models.TextField(
        default="Um único fluxo para implantar com governança e escalar com previsibilidade."
    )
    metodo_cta_label = models.CharField(max_length=50, default="QUERO AVALIAR MEU MUNICÍPIO")
    metodo_cta_link = models.CharField(max_length=120, default="#simulador")

    planos_kicker = models.CharField(max_length=80, default="PLANOS MUNICIPAIS")
    planos_titulo = models.TextField(
        default="O GEPUB respeita o porte do município e cresce conforme a operação."
    )
    planos_descricao = models.TextField(
        default="Você contrata uma base mensal com limites objetivos e adicionais transparentes. "
        "Sem contrato confuso, sem variação imprevisível de custo."
    )
    planos_cta_label = models.CharField(max_length=50, default="SIMULAR AGORA")
    planos_cta_link = models.CharField(max_length=120, default="#simulador")

    servicos_kicker = models.CharField(max_length=80, default="NOSSOS SERVIÇOS")
    servicos_titulo = models.TextField(
        default="Tudo que entregamos para operação municipal de ponta a ponta."
    )
    servicos_cta_label = models.CharField(max_length=50, default="FALE COM O TIME GEPUB")
    servicos_cta_link = models.CharField(max_length=120, default="#simulador")

    rodape_texto = models.CharField(
        max_length=220,
        default="© GEPUB • Gestão Estratégica Pública. Todos os direitos reservados.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração institucional"
        verbose_name_plural = "Configurações institucionais"
        ordering = ["-atualizado_em", "-id"]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ativo:
            InstitutionalPageConfig.objects.exclude(pk=self.pk).filter(ativo=True).update(ativo=False)


class InstitutionalSlide(models.Model):
    pagina = models.ForeignKey(
        InstitutionalPageConfig,
        on_delete=models.CASCADE,
        related_name="slides",
    )
    titulo = models.CharField(max_length=120)
    subtitulo = models.CharField(max_length=180, blank=True, default="")
    descricao = models.TextField(blank=True, default="")
    imagem = models.ImageField(upload_to="institutional/slides/", blank=True, null=True)
    icone = models.CharField(max_length=80, default="fa-solid fa-user-tie")
    cta_label = models.CharField(max_length=50, blank=True, default="")
    cta_link = models.CharField(max_length=120, blank=True, default="")
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Slide institucional"
        verbose_name_plural = "Slides institucionais"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.pagina.nome} • {self.titulo}"


class InstitutionalMethodStep(models.Model):
    pagina = models.ForeignKey(
        InstitutionalPageConfig,
        on_delete=models.CASCADE,
        related_name="metodo_passos",
    )
    titulo = models.CharField(max_length=140)
    descricao = models.TextField(blank=True, default="")
    icone = models.CharField(max_length=80, default="fa-solid fa-circle-check")
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Passo do método"
        verbose_name_plural = "Passos do método"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.pagina.nome} • {self.titulo}"


class InstitutionalServiceCard(models.Model):
    pagina = models.ForeignKey(
        InstitutionalPageConfig,
        on_delete=models.CASCADE,
        related_name="servicos",
    )
    titulo = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default="")
    icone = models.CharField(max_length=80, default="fa-solid fa-square")
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Card de serviço"
        verbose_name_plural = "Cards de serviço"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.pagina.nome} • {self.titulo}"


class AuditoriaEvento(models.Model):
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.PROTECT,
        related_name="auditoria_eventos",
    )
    modulo = models.CharField(max_length=40)
    evento = models.CharField(max_length=80)
    entidade = models.CharField(max_length=80)
    entidade_id = models.CharField(max_length=40)
    antes = models.JSONField(default=dict, blank=True)
    depois = models.JSONField(default=dict, blank=True)
    observacao = models.CharField(max_length=200, blank=True, default="")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditoria_eventos",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de auditoria"
        verbose_name_plural = "Eventos de auditoria"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "modulo", "criado_em"]),
            models.Index(fields=["entidade", "entidade_id"]),
            models.Index(fields=["evento", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.modulo}:{self.evento} • {self.entidade}#{self.entidade_id}"


class TransparenciaEventoPublico(models.Model):
    class Modulo(models.TextChoices):
        PROCESSOS = "PROCESSOS", "Processos"
        COMPRAS = "COMPRAS", "Compras"
        CONTRATOS = "CONTRATOS", "Contratos"
        FINANCEIRO = "FINANCEIRO", "Financeiro"
        INTEGRACOES = "INTEGRACOES", "Integracoes"
        OUTROS = "OUTROS", "Outros"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.PROTECT,
        related_name="transparencia_eventos",
    )
    modulo = models.CharField(max_length=20, choices=Modulo.choices, default=Modulo.OUTROS)
    tipo_evento = models.CharField(max_length=80)
    titulo = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    referencia = models.CharField(max_length=120, blank=True, default="")
    valor = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    data_evento = models.DateTimeField(default=timezone.now)
    dados = models.JSONField(default=dict, blank=True)
    publico = models.BooleanField(default=True)
    publicado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de transparencia"
        verbose_name_plural = "Eventos de transparencia"
        ordering = ["-data_evento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "modulo", "data_evento"]),
            models.Index(fields=["tipo_evento", "data_evento"]),
            models.Index(fields=["publico", "data_evento"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_modulo_display()} • {self.tipo_evento} • {self.titulo}"


class PortalMunicipalConfig(models.Model):
    municipio = models.OneToOneField(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="portal_config",
    )
    titulo_portal = models.CharField(max_length=180, default="Portal Público Municipal")
    subtitulo_portal = models.CharField(max_length=220, blank=True, default="")
    mensagem_boas_vindas = models.TextField(blank=True, default="")
    logo = models.ImageField(upload_to="portal/brand/", blank=True, null=True)
    brasao = models.ImageField(upload_to="portal/brand/", blank=True, null=True)
    cor_primaria = models.CharField(max_length=9, default="#0E4A7E")
    cor_secundaria = models.CharField(max_length=9, default="#2F6EA9")
    endereco = models.CharField(max_length=220, blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    horario_atendimento = models.CharField(max_length=120, blank=True, default="")
    redes_sociais = models.JSONField(default=dict, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do portal municipal"
        verbose_name_plural = "Configurações do portal municipal"
        ordering = ["municipio__nome"]

    def __str__(self) -> str:
        return f"Portal • {self.municipio.nome}"


class PortalBanner(models.Model):
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="portal_banners",
    )
    titulo = models.CharField(max_length=180)
    subtitulo = models.CharField(max_length=220, blank=True, default="")
    imagem = models.ImageField(upload_to="portal/banners/", blank=True, null=True)
    link = models.CharField(max_length=220, blank=True, default="")
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Banner do portal"
        verbose_name_plural = "Banners do portal"
        ordering = ["ordem", "-id"]
        indexes = [
            models.Index(fields=["municipio", "ativo", "ordem"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio.nome} • {self.titulo}"


class PortalPaginaPublica(models.Model):
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="portal_paginas",
    )
    titulo = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, blank=True, default="")
    resumo = models.TextField(blank=True, default="")
    conteudo = models.TextField(blank=True, default="")
    mostrar_no_menu = models.BooleanField(default=False)
    mostrar_no_rodape = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=1)
    publicado = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_paginas_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Página pública do portal"
        verbose_name_plural = "Páginas públicas do portal"
        ordering = ["ordem", "titulo", "id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "slug"], name="uniq_portal_pagina_municipio_slug"),
        ]
        indexes = [
            models.Index(fields=["municipio", "publicado", "ordem"]),
            models.Index(fields=["municipio", "mostrar_no_menu", "ordem"]),
        ]

    def save(self, *args, **kwargs):
        base = slugify(self.titulo or "pagina").strip("-") or "pagina"
        if not self.slug:
            self.slug = base
        self.slug = slugify(self.slug).strip("-") or base
        candidate = self.slug[:220]
        i = 2
        qs = type(self).objects.filter(municipio=self.municipio).exclude(pk=self.pk)
        while qs.filter(slug=candidate).exists():
            suffix = f"-{i}"
            candidate = f"{base[: max(1, 220 - len(suffix))]}{suffix}"
            i += 1
        self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.titulo


class PortalMenuPublico(models.Model):
    class TipoDestino(models.TextChoices):
        INTERNO = "INTERNO", "Rota interna"
        PAGINA = "PAGINA", "Página pública"
        EXTERNO = "EXTERNO", "Link externo"

    class RotaInterna(models.TextChoices):
        HOME = "HOME", "Início"
        NOTICIAS = "NOTICIAS", "Notícias"
        LICITACOES = "LICITACOES", "Licitações"
        CONTRATOS = "CONTRATOS", "Contratos"
        TRANSPARENCIA = "TRANSPARENCIA", "Transparência"
        OUVIDORIA = "OUVIDORIA", "e-SIC/Ouvidoria"
        DIARIO = "DIARIO", "Diário Oficial"
        CONCURSOS = "CONCURSOS", "Concursos"
        CAMARA = "CAMARA", "Câmara"
        SAUDE = "SAUDE", "Saúde"
        EDUCACAO = "EDUCACAO", "Educação"

    class Posicao(models.TextChoices):
        HEADER = "HEADER", "Menu superior"
        FOOTER = "FOOTER", "Rodapé"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="portal_menu_items",
    )
    titulo = models.CharField(max_length=120)
    tipo_destino = models.CharField(
        max_length=10,
        choices=TipoDestino.choices,
        default=TipoDestino.INTERNO,
    )
    rota_interna = models.CharField(
        max_length=20,
        choices=RotaInterna.choices,
        default=RotaInterna.HOME,
        blank=True,
    )
    pagina = models.ForeignKey(
        "core.PortalPaginaPublica",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="menu_items",
    )
    url_externa = models.CharField(max_length=240, blank=True, default="")
    abrir_em_nova_aba = models.BooleanField(default=False)
    posicao = models.CharField(max_length=10, choices=Posicao.choices, default=Posicao.HEADER)
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Item de menu do portal"
        verbose_name_plural = "Itens de menu do portal"
        ordering = ["posicao", "ordem", "id"]
        indexes = [
            models.Index(fields=["municipio", "posicao", "ativo", "ordem"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio.nome} • {self.titulo}"


class PortalHomeBloco(models.Model):
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="portal_home_blocos",
    )
    titulo = models.CharField(max_length=160)
    descricao = models.TextField(blank=True, default="")
    icone = models.CharField(max_length=80, blank=True, default="fa-solid fa-circle-info")
    link = models.CharField(max_length=240, blank=True, default="")
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bloco da home do portal"
        verbose_name_plural = "Blocos da home do portal"
        ordering = ["ordem", "id"]
        indexes = [
            models.Index(fields=["municipio", "ativo", "ordem"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio.nome} • {self.titulo}"


class PortalTransparenciaArquivo(models.Model):
    class Categoria(models.TextChoices):
        ATOS_NORMATIVOS = "ATOS_NORMATIVOS", "Atos normativos próprios"
        DIARIO_OFICIAL = "DIARIO_OFICIAL", "Diário oficial"
        EXEC_ORC_GERAL_2025 = "EXEC_ORC_GERAL_2025", "Execução orçamentária geral 2025"
        EXEC_ORC_2024 = "EXEC_ORC_2024", "Execução orçamentária 2024"
        EMPRESAS_DIVIDA_ATIVA = "EMPRESAS_DIVIDA_ATIVA", "Empresas com dívida ativa"
        EMENDAS_PARLAMENTARES = "EMENDAS_PARLAMENTARES", "Emendas parlamentares"
        CONVENIOS_RECEBIDOS = "CONVENIOS_RECEBIDOS", "Convênios e transferências recebidas"
        CONVENIOS_REALIZADOS = "CONVENIOS_REALIZADOS", "Convênios e transferências realizadas"
        ACORDOS_SEM_TRANSFERENCIA = "ACORDOS_SEM_TRANSFERENCIA", "Acordos firmados sem transferências"
        RH_FOLHA_PAGAMENTO = "RH_FOLHA_PAGAMENTO", "Recursos Humanos • Folha de pagamento"
        RH_CARGOS = "RH_CARGOS", "Recursos Humanos • Cargos"
        RH_ESTAGIARIOS = "RH_ESTAGIARIOS", "Recursos Humanos • Estagiários"
        RH_TERCEIRIZADOS = "RH_TERCEIRIZADOS", "Recursos Humanos • Terceirizados"
        RH_CONCURSOS = "RH_CONCURSOS", "Recursos Humanos • Concursos"
        RH_SERVIDORES = "RH_SERVIDORES", "Recursos Humanos • Servidores"
        DIARIAS = "DIARIAS", "Diárias"
        OBRAS_PUBLICAS = "OBRAS_PUBLICAS", "Obras públicas"
        OBRAS_PARALISADAS = "OBRAS_PARALISADAS", "Obras paralisadas"
        LICITACOES = "LICITACOES", "Licitações"
        CONTRATOS = "CONTRATOS", "Contratos"
        ADITIVOS_CONTRATOS = "ADITIVOS_CONTRATOS", "Aditivos de contratos"
        FISCAL_CONTRATOS = "FISCAL_CONTRATOS", "Fiscal de contratos"
        LICITANTES_SANCIONADOS = "LICITANTES_SANCIONADOS", "Licitantes e/ou contratados sancionados"
        EMPRESAS_INIDONEAS = "EMPRESAS_INIDONEAS", "Empresas inidôneas e suspensas"
        PRESTACAO_CONTAS_ANTERIORES = "PRESTACAO_CONTAS_ANTERIORES", "Prestação de contas de anos anteriores"
        BALANCO_GERAL = "BALANCO_GERAL", "Prestação de contas • balanço geral"
        RELATORIO_GESTAO_ATIVIDADE = "RELATORIO_GESTAO_ATIVIDADE", "Relatório de gestão ou atividade"
        PARECER_PREVIO_TCE = "PARECER_PREVIO_TCE", "Julgamento das contas pelo TCE • parecer prévio"
        RESULTADO_JULGAMENTO_LEGISLATIVO = "RESULTADO_JULGAMENTO_LEGISLATIVO", "Resultado de julgamento das contas • legislativo"
        RGF = "RGF", "Relatório de gestão fiscal (RGF)"
        RREO = "RREO", "Relatório resumido de execução orçamentária (RREO)"
        PEI = "PEI", "Plano estratégico institucional (PEI)"
        PPA = "PPA", "Plano plurianual (PPA)"
        LDO = "LDO", "Lei de diretrizes orçamentárias (LDO)"
        LOA = "LOA", "Lei orçamentária anual (LOA)"
        MEDICAMENTOS = "MEDICAMENTOS", "Medicamentos"
        EDUCACAO_MATRICULAS = "EDUCACAO_MATRICULAS", "Educação • solicitações de matrícula"
        EDUCACAO_ESPERA_CRECHE = "EDUCACAO_ESPERA_CRECHE", "Educação • lista de espera de creche"
        EDUCACAO_LISTA_ALUNOS = "EDUCACAO_LISTA_ALUNOS", "Educação • lista de alunos"
        DIARIAS_TABELA_VALORES = "DIARIAS_TABELA_VALORES", "Diárias • tabela de valores"
        DADOS_ABERTOS = "DADOS_ABERTOS", "Dados abertos"
        PRESTACAO_CONTAS = "PRESTACAO_CONTAS", "Prestação de contas"
        OUTROS = "OUTROS", "Outros"

    class Formato(models.TextChoices):
        PDF = "PDF", "PDF"
        CSV = "CSV", "CSV"
        XLSX = "XLSX", "XLSX"
        JSON = "JSON", "JSON"
        LINK = "LINK", "Link externo"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="transparencia_arquivos",
    )
    categoria = models.CharField(max_length=40, choices=Categoria.choices, default=Categoria.OUTROS)
    titulo = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    competencia = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="Competência no formato AAAA-MM (opcional).",
    )
    data_referencia = models.DateField(null=True, blank=True)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.PDF)
    arquivo = models.FileField(upload_to="portal/transparencia/%Y/%m/", blank=True, null=True)
    link_externo = models.URLField(blank=True, default="")
    publico = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=1)
    publicado_em = models.DateTimeField(default=timezone.now)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transparencia_arquivos_publicados",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Arquivo de transparência"
        verbose_name_plural = "Arquivos de transparência"
        ordering = ["categoria", "ordem", "-publicado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "categoria", "publico"]),
            models.Index(fields=["municipio", "publico", "publicado_em"]),
            models.Index(fields=["formato"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio.nome} • {self.titulo}"


class PortalNoticia(models.Model):
    class Categoria(models.TextChoices):
        GERAL = "GERAL", "Geral"
        PREFEITURA = "PREFEITURA", "Prefeitura"
        TRANSPARENCIA = "TRANSPARENCIA", "Transparência"
        EDUCACAO = "EDUCACAO", "Educação"
        SAUDE = "SAUDE", "Saúde"
        OUVIDORIA = "OUVIDORIA", "Ouvidoria"
        CAMARA = "CAMARA", "Câmara"
        CONCURSOS = "CONCURSOS", "Concursos"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="portal_noticias",
    )
    titulo = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, blank=True, default="")
    resumo = models.TextField(blank=True, default="")
    conteudo = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.GERAL)
    imagem = models.ImageField(upload_to="portal/noticias/", blank=True, null=True)
    destaque = models.BooleanField(default=False)
    publicado = models.BooleanField(default=True)
    publicado_em = models.DateTimeField(default=timezone.now)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_noticias_publicadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notícia do portal"
        verbose_name_plural = "Notícias do portal"
        ordering = ["-publicado_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "slug"], name="uniq_portal_noticia_municipio_slug"),
        ]
        indexes = [
            models.Index(fields=["municipio", "publicado", "publicado_em"]),
            models.Index(fields=["categoria", "publicado"]),
        ]

    def save(self, *args, **kwargs):
        base = slugify(self.titulo or "noticia").strip("-") or "noticia"
        if not self.slug:
            self.slug = base
        self.slug = slugify(self.slug).strip("-") or base
        candidate = self.slug[:240]
        i = 2
        qs = type(self).objects.filter(municipio=self.municipio).exclude(pk=self.pk)
        while qs.filter(slug=candidate).exists():
            suffix = f"-{i}"
            candidate = f"{base[: max(1, 240 - len(suffix))]}{suffix}"
            i += 1
        self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.titulo


class DiarioOficialEdicao(models.Model):
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="diarios_oficiais",
    )
    numero = models.CharField(max_length=40)
    data_publicacao = models.DateField(default=timezone.localdate)
    resumo = models.CharField(max_length=220, blank=True, default="")
    arquivo_pdf = models.FileField(upload_to="portal/diario_oficial/%Y/%m/", blank=True, null=True)
    publicado = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_oficiais_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Edição do Diário Oficial"
        verbose_name_plural = "Edições do Diário Oficial"
        ordering = ["-data_publicacao", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_diario_oficial_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "publicado", "data_publicacao"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio.nome} • Diário {self.numero}"


class ConcursoPublico(models.Model):
    class Tipo(models.TextChoices):
        CONCURSO = "CONCURSO", "Concurso público"
        SELETIVO = "SELETIVO", "Processo seletivo"
        CHAMAMENTO = "CHAMAMENTO", "Chamamento"

    class Status(models.TextChoices):
        PREVISTO = "PREVISTO", "Previsto"
        INSCRICOES_ABERTAS = "INSCRICOES_ABERTAS", "Inscrições abertas"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        HOMOLOGADO = "HOMOLOGADO", "Homologado"
        ENCERRADO = "ENCERRADO", "Encerrado"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="concursos_publicos",
    )
    titulo = models.CharField(max_length=220)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONCURSO)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PREVISTO)
    descricao = models.TextField(blank=True, default="")
    edital_arquivo = models.FileField(upload_to="portal/concursos/editais/%Y/%m/", blank=True, null=True)
    inicio_inscricao = models.DateField(null=True, blank=True)
    fim_inscricao = models.DateField(null=True, blank=True)
    publicado = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="concursos_publicos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Concurso público"
        verbose_name_plural = "Concursos públicos"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "publicado", "status"]),
        ]

    def __str__(self) -> str:
        return self.titulo


class ConcursoEtapa(models.Model):
    concurso = models.ForeignKey(
        ConcursoPublico,
        on_delete=models.CASCADE,
        related_name="etapas",
    )
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    arquivo = models.FileField(upload_to="portal/concursos/etapas/%Y/%m/", blank=True, null=True)
    ordem = models.PositiveIntegerField(default=1)
    publicado = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Etapa de concurso"
        verbose_name_plural = "Etapas de concurso"
        ordering = ["ordem", "id"]
        indexes = [
            models.Index(fields=["concurso", "publicado", "ordem"]),
        ]

    def __str__(self) -> str:
        return f"{self.concurso.titulo} • {self.titulo}"


class CamaraMateria(models.Model):
    class Tipo(models.TextChoices):
        PROJETO_LEI = "PROJETO_LEI", "Projeto de Lei"
        REQUERIMENTO = "REQUERIMENTO", "Requerimento"
        MOCACAO = "MOCACAO", "Moção"
        INDICACAO = "INDICACAO", "Indicação"
        OUTRO = "OUTRO", "Outro"

    class Status(models.TextChoices):
        EM_TRAMITE = "EM_TRAMITE", "Em trâmite"
        APROVADO = "APROVADO", "Aprovado"
        REJEITADO = "REJEITADO", "Rejeitado"
        ARQUIVADO = "ARQUIVADO", "Arquivado"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="camara_materias",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OUTRO)
    numero = models.CharField(max_length=40)
    ano = models.PositiveIntegerField(default=_current_year)
    ementa = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EM_TRAMITE)
    arquivo = models.FileField(upload_to="portal/camara/materias/%Y/%m/", blank=True, null=True)
    publicado = models.BooleanField(default=True)
    data_publicacao = models.DateField(default=timezone.localdate)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Matéria da Câmara"
        verbose_name_plural = "Matérias da Câmara"
        ordering = ["-data_publicacao", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "tipo", "numero", "ano"], name="uniq_camara_materia_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "publicado", "data_publicacao"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.numero}/{self.ano}"


class CamaraSessao(models.Model):
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.CASCADE,
        related_name="camara_sessoes",
    )
    titulo = models.CharField(max_length=220)
    data_sessao = models.DateField(default=timezone.localdate)
    pauta = models.TextField(blank=True, default="")
    ata_arquivo = models.FileField(upload_to="portal/camara/sessoes/%Y/%m/", blank=True, null=True)
    video_url = models.URLField(blank=True, default="")
    publicado = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sessão da Câmara"
        verbose_name_plural = "Sessões da Câmara"
        ordering = ["-data_sessao", "-id"]
        indexes = [
            models.Index(fields=["municipio", "publicado", "data_sessao"]),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.data_sessao:%d/%m/%Y})"
