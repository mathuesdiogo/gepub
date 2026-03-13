from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from apps.core.module_access import MANAGED_MODULES


class Command(BaseCommand):
    help = (
        "Popula a prefeitura de Santa Aurora do Norte com dados demonstrativos "
        "completos para cenário municipal de 100 mil habitantes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="santa-aurora-do-norte", help="Slug do município alvo.")
        parser.add_argument("--nome", default="Santa Aurora do Norte", help="Nome oficial do município.")
        parser.add_argument("--uf", default="MA", help="UF do município.")
        parser.add_argument("--password", default="12345678", help="Senha padrão dos usuários criados.")

    def handle(self, *args, **options):
        from apps.accounts.models import Profile
        from apps.comunicacao.models import (
            NotificationChannelConfig,
            NotificationJob,
            NotificationLog,
            NotificationTemplate,
        )
        from apps.contratos.models import ContratoAdministrativo, MedicaoContrato
        from apps.conversor.models import ConversionJob
        from apps.core.models import TransparenciaEventoPublico
        from apps.core.services_portal_seed import ensure_portal_seed_for_municipio
        from apps.educacao.models import Aluno, Curso, Matricula, Turma
        from apps.educacao.models_calendario import CalendarioEducacionalEvento
        from apps.educacao.models_diario import DiarioTurma
        from apps.educacao.models_notas import ComponenteCurricular
        from apps.educacao.models_periodos import HorarioAula, PeriodoLetivo
        from apps.integracoes.models import ConectorIntegracao, IntegracaoExecucao
        from apps.nee.models import (
            AcompanhamentoNEE,
            AlunoNecessidade,
            ApoioMatricula,
            EvolucaoPlanoNEE,
            LaudoNEE,
            ObjetivoPlanoNEE,
            PlanoClinicoNEE,
            RecursoNEE,
            TipoNecessidade,
        )
        from apps.org.models import (
            Municipio,
            MunicipioModuloAtivo,
            Secretaria,
            SecretariaModuloAtivo,
            Setor,
            Unidade,
        )
        from apps.ouvidoria.models import OuvidoriaCadastro, OuvidoriaResposta, OuvidoriaTramitacao
        from apps.paineis.models import Chart, Dashboard, Dataset, DatasetColumn, DatasetVersion, ExportJob
        from apps.rh.models import RhCadastro
        from apps.saude.models import (
            AgendamentoSaude,
            AtendimentoSaude,
            EspecialidadeSaude,
            FilaEsperaSaude,
            GradeAgendaSaude,
            PacienteSaude,
            ProfissionalSaude,
            SalaSaude,
        )

        slug = (options["slug"] or "").strip().lower()
        nome_municipio = (options["nome"] or "").strip()
        uf = (options["uf"] or "MA").strip().upper()[:2]
        password = options["password"]
        today = timezone.localdate()
        now = timezone.now()

        if not slug:
            raise CommandError("Informe um slug válido.")

        municipio = Municipio.objects.filter(slug_site=slug).first()
        if not municipio:
            municipio = Municipio.objects.filter(nome__iexact=nome_municipio).first()
        if not municipio:
            municipio = Municipio.objects.create(
                nome=nome_municipio,
                uf=uf,
                slug_site=slug,
                ativo=True,
            )

        municipio.nome = nome_municipio
        municipio.uf = uf
        municipio.slug_site = slug
        municipio.ativo = True
        municipio.cnpj_prefeitura = municipio.cnpj_prefeitura or "12.345.678/0001-90"
        municipio.razao_social_prefeitura = municipio.razao_social_prefeitura or f"Municipio de {nome_municipio}"
        municipio.nome_fantasia_prefeitura = municipio.nome_fantasia_prefeitura or f"Prefeitura de {nome_municipio}"
        municipio.endereco_prefeitura = municipio.endereco_prefeitura or "Praça da Matriz, 100 - Centro"
        municipio.telefone_prefeitura = municipio.telefone_prefeitura or "(98) 3333-1000"
        municipio.email_prefeitura = municipio.email_prefeitura or f"gabinete@{slug}.ma.gov.br"
        municipio.site_prefeitura = municipio.site_prefeitura or f"https://{slug}.ma.gov.br"
        municipio.nome_prefeito = municipio.nome_prefeito or "Maria Helena Costa"
        municipio.save()

        rnd = random.Random(100_000 + municipio.id)
        User = get_user_model()

        self.stdout.write(self.style.WARNING(f"Seed Santa Aurora 100k iniciado para {municipio.nome}/{municipio.uf}"))

        self.stdout.write("1) Aplicando seed estrutural base...")
        call_command("seed_bacuri_demo", slug=municipio.slug_site, password=password, verbosity=0)
        call_command("seed_beneficios_demo", slug=municipio.slug_site, password=password, verbosity=0)

        # Estrutura base por secretaria/unidade/setor
        def ensure_secretaria(nome: str, tipo_modelo: str, aliases: list[str]) -> Secretaria:
            qs = Secretaria.objects.filter(municipio=municipio)
            sec = qs.filter(tipo_modelo=tipo_modelo).order_by("id").first() if tipo_modelo else None
            if not sec:
                for alias in aliases:
                    sec = qs.filter(nome__icontains=alias).order_by("id").first()
                    if sec:
                        break
            if not sec:
                sec = Secretaria.objects.create(
                    municipio=municipio,
                    nome=nome,
                    tipo_modelo=tipo_modelo,
                    ativo=True,
                )
            sec.nome = sec.nome or nome
            sec.tipo_modelo = tipo_modelo
            sec.ativo = True
            sec.save()
            return sec

        def ensure_unidades(secretaria: Secretaria, tipo: str, target: int, prefix: str) -> list[Unidade]:
            unidades_qs = Unidade.objects.filter(secretaria=secretaria, tipo=tipo).order_by("id")
            existentes = list(unidades_qs)
            if len(existentes) < target:
                novos = []
                for idx in range(len(existentes) + 1, target + 1):
                    novos.append(
                        Unidade(
                            secretaria=secretaria,
                            tipo=tipo,
                            nome=f"{prefix} {idx:02d}",
                            ativo=True,
                            email=f"contato{idx:02d}@{slug}.ma.gov.br",
                            telefone=f"(98) 33{idx:02d}-10{idx:02d}",
                            endereco=f"Av. Setorial {idx}, {nome_municipio}/{uf}",
                        )
                    )
                Unidade.objects.bulk_create(novos, batch_size=200)
            return list(Unidade.objects.filter(secretaria=secretaria, tipo=tipo).order_by("id"))

        def ensure_setores(unidades: list[Unidade], nomes: list[str]) -> list[Setor]:
            novos = []
            existentes = {
                (item.unidade_id, item.nome)
                for item in Setor.objects.filter(unidade__in=unidades).only("id", "unidade_id", "nome")
            }
            for unidade in unidades:
                for nome in nomes:
                    key = (unidade.id, nome)
                    if key in existentes:
                        continue
                    novos.append(Setor(unidade=unidade, nome=nome, ativo=True))
                    existentes.add(key)
            if novos:
                Setor.objects.bulk_create(novos, batch_size=500)
            return list(Setor.objects.filter(unidade__in=unidades, ativo=True).order_by("unidade_id", "nome"))

        sec_admin = ensure_secretaria("Secretaria de Administração", "administracao", ["Administração"])
        sec_educacao = ensure_secretaria("Secretaria de Educação", "educacao", ["Educação"])
        sec_saude = ensure_secretaria("Secretaria de Saúde", "saude", ["Saúde"])
        sec_financas = ensure_secretaria("Secretaria de Finanças e Fazenda", "financas", ["Finanças", "Fazenda"])
        sec_obras = ensure_secretaria("Secretaria de Obras e Infraestrutura", "obras", ["Obras"])
        sec_assistencia = ensure_secretaria("Secretaria de Assistência Social", "assistencia", ["Assistência"])
        sec_transporte = ensure_secretaria("Secretaria de Transporte", "transporte", ["Transporte"])
        sec_tecnologia = ensure_secretaria("Secretaria de Tecnologia e Inovação", "tecnologia", ["Tecnologia"])

        unidades_edu = ensure_unidades(sec_educacao, Unidade.Tipo.EDUCACAO, target=18, prefix="Escola Municipal")
        unidades_saude = ensure_unidades(sec_saude, Unidade.Tipo.SAUDE, target=12, prefix="UBS Regional")
        unidades_admin = ensure_unidades(sec_admin, Unidade.Tipo.ADMINISTRACAO, target=4, prefix="Centro Administrativo")
        unidades_fin = ensure_unidades(sec_financas, Unidade.Tipo.FINANCAS, target=3, prefix="Núcleo Fazendário")
        unidades_transp = ensure_unidades(sec_transporte, Unidade.Tipo.TRANSPORTE, target=2, prefix="Base de Transporte")
        unidades_tech = ensure_unidades(sec_tecnologia, Unidade.Tipo.TECNOLOGIA, target=2, prefix="Núcleo de Tecnologia")

        setores_edu = ensure_setores(unidades_edu, ["Coordenação Pedagógica", "Secretaria Escolar", "AEE"])
        setores_saude = ensure_setores(unidades_saude, ["Atendimento", "Enfermagem", "Farmácia"])
        setores_admin = ensure_setores(unidades_admin + unidades_fin + unidades_transp + unidades_tech, ["Gestão", "Operações"])
        todos_setores = setores_edu + setores_saude + setores_admin

        # Ativação de catálogo de módulos
        all_modules = sorted(set(MANAGED_MODULES))
        for modulo in all_modules:
            MunicipioModuloAtivo.objects.update_or_create(
                municipio=municipio,
                modulo=modulo,
                defaults={"ativo": True},
            )
        for secretaria in Secretaria.objects.filter(municipio=municipio, ativo=True):
            for modulo in all_modules:
                SecretariaModuloAtivo.objects.update_or_create(
                    secretaria=secretaria,
                    modulo=modulo,
                    defaults={"ativo": True},
                )

        # Resolve usuário referência
        seed_user = (
            User.objects.filter(profile__municipio=municipio, profile__ativo=True)
            .order_by("-is_superuser", "-is_staff", "id")
            .first()
        )
        if not seed_user:
            seed_user = User.objects.filter(is_superuser=True).order_by("id").first()
        if not seed_user:
            seed_user = User.objects.create_superuser(
                username=f"{slug}.admin",
                email=f"admin@{slug}.ma.gov.br",
                password=password,
            )
            Profile.objects.update_or_create(
                user=seed_user,
                defaults={
                    "role": Profile.Role.MUNICIPAL,
                    "municipio": municipio,
                    "secretaria": sec_admin,
                    "unidade": unidades_admin[0] if unidades_admin else None,
                    "setor": (setores_admin[0] if setores_admin else None),
                    "ativo": True,
                    "bloqueado": False,
                    "must_change_password": False,
                },
            )

        self.stdout.write("2) Reforçando quadro funcional (usuários + RH)...")
        role_pool = [
            Profile.Role.UNIDADE,
            Profile.Role.SECRETARIA,
            Profile.Role.LEITURA,
            Profile.Role.AUDITORIA,
            Profile.Role.RH_GESTOR,
            Profile.Role.PROTOCOLO,
            Profile.Role.CAD_OPER,
            Profile.Role.EDU_PROF,
            Profile.Role.EDU_SECRETARIA,
            Profile.Role.SAU_MEDICO,
            Profile.Role.SAU_ENFERMEIRO,
            Profile.Role.SAU_RECEPCAO,
            Profile.Role.SAU_FARMACIA,
            Profile.Role.INT_GESTAO,
            Profile.Role.DADOS_ANALISTA,
            Profile.Role.PORTAL_EDITOR,
        ]
        perfis_atuais = Profile.objects.filter(municipio=municipio, ativo=True).count()
        target_perfis = 450
        perfis_criados = 0
        if perfis_atuais < target_perfis:
            inicio = User.objects.filter(username__startswith=f"{slug}.srv.").count() + 1
            needed = target_perfis - perfis_atuais
            for idx in range(inicio, inicio + needed):
                username = f"{slug}.srv.{idx:04d}"
                email = f"srv{idx:04d}@{slug}.ma.gov.br"
                if User.objects.filter(username=username).exists():
                    continue
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name="Servidor",
                    last_name=f"{idx:04d}",
                    is_active=True,
                )
                role = rnd.choice(role_pool)
                secretaria = rnd.choice([sec_admin, sec_educacao, sec_saude, sec_financas, sec_obras, sec_assistencia, sec_transporte, sec_tecnologia])
                if role in {Profile.Role.EDU_PROF, Profile.Role.EDU_SECRETARIA}:
                    unidade = rnd.choice(unidades_edu)
                    setor = rnd.choice(setores_edu) if setores_edu else None
                elif role in {Profile.Role.SAU_MEDICO, Profile.Role.SAU_ENFERMEIRO, Profile.Role.SAU_RECEPCAO, Profile.Role.SAU_FARMACIA}:
                    unidade = rnd.choice(unidades_saude)
                    setor = rnd.choice(setores_saude) if setores_saude else None
                else:
                    unidade = rnd.choice(unidades_admin + unidades_fin + unidades_transp + unidades_tech + unidades_edu + unidades_saude)
                    setor = rnd.choice(todos_setores) if todos_setores else None
                Profile.objects.update_or_create(
                    user=user,
                    defaults={
                        "role": role,
                        "municipio": municipio,
                        "secretaria": secretaria,
                        "unidade": unidade,
                        "setor": setor,
                        "ativo": True,
                        "bloqueado": False,
                        "must_change_password": False,
                    },
                )
                perfis_criados += 1

        target_rh = 1800
        rh_qs = RhCadastro.objects.filter(municipio=municipio)
        rh_missing = max(0, target_rh - rh_qs.count())
        if rh_missing:
            usuarios_municipio = list(User.objects.filter(profile__municipio=municipio).distinct())
            rh_novos = []
            start = rh_qs.filter(codigo__startswith="SAN-RH-").count() + 1
            unidades_rh = unidades_admin + unidades_fin + unidades_edu + unidades_saude + unidades_transp
            for idx in range(start, start + rh_missing):
                secretaria = rnd.choice([sec_admin, sec_educacao, sec_saude, sec_financas, sec_obras, sec_assistencia, sec_transporte, sec_tecnologia])
                unidade = rnd.choice(unidades_rh)
                setor = rnd.choice(todos_setores) if todos_setores else None
                salario = Decimal(str(round(rnd.uniform(1600, 13200), 2)))
                rh_novos.append(
                    RhCadastro(
                        municipio=municipio,
                        secretaria=secretaria,
                        unidade=unidade,
                        setor=setor,
                        servidor=rnd.choice(usuarios_municipio) if usuarios_municipio else seed_user,
                        codigo=f"SAN-RH-{idx:05d}",
                        matricula=f"SANMAT{idx:06d}",
                        nome=f"Servidor Municipal {idx:05d}",
                        cargo=rnd.choice(["Assistente Administrativo", "Analista", "Técnico", "Fiscal", "Motorista", "Enfermeiro", "Professor"]),
                        funcao=rnd.choice(["Operacional", "Gestão", "Apoio", "Atendimento"]),
                        regime=rnd.choice([RhCadastro.Regime.ESTATUTARIO, RhCadastro.Regime.CLT, RhCadastro.Regime.COMISSIONADO]),
                        data_admissao=today - timedelta(days=rnd.randint(90, 3650)),
                        situacao_funcional=rnd.choice(
                            [
                                RhCadastro.SituacaoFuncional.ATIVO,
                                RhCadastro.SituacaoFuncional.ATIVO,
                                RhCadastro.SituacaoFuncional.FERIAS,
                                RhCadastro.SituacaoFuncional.AFASTADO,
                            ]
                        ),
                        salario_base=salario,
                        status=RhCadastro.Status.ATIVO,
                        criado_por=seed_user,
                    )
                )
            RhCadastro.objects.bulk_create(rh_novos, batch_size=400, ignore_conflicts=True)

        self.stdout.write("3) Expandindo Educação (cursos, turmas, alunos, grade, horários, calendário)...")
        cursos_base = [
            ("Ensino Fundamental I", "SAN-EFI"),
            ("Ensino Fundamental II", "SAN-EFII"),
            ("Ensino Médio Integrado", "SAN-EMI"),
            ("EJA Modular", "SAN-EJA"),
            ("Formação Técnica em Informática", "SAN-TEC-INF"),
            ("Formação Técnica em Enfermagem", "SAN-TEC-ENF"),
            ("Curso Livre de Robótica", "SAN-LIV-ROB"),
            ("Curso Livre de Música", "SAN-LIV-MUS"),
            ("Curso Livre de Esportes", "SAN-LIV-ESP"),
        ]
        cursos = []
        for nome, codigo in cursos_base:
            curso, _ = Curso.objects.get_or_create(
                nome=nome,
                codigo=codigo,
                defaults={
                    "modalidade_oferta": Curso.ModalidadeOferta.REGULAR,
                    "carga_horaria": rnd.choice([400, 600, 800, 1200]),
                    "ativo": True,
                },
            )
            curso.ativo = True
            curso.save(update_fields=["ativo"])
            cursos.append(curso)

        target_turmas = 260
        turmas_atuais = Turma.objects.filter(unidade__in=unidades_edu, ano_letivo=today.year).count()
        if turmas_atuais < target_turmas:
            novos = []
            start = turmas_atuais + 1
            for idx in range(start, target_turmas + 1):
                novos.append(
                    Turma(
                        unidade=rnd.choice(unidades_edu),
                        nome=f"Turma SAN {today.year}-{idx:03d}",
                        ano_letivo=today.year,
                        turno=rnd.choice([Turma.Turno.MANHA, Turma.Turno.TARDE, Turma.Turno.NOITE]),
                        modalidade=rnd.choice(
                            [
                                Turma.Modalidade.REGULAR,
                                Turma.Modalidade.REGULAR,
                                Turma.Modalidade.EJA,
                                Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
                            ]
                        ),
                        etapa=rnd.choice(
                            [
                                Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS,
                                Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS,
                                Turma.Etapa.ENSINO_MEDIO,
                                Turma.Etapa.EJA_FUNDAMENTAL,
                            ]
                        ),
                        forma_oferta=Turma.FormaOferta.PRESENCIAL,
                        curso=rnd.choice(cursos),
                        ativo=True,
                    )
                )
            Turma.objects.bulk_create(novos, batch_size=250)

        professores = list(
            User.objects.filter(
                profile__municipio=municipio,
                profile__role__in=[Profile.Role.PROFESSOR, Profile.Role.EDU_PROF, Profile.Role.EDU_COORD],
            ).distinct()
        )
        if not professores:
            professores = [seed_user]
        for turma in Turma.objects.filter(unidade__in=unidades_edu, ano_letivo=today.year)[:300]:
            sample_size = 1 if len(professores) == 1 else 2
            turma.professores.add(*rnd.sample(professores, k=min(sample_size, len(professores))))
            DiarioTurma.objects.get_or_create(turma=turma, professor=rnd.choice(professores), ano_letivo=today.year)

        for numero, (inicio, fim) in enumerate(
            [
                (date(today.year, 1, 15), date(today.year, 3, 31)),
                (date(today.year, 4, 1), date(today.year, 6, 30)),
                (date(today.year, 7, 1), date(today.year, 9, 30)),
                (date(today.year, 10, 1), date(today.year, 12, 20)),
            ],
            start=1,
        ):
            PeriodoLetivo.objects.get_or_create(
                ano_letivo=today.year,
                tipo=PeriodoLetivo.Tipo.BIMESTRE,
                numero=numero,
                defaults={"inicio": inicio, "fim": fim, "ativo": True},
            )

        componentes_base = [
            "Língua Portuguesa",
            "Matemática",
            "História",
            "Geografia",
            "Ciências",
            "Inglês",
            "Arte",
            "Educação Física",
            "Projeto de Vida",
            "Tecnologia",
            "Robótica",
            "Cidadania",
        ]
        for idx, nome in enumerate(componentes_base, start=1):
            ComponenteCurricular.objects.get_or_create(
                nome=nome,
                sigla=f"C{idx:02d}",
                defaults={"ativo": True},
            )
        componentes = list(ComponenteCurricular.objects.filter(ativo=True))

        target_alunos = 9000
        alunos_municipio = Aluno.objects.filter(matriculas__turma__unidade__in=unidades_edu).distinct().count()
        alunos_missing = max(0, target_alunos - alunos_municipio)
        if alunos_missing:
            novos_alunos = []
            base = Aluno.objects.filter(nome__startswith="Aluno SAN100K ").count() + 1
            for idx in range(base, base + alunos_missing):
                novos_alunos.append(
                    Aluno(
                        nome=f"Aluno SAN100K {idx:05d}",
                        data_nascimento=today - timedelta(days=rnd.randint(8 * 365, 18 * 365)),
                        nome_mae=f"Responsável {idx:05d}",
                        nome_pai=f"Responsável 2 {idx:05d}",
                        telefone=f"(98) 9{rnd.randint(1000, 9999)}-{rnd.randint(1000, 9999)}",
                        email=f"aluno{idx:05d}@{slug}.edu.br",
                        endereco=f"Bairro Educacional {rnd.randint(1, 60)}, {nome_municipio}/{uf}",
                        ativo=True,
                    )
                )
            Aluno.objects.bulk_create(novos_alunos, batch_size=500)

            turmas = list(Turma.objects.filter(unidade__in=unidades_edu, ano_letivo=today.year))
            candidatos = list(
                Aluno.objects.filter(nome__startswith="Aluno SAN100K ")
                .exclude(matriculas__turma__unidade__in=unidades_edu)
                .order_by("id")[:alunos_missing]
            )
            matriculas = []
            for aluno in candidatos:
                matriculas.append(
                    Matricula(
                        aluno=aluno,
                        turma=rnd.choice(turmas),
                        data_matricula=today - timedelta(days=rnd.randint(5, 240)),
                        situacao=Matricula.Situacao.ATIVA,
                        resultado_final="",
                        observacao="Matrícula gerada por seed 100k.",
                    )
                )
            Matricula.objects.bulk_create(matriculas, batch_size=500, ignore_conflicts=True)

        horario_templates = []
        horas_base = [time(7, 15), time(8, 10), time(9, 5), time(10, 0), time(10, 55)]
        for dia in [1, 2, 3, 4, 5]:
            for ordem, inicio in enumerate(horas_base, start=1):
                fim_dt = (datetime.combine(today, inicio) + timedelta(minutes=45)).time()
                horario_templates.append((dia, ordem, inicio, fim_dt))

        horarios_novos = []
        turmas_horario = list(Turma.objects.filter(unidade__in=unidades_edu, ano_letivo=today.year).order_by("id")[:260])
        existing_pairs = {
            (h.turma_id, h.dia_semana, h.ordem)
            for h in HorarioAula.objects.filter(turma__in=turmas_horario).only("turma_id", "dia_semana", "ordem")
        }
        for turma in turmas_horario:
            for dia, ordem, inicio, fim in horario_templates:
                key = (turma.id, dia, ordem)
                if key in existing_pairs:
                    continue
                horarios_novos.append(
                    HorarioAula(
                        turma=turma,
                        dia_semana=dia,
                        ordem=ordem,
                        inicio=inicio,
                        fim=fim,
                        componente=rnd.choice(componentes).nome if componentes else "Componente",
                        professor=rnd.choice(professores),
                        local=f"Sala {rnd.randint(1, 20)}",
                        ativo=True,
                    )
                )
                existing_pairs.add(key)
        if horarios_novos:
            HorarioAula.objects.bulk_create(horarios_novos, batch_size=1000)

        calendario_exists = CalendarioEducacionalEvento.objects.filter(
            secretaria=sec_educacao,
            ano_letivo=today.year,
        ).count()
        if calendario_exists < 30:
            eventos = []
            for idx in range(1, 31):
                data_base = date(today.year, 1, 1) + timedelta(days=idx * 10)
                eventos.append(
                    CalendarioEducacionalEvento(
                        ano_letivo=today.year,
                        secretaria=sec_educacao,
                        unidade=rnd.choice(unidades_edu),
                        titulo=f"Evento Educacional {idx:02d}",
                        descricao="Evento pedagógico e administrativo da rede municipal.",
                        tipo=rnd.choice(
                            [
                                CalendarioEducacionalEvento.Tipo.LETIVO,
                                CalendarioEducacionalEvento.Tipo.PLANEJAMENTO,
                                CalendarioEducacionalEvento.Tipo.PEDAGOGICO,
                                CalendarioEducacionalEvento.Tipo.COMEMORATIVA,
                            ]
                        ),
                        data_inicio=data_base,
                        data_fim=data_base,
                        dia_letivo=idx % 3 != 0,
                        ativo=True,
                        criado_por=seed_user,
                        atualizado_por=seed_user,
                    )
                )
            CalendarioEducacionalEvento.objects.bulk_create(eventos, batch_size=200, ignore_conflicts=True)

        self.stdout.write("4) Expandindo Saúde (pacientes, profissionais, agenda, atendimentos)...")
        especialidades_nomes = [
            "Clínica Geral",
            "Pediatria",
            "Ginecologia",
            "Cardiologia",
            "Dermatologia",
            "Ortopedia",
            "Psiquiatria",
            "Odontologia",
            "Enfermagem",
            "Fisioterapia",
        ]
        especialidades = []
        for nome in especialidades_nomes:
            esp, _ = EspecialidadeSaude.objects.get_or_create(nome=nome, defaults={"ativo": True})
            esp.ativo = True
            esp.save(update_fields=["ativo"])
            especialidades.append(esp)

        salas_novas = []
        for unidade in unidades_saude:
            for idx in range(1, 4):
                nome = f"Sala {idx:02d} - {unidade.id}"
                if SalaSaude.objects.filter(unidade=unidade, nome=nome).exists():
                    continue
                salas_novas.append(SalaSaude(unidade=unidade, nome=nome, capacidade=1, ativo=True))
        if salas_novas:
            SalaSaude.objects.bulk_create(salas_novas, batch_size=200)
        salas = list(SalaSaude.objects.filter(unidade__in=unidades_saude, ativo=True))

        target_profissionais = 380
        prof_qs = ProfissionalSaude.objects.filter(unidade__in=unidades_saude)
        prof_missing = max(0, target_profissionais - prof_qs.count())
        if prof_missing:
            novos = []
            start = prof_qs.filter(nome__startswith="Profissional SAN100K ").count() + 1
            cargos = [
                ProfissionalSaude.Cargo.MEDICO,
                ProfissionalSaude.Cargo.ENFERMEIRO,
                ProfissionalSaude.Cargo.TECNICO,
                ProfissionalSaude.Cargo.AGENTE,
                ProfissionalSaude.Cargo.ADMIN,
            ]
            for idx in range(start, start + prof_missing):
                cargo = rnd.choice(cargos)
                unidade = rnd.choice(unidades_saude)
                novos.append(
                    ProfissionalSaude(
                        unidade=unidade,
                        especialidade=rnd.choice(especialidades),
                        nome=f"Profissional SAN100K {idx:04d}",
                        cargo=cargo,
                        carga_horaria_semanal=rnd.choice([20, 24, 30, 40]),
                        conselho_numero=f"REG-{idx:05d}",
                        telefone=f"(98) 98{rnd.randint(100,999)}-{rnd.randint(1000,9999)}",
                        email=f"prof.saude{idx:04d}@{slug}.ma.gov.br",
                        ativo=True,
                    )
                )
            ProfissionalSaude.objects.bulk_create(novos, batch_size=300)
        profissionais = list(ProfissionalSaude.objects.filter(unidade__in=unidades_saude, ativo=True))

        grade_novas = []
        existing_grade = {
            (g.profissional_id, g.dia_semana, g.inicio, g.fim)
            for g in GradeAgendaSaude.objects.filter(unidade__in=unidades_saude).only(
                "profissional_id",
                "dia_semana",
                "inicio",
                "fim",
            )
        }
        slots_grade = [
            (0, time(8, 0), time(12, 0)),
            (1, time(8, 0), time(12, 0)),
            (2, time(13, 0), time(17, 0)),
            (3, time(13, 0), time(17, 0)),
            (4, time(8, 0), time(12, 0)),
        ]
        for profissional in profissionais[:260]:
            for dia_semana, ini, fim in slots_grade:
                key = (profissional.id, dia_semana, ini, fim)
                if key in existing_grade:
                    continue
                grade_novas.append(
                    GradeAgendaSaude(
                        unidade=profissional.unidade,
                        profissional=profissional,
                        sala=rnd.choice(salas) if salas else None,
                        especialidade=profissional.especialidade,
                        dia_semana=dia_semana,
                        inicio=ini,
                        fim=fim,
                        duracao_minutos=30,
                        intervalo_minutos=0,
                        ativo=True,
                    )
                )
                existing_grade.add(key)
        if grade_novas:
            GradeAgendaSaude.objects.bulk_create(grade_novas, batch_size=600)

        target_pacientes = 6500
        pac_qs = PacienteSaude.objects.filter(unidade_referencia__in=unidades_saude)
        pac_missing = max(0, target_pacientes - pac_qs.count())
        if pac_missing:
            novos = []
            start = pac_qs.filter(nome__startswith="Paciente SAN100K ").count() + 1
            for idx in range(start, start + pac_missing):
                novos.append(
                    PacienteSaude(
                        unidade_referencia=rnd.choice(unidades_saude),
                        nome=f"Paciente SAN100K {idx:05d}",
                        data_nascimento=today - timedelta(days=rnd.randint(1 * 365, 95 * 365)),
                        sexo=rnd.choice(
                            [
                                PacienteSaude.Sexo.FEMININO,
                                PacienteSaude.Sexo.MASCULINO,
                                PacienteSaude.Sexo.NAO_INFORMADO,
                            ]
                        ),
                        cartao_sus=f"8980{municipio.id:03d}{idx:010d}"[:18],
                        telefone=f"(98) 9{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}",
                        email=f"paciente{idx:05d}@demo.local",
                        endereco=f"Rua da Saúde, {rnd.randint(1, 999)} - {nome_municipio}/{uf}",
                        responsavel_nome=f"Responsável {idx:05d}",
                        responsavel_telefone=f"(98) 9{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}",
                        vulnerabilidades=rnd.choice(["", "", "Acompanhamento social", "Hipertensão", "Diabetes"]),
                        ativo=True,
                    )
                )
            PacienteSaude.objects.bulk_create(novos, batch_size=600)

        pacientes = list(PacienteSaude.objects.filter(unidade_referencia__in=unidades_saude).order_by("id"))

        target_atendimentos = 15000
        at_qs = AtendimentoSaude.objects.filter(unidade__in=unidades_saude)
        at_missing = max(0, target_atendimentos - at_qs.count())
        if at_missing:
            novos = []
            tipos = [
                AtendimentoSaude.Tipo.CONSULTA,
                AtendimentoSaude.Tipo.PROCEDIMENTO,
                AtendimentoSaude.Tipo.TRIAGEM,
                AtendimentoSaude.Tipo.VACINA,
                AtendimentoSaude.Tipo.VISITA,
            ]
            for _ in range(at_missing):
                paciente = rnd.choice(pacientes)
                profissional = rnd.choice(profissionais)
                novos.append(
                    AtendimentoSaude(
                        unidade=profissional.unidade,
                        profissional=profissional,
                        data=today - timedelta(days=rnd.randint(0, 540)),
                        tipo=rnd.choice(tipos),
                        paciente_nome=paciente.nome,
                        observacoes=rnd.choice(
                            [
                                "Atendimento ambulatorial de rotina.",
                                "Retorno programado em 30 dias.",
                                "Paciente orientado sobre cuidados domiciliares.",
                                "Evolução estável e sem intercorrências.",
                            ]
                        ),
                        cid=rnd.choice(["", "", "J00", "I10", "E11", "M54"]),
                    )
                )
            AtendimentoSaude.objects.bulk_create(novos, batch_size=1000)

        target_agendamentos = 5000
        ag_qs = AgendamentoSaude.objects.filter(unidade__in=unidades_saude)
        ag_missing = max(0, target_agendamentos - ag_qs.count())
        if ag_missing:
            novos = []
            statuses = [
                AgendamentoSaude.Status.MARCADO,
                AgendamentoSaude.Status.CONFIRMADO,
                AgendamentoSaude.Status.ATENDIDO,
                AgendamentoSaude.Status.FALTA,
                AgendamentoSaude.Status.CANCELADO,
            ]
            tipos = [
                AgendamentoSaude.Tipo.PRIMEIRA_CONSULTA,
                AgendamentoSaude.Tipo.RETORNO,
                AgendamentoSaude.Tipo.PROCEDIMENTO,
                AgendamentoSaude.Tipo.ENCAIXE,
            ]
            for _ in range(ag_missing):
                profissional = rnd.choice(profissionais)
                paciente = rnd.choice(pacientes)
                delta_dias = rnd.randint(-180, 120)
                inicio = now + timedelta(days=delta_dias, hours=rnd.randint(-4, 4))
                fim = inicio + timedelta(minutes=rnd.choice([20, 30, 40]))
                novos.append(
                    AgendamentoSaude(
                        unidade=profissional.unidade,
                        profissional=profissional,
                        especialidade=profissional.especialidade,
                        sala=rnd.choice(salas) if salas else None,
                        paciente_nome=paciente.nome,
                        paciente_cpf="",
                        inicio=inicio,
                        fim=fim,
                        tipo=rnd.choice(tipos),
                        status=rnd.choice(statuses),
                        motivo="Agenda municipal escalonada para atenção básica e especializada.",
                    )
                )
            AgendamentoSaude.objects.bulk_create(novos, batch_size=1000)

        target_fila = 900
        fila_qs = FilaEsperaSaude.objects.filter(unidade__in=unidades_saude)
        fila_missing = max(0, target_fila - fila_qs.count())
        if fila_missing:
            novos = []
            for _ in range(fila_missing):
                paciente = rnd.choice(pacientes)
                prioridade = rnd.choice(
                    [
                        FilaEsperaSaude.Prioridade.BAIXA,
                        FilaEsperaSaude.Prioridade.MEDIA,
                        FilaEsperaSaude.Prioridade.ALTA,
                    ]
                )
                status = rnd.choice(
                    [
                        FilaEsperaSaude.Status.AGUARDANDO,
                        FilaEsperaSaude.Status.AGUARDANDO,
                        FilaEsperaSaude.Status.CHAMADO,
                        FilaEsperaSaude.Status.CONVERTIDO,
                    ]
                )
                novos.append(
                    FilaEsperaSaude(
                        unidade=rnd.choice(unidades_saude),
                        especialidade=rnd.choice(especialidades),
                        paciente_nome=paciente.nome,
                        paciente_contato=paciente.telefone,
                        prioridade=prioridade,
                        status=status,
                        observacoes="Demanda regulada pelo núcleo municipal.",
                    )
                )
            FilaEsperaSaude.objects.bulk_create(novos, batch_size=800)

        self.stdout.write("5) Expandindo NEE (tipos, laudos, apoios, planos e evolução)...")
        tipos_nee = [
            "TEA",
            "TDAH",
            "Deficiência Intelectual",
            "Deficiência Física",
            "Deficiência Visual",
            "Deficiência Auditiva",
            "Altas Habilidades",
            "Transtorno de Aprendizagem",
            "Paralisia Cerebral",
            "Síndrome de Down",
        ]
        tipos_obj = []
        for nome in tipos_nee:
            obj, _ = TipoNecessidade.objects.get_or_create(nome=nome, defaults={"ativo": True})
            obj.ativo = True
            obj.save(update_fields=["ativo"])
            tipos_obj.append(obj)

        matriculas_municipio = list(
            Matricula.objects.filter(turma__unidade__in=unidades_edu, situacao=Matricula.Situacao.ATIVA)
            .select_related("aluno", "turma")
            .order_by("id")
        )
        alunos_municipio_list = [m.aluno for m in matriculas_municipio if m.aluno_id]
        alunos_municipio_ids = list({a.id for a in alunos_municipio_list})

        target_necessidades = 1200
        nee_qs = AlunoNecessidade.objects.filter(aluno_id__in=alunos_municipio_ids)
        nee_missing = max(0, target_necessidades - nee_qs.count())
        if nee_missing and alunos_municipio_list:
            novos = []
            for _ in range(nee_missing):
                aluno = rnd.choice(alunos_municipio_list)
                novos.append(
                    AlunoNecessidade(
                        aluno=aluno,
                        tipo=rnd.choice(tipos_obj),
                        cid=rnd.choice(["", "F84", "F90", "Q90", "G80"]),
                        observacao="Registro NEE demonstrativo para acompanhamento multidisciplinar.",
                        ativo=True,
                    )
                )
            AlunoNecessidade.objects.bulk_create(novos, batch_size=700)

        target_apoios = 900
        apoio_qs = ApoioMatricula.objects.filter(matricula__in=matriculas_municipio)
        apoio_missing = max(0, target_apoios - apoio_qs.count())
        if apoio_missing and matriculas_municipio:
            novos = []
            tipos_apoio = [
                ApoioMatricula.TipoApoio.AEE,
                ApoioMatricula.TipoApoio.CUIDADOR,
                ApoioMatricula.TipoApoio.INTERPRETE_LIBRAS,
                ApoioMatricula.TipoApoio.PROFESSOR_APOIO,
                ApoioMatricula.TipoApoio.RECURSO,
            ]
            for _ in range(apoio_missing):
                mat = rnd.choice(matriculas_municipio)
                tipo = rnd.choice(tipos_apoio)
                novos.append(
                    ApoioMatricula(
                        matricula=mat,
                        descricao=f"Apoio pedagógico {tipo}",
                        carga_horaria=rnd.choice([2, 4, 6, 8]),
                        ativo=True,
                        tipo=tipo,
                        observacao="Apoio planejado no PDI municipal.",
                    )
                )
            ApoioMatricula.objects.bulk_create(novos, batch_size=600)

        profissionais_nee = profissionais[:]
        target_laudos = 700
        laudos_qs = LaudoNEE.objects.filter(aluno_id__in=alunos_municipio_ids)
        laudos_missing = max(0, target_laudos - laudos_qs.count())
        if laudos_missing and alunos_municipio_list:
            novos = []
            for idx in range(1, laudos_missing + 1):
                aluno = rnd.choice(alunos_municipio_list)
                emissao = today - timedelta(days=rnd.randint(0, 900))
                validade = emissao + timedelta(days=rnd.choice([180, 365, 540]))
                novos.append(
                    LaudoNEE(
                        aluno=aluno,
                        numero=f"SAN-NEE-LD-{idx:05d}",
                        data_emissao=emissao,
                        validade=validade,
                        profissional=rnd.choice(["Neuropediatra", "Psicopedagogo", "Fonoaudiólogo", "Psicólogo"]),
                        profissional_saude=rnd.choice(profissionais_nee) if profissionais_nee else None,
                        texto="Laudo técnico para atendimento educacional especializado.",
                    )
                )
            LaudoNEE.objects.bulk_create(novos, batch_size=500)

        target_recursos = 900
        rec_qs = RecursoNEE.objects.filter(aluno_id__in=alunos_municipio_ids)
        rec_missing = max(0, target_recursos - rec_qs.count())
        if rec_missing and alunos_municipio_list:
            novos = []
            for idx in range(1, rec_missing + 1):
                aluno = rnd.choice(alunos_municipio_list)
                novos.append(
                    RecursoNEE(
                        aluno=aluno,
                        nome=f"Recurso NEE {idx:05d}",
                        status=rnd.choice(
                            [
                                RecursoNEE.Status.ATIVO,
                                RecursoNEE.Status.EM_AVALIACAO,
                                RecursoNEE.Status.INATIVO,
                            ]
                        ),
                        observacao="Recurso de apoio e adaptação curricular.",
                    )
                )
            RecursoNEE.objects.bulk_create(novos, batch_size=700)

        target_acomp = 3000
        acomp_qs = AcompanhamentoNEE.objects.filter(aluno_id__in=alunos_municipio_ids)
        acomp_missing = max(0, target_acomp - acomp_qs.count())
        if acomp_missing and alunos_municipio_list:
            novos = []
            for _ in range(acomp_missing):
                aluno = rnd.choice(alunos_municipio_list)
                novos.append(
                    AcompanhamentoNEE(
                        aluno=aluno,
                        data=today - timedelta(days=rnd.randint(0, 360)),
                        tipo_evento=rnd.choice(
                            [
                                AcompanhamentoNEE.TipoEvento.OBSERVACAO,
                                AcompanhamentoNEE.TipoEvento.ATENDIMENTO,
                                AcompanhamentoNEE.TipoEvento.EVOLUCAO,
                                AcompanhamentoNEE.TipoEvento.INTERVENCAO,
                            ]
                        ),
                        descricao="Registro de acompanhamento evolutivo NEE integrado à rede municipal.",
                        autor=seed_user,
                        visibilidade=rnd.choice(
                            [AcompanhamentoNEE.Visibilidade.EQUIPE, AcompanhamentoNEE.Visibilidade.GESTAO]
                        ),
                    )
                )
            AcompanhamentoNEE.objects.bulk_create(novos, batch_size=1000)

        target_planos = 450
        planos_qs = PlanoClinicoNEE.objects.filter(aluno_id__in=alunos_municipio_ids)
        planos_missing = max(0, target_planos - planos_qs.count())
        if planos_missing:
            alunos_sem_plano = list(
                Aluno.objects.filter(id__in=alunos_municipio_ids)
                .exclude(plano_clinico_nee__isnull=False)
                .order_by("id")[:planos_missing]
            )
            novos_planos = []
            for aluno in alunos_sem_plano:
                novos_planos.append(
                    PlanoClinicoNEE(
                        aluno=aluno,
                        data_inicio=today - timedelta(days=rnd.randint(10, 480)),
                        data_revisao=today + timedelta(days=rnd.randint(60, 240)),
                        responsavel=seed_user,
                        profissional_saude=rnd.choice(profissionais_nee) if profissionais_nee else None,
                        objetivo_geral="Fortalecer autonomia pedagógica e social do estudante.",
                        observacao="Plano clínico integrado entre educação e saúde.",
                    )
                )
            PlanoClinicoNEE.objects.bulk_create(novos_planos, batch_size=400, ignore_conflicts=True)

        planos_recentes = list(PlanoClinicoNEE.objects.filter(aluno_id__in=alunos_municipio_ids).order_by("-id")[:450])
        objetivos_novos = []
        for plano in planos_recentes:
            existentes = ObjetivoPlanoNEE.objects.filter(plano=plano).count()
            if existentes >= 2:
                continue
            for _ in range(2 - existentes):
                objetivos_novos.append(
                    ObjetivoPlanoNEE(
                        plano=plano,
                        area=rnd.choice(
                            [
                                ObjetivoPlanoNEE.Area.COGNITIVO,
                                ObjetivoPlanoNEE.Area.SOCIAL,
                                ObjetivoPlanoNEE.Area.MOTOR,
                                ObjetivoPlanoNEE.Area.COMUNICACAO,
                            ]
                        ),
                        descricao="Desenvolver habilidades funcionais com plano semanal individualizado.",
                        meta="Meta com indicadores de evolução mensais.",
                        prazo=today + timedelta(days=rnd.randint(90, 240)),
                        status=rnd.choice(
                            [
                                ObjetivoPlanoNEE.Status.ATIVO,
                                ObjetivoPlanoNEE.Status.EM_ANDAMENTO,
                                ObjetivoPlanoNEE.Status.CONCLUIDO,
                            ]
                        ),
                    )
                )
        if objetivos_novos:
            ObjetivoPlanoNEE.objects.bulk_create(objetivos_novos, batch_size=500)

        objetivos = list(ObjetivoPlanoNEE.objects.filter(plano__aluno_id__in=alunos_municipio_ids))
        evolucoes_novas = []
        for objetivo in objetivos[:900]:
            if EvolucaoPlanoNEE.objects.filter(objetivo=objetivo).exists():
                continue
            evolucoes_novas.append(
                EvolucaoPlanoNEE(
                    objetivo=objetivo,
                    data=today - timedelta(days=rnd.randint(0, 120)),
                    descricao="Evolução registrada em atendimento conjunto NEE.",
                    avaliacao="Boa adesão às estratégias pedagógicas.",
                    profissional=seed_user,
                )
            )
        if evolucoes_novas:
            EvolucaoPlanoNEE.objects.bulk_create(evolucoes_novas, batch_size=500)

        self.stdout.write("6) Expandindo Contratos e medições...")
        target_contratos = 180
        contratos_qs = ContratoAdministrativo.objects.filter(municipio=municipio)
        contrato_missing = max(0, target_contratos - contratos_qs.count())
        if contrato_missing:
            novos = []
            start = contratos_qs.filter(numero__startswith=f"CT-{today.year}-SAN-").count() + 1
            for idx in range(start, start + contrato_missing):
                inicio_vig = today - timedelta(days=rnd.randint(10, 700))
                fim_vig = inicio_vig + timedelta(days=rnd.randint(180, 900))
                valor = Decimal(str(round(rnd.uniform(60000, 2400000), 2)))
                novos.append(
                    ContratoAdministrativo(
                        municipio=municipio,
                        numero=f"CT-{today.year}-SAN-{idx:04d}",
                        objeto=rnd.choice(
                            [
                                "Serviço de manutenção predial",
                                "Aquisição de insumos de saúde",
                                "Transporte escolar municipal",
                                "Licença de software administrativo",
                                "Reforma de unidades educacionais",
                                "Coleta e destinação de resíduos",
                            ]
                        ),
                        fornecedor_nome=f"Fornecedor SAN {idx:04d}",
                        fornecedor_documento=f"{rnd.randint(10,99)}.{rnd.randint(100,999)}.{rnd.randint(100,999)}/0001-{rnd.randint(10,99)}",
                        fiscal_nome=rnd.choice(["Carlos Mendes", "Aline Costa", "Rita Silva", "Paulo Souza"]),
                        valor_total=valor,
                        vigencia_inicio=inicio_vig,
                        vigencia_fim=fim_vig,
                        status=rnd.choice(
                            [
                                ContratoAdministrativo.Status.ATIVO,
                                ContratoAdministrativo.Status.ATIVO,
                                ContratoAdministrativo.Status.SUSPENSO,
                                ContratoAdministrativo.Status.ENCERRADO,
                            ]
                        ),
                        criado_por=seed_user,
                    )
                )
            ContratoAdministrativo.objects.bulk_create(novos, batch_size=400, ignore_conflicts=True)

        contratos = list(ContratoAdministrativo.objects.filter(municipio=municipio).order_by("id"))
        target_medicoes = 540
        med_qs = MedicaoContrato.objects.filter(contrato__municipio=municipio)
        med_missing = max(0, target_medicoes - med_qs.count())
        if med_missing and contratos:
            counts = {
                row["contrato_id"]: row["c"]
                for row in MedicaoContrato.objects.filter(contrato__in=contratos)
                .values("contrato_id")
                .annotate(c=Count("id"))
            }
            novos = []
            for _ in range(med_missing):
                contrato = rnd.choice(contratos)
                prox = counts.get(contrato.id, 0) + 1
                counts[contrato.id] = prox
                valor = Decimal(str(round(rnd.uniform(5000, 180000), 2)))
                comp_date = today - timedelta(days=rnd.randint(0, 420))
                novos.append(
                    MedicaoContrato(
                        contrato=contrato,
                        numero=f"MED-{prox:03d}",
                        competencia=comp_date.strftime("%Y-%m"),
                        data_medicao=comp_date,
                        valor_medido=valor,
                        observacao="Medição periódica do contrato.",
                        status=rnd.choice(
                            [
                                MedicaoContrato.Status.PENDENTE,
                                MedicaoContrato.Status.ATESTADA,
                                MedicaoContrato.Status.LIQUIDADA,
                            ]
                        ),
                        criado_por=seed_user,
                    )
                )
            MedicaoContrato.objects.bulk_create(novos, batch_size=800, ignore_conflicts=True)

        self.stdout.write("7) Expandindo Integrações, Painéis BI, Conversor e Comunicação...")
        dominios = [
            ConectorIntegracao.Dominio.FINANCEIRO,
            ConectorIntegracao.Dominio.EDUCACAO,
            ConectorIntegracao.Dominio.SAUDE,
            ConectorIntegracao.Dominio.TRANSPARENCIA,
            ConectorIntegracao.Dominio.SICONFI,
            ConectorIntegracao.Dominio.GOVBR,
            ConectorIntegracao.Dominio.OUTROS,
        ]
        tipos_con = [ConectorIntegracao.Tipo.API, ConectorIntegracao.Tipo.ARQUIVO, ConectorIntegracao.Tipo.ETL]
        target_conectores = 26
        con_qs = ConectorIntegracao.objects.filter(municipio=municipio)
        con_missing = max(0, target_conectores - con_qs.count())
        if con_missing:
            novos = []
            start = con_qs.filter(nome__startswith="SAN Conector ").count() + 1
            for idx in range(start, start + con_missing):
                dominio = rnd.choice(dominios)
                nome = f"SAN Conector {idx:03d} - {dominio}"
                novos.append(
                    ConectorIntegracao(
                        municipio=municipio,
                        nome=nome,
                        dominio=dominio,
                        tipo=rnd.choice(tipos_con),
                        endpoint=f"https://api.{slug}.ma.gov.br/{dominio.lower()}/{idx:03d}",
                        credenciais={"token": f"tok_san_{idx:04d}"},
                        configuracao={"retry": rnd.choice([1, 2, 3]), "timeout": rnd.choice([15, 20, 30])},
                        ativo=True,
                        criado_por=seed_user,
                    )
                )
            ConectorIntegracao.objects.bulk_create(novos, batch_size=200, ignore_conflicts=True)
        conectores = list(ConectorIntegracao.objects.filter(municipio=municipio))

        target_execucoes = 900
        ex_qs = IntegracaoExecucao.objects.filter(municipio=municipio)
        ex_missing = max(0, target_execucoes - ex_qs.count())
        if ex_missing and conectores:
            novos = []
            for idx in range(ex_missing):
                conector = rnd.choice(conectores)
                status = rnd.choice([IntegracaoExecucao.Status.SUCESSO, IntegracaoExecucao.Status.SUCESSO, IntegracaoExecucao.Status.FALHA])
                novos.append(
                    IntegracaoExecucao(
                        municipio=municipio,
                        conector=conector,
                        direcao=rnd.choice([IntegracaoExecucao.Direcao.IMPORTACAO, IntegracaoExecucao.Direcao.EXPORTACAO]),
                        status=status,
                        referencia=f"SAN-INT-{today.year}-{idx:05d}",
                        quantidade_registros=rnd.randint(5, 6000),
                        detalhes="Execução automatizada do pipeline municipal.",
                        executado_por=seed_user,
                        executado_em=now - timedelta(days=rnd.randint(0, 180), minutes=rnd.randint(0, 1440)),
                    )
                )
            IntegracaoExecucao.objects.bulk_create(novos, batch_size=1000)

        target_datasets = 36
        ds_qs = Dataset.objects.filter(municipio=municipio)
        ds_missing = max(0, target_datasets - ds_qs.count())
        if ds_missing:
            novos = []
            categorias = ["Educação", "Saúde", "Financeiro", "Tributos", "Contratos", "Ouvidoria", "RH", "Frota"]
            secretarias_all = list(Secretaria.objects.filter(municipio=municipio, ativo=True))
            unidades_all = list(Unidade.objects.filter(secretaria__municipio=municipio, ativo=True))
            for idx in range(1, ds_missing + 1):
                cat = rnd.choice(categorias)
                novos.append(
                    Dataset(
                        municipio=municipio,
                        secretaria=rnd.choice(secretarias_all) if secretarias_all else None,
                        unidade=rnd.choice(unidades_all) if unidades_all else None,
                        nome=f"Dataset SAN {cat} {idx:03d}",
                        descricao=f"Base demonstrativa de {cat.lower()} para acompanhamento executivo.",
                        categoria=cat,
                        fonte=rnd.choice(
                            [
                                Dataset.Fonte.CSV,
                                Dataset.Fonte.XLSX,
                                Dataset.Fonte.GOOGLE_SHEETS,
                                Dataset.Fonte.PDF,
                            ]
                        ),
                        visibilidade=rnd.choice([Dataset.Visibilidade.INTERNO, Dataset.Visibilidade.PUBLICO]),
                        status=rnd.choice(
                            [
                                Dataset.Status.RASCUNHO,
                                Dataset.Status.VALIDADO,
                                Dataset.Status.PUBLICADO,
                                Dataset.Status.ARQUIVADO,
                            ]
                        ),
                        criado_por=seed_user,
                        atualizado_por=seed_user,
                    )
                )
            Dataset.objects.bulk_create(novos, batch_size=300)
        datasets = list(Dataset.objects.filter(municipio=municipio).order_by("id"))

        versoes_novas = []
        for dataset in datasets:
            if DatasetVersion.objects.filter(dataset=dataset).exists():
                continue
            versoes_novas.append(
                DatasetVersion(
                    dataset=dataset,
                    numero=1,
                    fonte=dataset.fonte,
                    status=DatasetVersion.Status.CONCLUIDO,
                    schema_json={"columns": ["competencia", "valor", "categoria", "unidade"]},
                    profile_json={"rows": rnd.randint(300, 15000), "quality_score": rnd.randint(82, 99)},
                    preview_json=[
                        {"competencia": f"{today.year}-01", "valor": rnd.randint(1500, 9000), "categoria": dataset.categoria},
                        {"competencia": f"{today.year}-02", "valor": rnd.randint(1500, 9000), "categoria": dataset.categoria},
                    ],
                    logs="Versão inicial processada com sucesso.",
                    criado_por=seed_user,
                    processado_em=now - timedelta(days=rnd.randint(0, 90)),
                )
            )
        if versoes_novas:
            DatasetVersion.objects.bulk_create(versoes_novas, batch_size=200)

        for versao in DatasetVersion.objects.filter(dataset__in=datasets):
            if DatasetColumn.objects.filter(versao=versao).exists():
                continue
            DatasetColumn.objects.bulk_create(
                [
                    DatasetColumn(versao=versao, nome="competencia", tipo=DatasetColumn.Tipo.DATA, papel=DatasetColumn.Papel.DIMENSAO, ordem=1),
                    DatasetColumn(versao=versao, nome="secretaria", tipo=DatasetColumn.Tipo.TEXTO, papel=DatasetColumn.Papel.DIMENSAO, ordem=2),
                    DatasetColumn(versao=versao, nome="unidade", tipo=DatasetColumn.Tipo.TEXTO, papel=DatasetColumn.Papel.DIMENSAO, ordem=3),
                    DatasetColumn(versao=versao, nome="valor", tipo=DatasetColumn.Tipo.NUMERO, papel=DatasetColumn.Papel.MEDIDA, ordem=4),
                    DatasetColumn(versao=versao, nome="quantidade", tipo=DatasetColumn.Tipo.NUMERO, papel=DatasetColumn.Papel.MEDIDA, ordem=5),
                ],
                ignore_conflicts=True,
            )

        for dataset in datasets:
            dash, _ = Dashboard.objects.get_or_create(
                dataset=dataset,
                nome=f"Painel Executivo - {dataset.nome[:80]}",
                defaults={
                    "descricao": "Painel de acompanhamento com indicadores estratégicos.",
                    "tema": "institucional",
                    "layout_json": {"cols": 12, "widgets": 5},
                    "ativo": True,
                    "criado_por": seed_user,
                },
            )
            if Chart.objects.filter(dashboard=dash).count() < 3:
                chart_count = Chart.objects.filter(dashboard=dash).count()
                chart_types = [Chart.Tipo.KPI, Chart.Tipo.BARRA, Chart.Tipo.LINHA, Chart.Tipo.PIZZA]
                novos = []
                for ordem in range(chart_count + 1, 4):
                    tipo = chart_types[(ordem - 1) % len(chart_types)]
                    novos.append(
                        Chart(
                            dashboard=dash,
                            tipo=tipo,
                            titulo=f"{dash.dataset.categoria or 'Indicador'} {ordem}",
                            ordem=ordem,
                            config_json={"x": "competencia", "y": "valor", "agg": "sum"},
                            ativo=True,
                        )
                    )
                Chart.objects.bulk_create(novos, ignore_conflicts=True)

        target_exports = 220
        exb_qs = ExportJob.objects.filter(dataset__municipio=municipio)
        exb_missing = max(0, target_exports - exb_qs.count())
        if exb_missing and datasets:
            dashboards = list(Dashboard.objects.filter(dataset__in=datasets))
            novos = []
            for idx in range(exb_missing):
                ds = rnd.choice(datasets)
                status = rnd.choice(
                    [
                        ExportJob.Status.PENDENTE,
                        ExportJob.Status.PROCESSANDO,
                        ExportJob.Status.CONCLUIDO,
                        ExportJob.Status.ERRO,
                    ]
                )
                novos.append(
                    ExportJob(
                        dataset=ds,
                        dashboard=rnd.choice(dashboards) if dashboards else None,
                        formato=rnd.choice([ExportJob.Formato.PDF, ExportJob.Formato.CSV, ExportJob.Formato.PNG]),
                        filtros_json={"municipio": municipio.id, "range": "ultimos_12_meses"},
                        status=status,
                        log=f"Exportação demonstrativa #{idx+1}",
                        solicitado_por=seed_user,
                        concluido_em=now - timedelta(days=rnd.randint(0, 60)) if status == ExportJob.Status.CONCLUIDO else None,
                    )
                )
            ExportJob.objects.bulk_create(novos, batch_size=400)

        target_conversor = 800
        cv_qs = ConversionJob.objects.filter(municipio=municipio)
        cv_missing = max(0, target_conversor - cv_qs.count())
        if cv_missing:
            novos = []
            tipos_cv = [choice[0] for choice in ConversionJob.Tipo.choices]
            status_cv = [choice[0] for choice in ConversionJob.Status.choices]
            secretarias_all = list(Secretaria.objects.filter(municipio=municipio, ativo=True))
            unidades_all = list(Unidade.objects.filter(secretaria__municipio=municipio, ativo=True))
            setores_all = list(Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True))
            for idx in range(cv_missing):
                status = rnd.choice(status_cv)
                inicio_job = now - timedelta(days=rnd.randint(0, 120), minutes=rnd.randint(0, 1440))
                concluido = inicio_job + timedelta(seconds=rnd.randint(20, 600)) if status == ConversionJob.Status.CONCLUIDO else None
                duracao = rnd.randint(1200, 180000) if status in {ConversionJob.Status.CONCLUIDO, ConversionJob.Status.ERRO} else 0
                novos.append(
                    ConversionJob(
                        municipio=municipio,
                        secretaria=rnd.choice(secretarias_all) if secretarias_all else None,
                        unidade=rnd.choice(unidades_all) if unidades_all else None,
                        setor=rnd.choice(setores_all) if setores_all else None,
                        tipo=rnd.choice(tipos_cv),
                        status=status,
                        parametros_json={"a4": True, "quality": rnd.choice(["normal", "high"])},
                        logs=f"Job demonstrativo SAN #{idx+1}",
                        tamanho_entrada=rnd.randint(20_000, 18_000_000),
                        tamanho_saida=rnd.randint(15_000, 12_000_000) if status == ConversionJob.Status.CONCLUIDO else 0,
                        duracao_ms=duracao,
                        criado_por=seed_user,
                        criado_em=inicio_job,
                        atualizado_em=inicio_job,
                        concluido_em=concluido,
                    )
                )
            ConversionJob.objects.bulk_create(novos, batch_size=500)

        canais = [
            (NotificationChannelConfig.Channel.EMAIL, NotificationChannelConfig.Provider.SMTP),
            (NotificationChannelConfig.Channel.SMS, NotificationChannelConfig.Provider.ZENVIA),
            (NotificationChannelConfig.Channel.WHATSAPP, NotificationChannelConfig.Provider.META),
        ]
        for channel, provider in canais:
            NotificationChannelConfig.objects.update_or_create(
                municipio=municipio,
                secretaria=None,
                unidade=None,
                channel=channel,
                provider=provider,
                defaults={
                    "sender_name": f"Prefeitura {nome_municipio}",
                    "sender_identifier": (
                        municipio.email_prefeitura
                        if channel == NotificationChannelConfig.Channel.EMAIL
                        else "(98) 98888-0000"
                    ),
                    "credentials_json": {"mode": "demo", "provider": provider.lower()},
                    "options_json": {"retry": 2, "throttle_per_min": 120},
                    "is_active": True,
                    "prioridade": 1,
                    "atualizado_por": seed_user,
                },
            )

        event_keys = [
            "EDUCACAO_MATRICULA",
            "EDUCACAO_FREQUENCIA_ALERTA",
            "EDUCACAO_NOTA_PUBLICADA",
            "SAUDE_AGENDAMENTO_CRIADO",
            "SAUDE_AGENDAMENTO_CONFIRMACAO",
            "OUVIDORIA_PROTOCOLO",
            "OUVIDORIA_RESPOSTA",
            "INTEGRACAO_FALHA",
            "INTEGRACAO_SUCESSO",
            "FINANCEIRO_ALERTA",
            "PORTAL_NOVA_PUBLICACAO",
            "NEE_ATUALIZACAO_PLANO",
        ]
        templates_target = 40
        templates_qs = NotificationTemplate.objects.filter(municipio=municipio)
        templates_missing = max(0, templates_target - templates_qs.count())
        if templates_missing:
            novos = []
            canais_template = [
                NotificationChannelConfig.Channel.EMAIL,
                NotificationChannelConfig.Channel.SMS,
                NotificationChannelConfig.Channel.WHATSAPP,
            ]
            for idx in range(templates_missing):
                event_key = rnd.choice(event_keys)
                channel = rnd.choice(canais_template)
                novos.append(
                    NotificationTemplate(
                        municipio=municipio,
                        scope=NotificationTemplate.Scope.MUNICIPIO,
                        event_key=event_key,
                        channel=channel,
                        nome=f"Template SAN {event_key} {idx+1:03d}",
                        subject=f"[{nome_municipio}] {event_key.replace('_', ' ').title()}",
                        body="Mensagem demonstrativa para operação municipal em ambiente de homologação.",
                        is_active=True,
                        nee_safe=event_key.startswith("NEE_"),
                        atualizado_por=seed_user,
                    )
                )
            NotificationTemplate.objects.bulk_create(novos, batch_size=200, ignore_conflicts=True)

        jobs_target = 1200
        jobs_qs = NotificationJob.objects.filter(municipio=municipio)
        jobs_missing = max(0, jobs_target - jobs_qs.count())
        if jobs_missing:
            novos = []
            canais_job = [
                NotificationChannelConfig.Channel.EMAIL,
                NotificationChannelConfig.Channel.SMS,
                NotificationChannelConfig.Channel.WHATSAPP,
            ]
            for idx in range(jobs_missing):
                channel = rnd.choice(canais_job)
                status = rnd.choice(
                    [
                        NotificationJob.Status.PENDENTE,
                        NotificationJob.Status.ENVIADO,
                        NotificationJob.Status.ENTREGUE,
                        NotificationJob.Status.FALHA,
                        NotificationJob.Status.CANCELADO,
                    ]
                )
                scheduled = now - timedelta(days=rnd.randint(0, 45), minutes=rnd.randint(0, 1440))
                sent_at = scheduled + timedelta(minutes=rnd.randint(1, 25)) if status in {NotificationJob.Status.ENVIADO, NotificationJob.Status.ENTREGUE, NotificationJob.Status.FALHA} else None
                delivered_at = sent_at + timedelta(minutes=rnd.randint(1, 15)) if status == NotificationJob.Status.ENTREGUE and sent_at else None
                novos.append(
                    NotificationJob(
                        municipio=municipio,
                        event_key=rnd.choice(event_keys),
                        channel=channel,
                        provider=rnd.choice(["SMTP", "ZENVIA", "META", "MOCK"]),
                        to_name=f"Cidadão {idx+1:05d}",
                        destination=(
                            f"cidadao{idx+1:05d}@email.local"
                            if channel == NotificationChannelConfig.Channel.EMAIL
                            else f"+559899{rnd.randint(100000, 999999)}"
                        ),
                        payload_json={"municipio": municipio.nome, "demo": True},
                        subject_rendered="Comunicação oficial do município",
                        body_rendered="Conteúdo demonstrativo para validação de fluxos de comunicação.",
                        status=status,
                        priority=rnd.choice(
                            [
                                NotificationJob.Priority.NORMAL,
                                NotificationJob.Priority.NORMAL,
                                NotificationJob.Priority.ALTA,
                                NotificationJob.Priority.BAIXA,
                            ]
                        ),
                        attempts=rnd.randint(0, 2),
                        max_attempts=3,
                        fallback_channels=["EMAIL", "WHATSAPP"],
                        fallback_index=0,
                        provider_message_id=f"prov-{idx+1:06d}" if status in {NotificationJob.Status.ENVIADO, NotificationJob.Status.ENTREGUE} else "",
                        error_message="Falha temporária de gateway." if status == NotificationJob.Status.FALHA else "",
                        entity_module=rnd.choice(["EDUCACAO", "SAUDE", "OUVIDORIA", "INTEGRACOES"]),
                        entity_type="REGISTRO",
                        entity_id=str(idx + 1),
                        scheduled_at=scheduled,
                        sent_at=sent_at,
                        delivered_at=delivered_at,
                        created_by=seed_user,
                        created_at=scheduled,
                        updated_at=sent_at or scheduled,
                    )
                )
            NotificationJob.objects.bulk_create(novos, batch_size=600)

        log_jobs = list(NotificationJob.objects.filter(municipio=municipio).exclude(status=NotificationJob.Status.PENDENTE).order_by("-id")[:900])
        logs_novos = []
        existing_logs_job_ids = set(NotificationLog.objects.filter(job__in=log_jobs).values_list("job_id", flat=True))
        for job in log_jobs:
            if job.id in existing_logs_job_ids:
                continue
            logs_novos.append(
                NotificationLog(
                    job=job,
                    status=job.status,
                    attempt=max(1, job.attempts or 1),
                    channel=job.channel,
                    provider=job.provider,
                    destination=job.destination,
                    subject=job.subject_rendered,
                    body=job.body_rendered,
                    provider_response={"status": job.status, "demo": True},
                    error_message=job.error_message,
                    created_at=job.sent_at or job.created_at,
                )
            )
        if logs_novos:
            NotificationLog.objects.bulk_create(logs_novos, batch_size=500)

        self.stdout.write("8) Expandindo Ouvidoria/e-SIC e Transparência...")
        ouvidoria_target = 600
        ouv_qs = OuvidoriaCadastro.objects.filter(municipio=municipio)
        ouv_missing = max(0, ouvidoria_target - ouv_qs.count())
        if ouv_missing:
            novos = []
            secretarias_all = list(Secretaria.objects.filter(municipio=municipio, ativo=True))
            unidades_all = list(Unidade.objects.filter(secretaria__municipio=municipio, ativo=True))
            setores_all = list(Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True))
            start = ouv_qs.filter(protocolo__startswith=f"SAN-OUV-{today.year}-").count() + 1
            for idx in range(start, start + ouv_missing):
                tipo = rnd.choice(
                    [
                        OuvidoriaCadastro.Tipo.RECLAMACAO,
                        OuvidoriaCadastro.Tipo.SUGESTAO,
                        OuvidoriaCadastro.Tipo.ELOGIO,
                        OuvidoriaCadastro.Tipo.DENUNCIA,
                        OuvidoriaCadastro.Tipo.ESIC,
                        OuvidoriaCadastro.Tipo.ESIC,
                    ]
                )
                status = rnd.choice(
                    [
                        OuvidoriaCadastro.Status.ABERTO,
                        OuvidoriaCadastro.Status.EM_ANALISE,
                        OuvidoriaCadastro.Status.ENCAMINHADO,
                        OuvidoriaCadastro.Status.RESPONDIDO,
                        OuvidoriaCadastro.Status.CONCLUIDO,
                    ]
                )
                prazo = today + timedelta(days=rnd.randint(5, 30))
                respondido_em = (now - timedelta(days=rnd.randint(1, 40))) if status in {OuvidoriaCadastro.Status.RESPONDIDO, OuvidoriaCadastro.Status.CONCLUIDO} else None
                novos.append(
                    OuvidoriaCadastro(
                        municipio=municipio,
                        secretaria=rnd.choice(secretarias_all) if secretarias_all else None,
                        unidade=rnd.choice(unidades_all) if unidades_all else None,
                        setor=rnd.choice(setores_all) if setores_all else None,
                        protocolo=f"SAN-OUV-{today.year}-{idx:06d}",
                        assunto=rnd.choice(
                            [
                                "Solicitação de informação pública",
                                "Melhoria na infraestrutura urbana",
                                "Demanda de atendimento em saúde",
                                "Sugestão para transporte escolar",
                                "Reclamação sobre iluminação pública",
                            ]
                        ),
                        tipo=tipo,
                        prioridade=rnd.choice(
                            [
                                OuvidoriaCadastro.Prioridade.BAIXA,
                                OuvidoriaCadastro.Prioridade.MEDIA,
                                OuvidoriaCadastro.Prioridade.ALTA,
                            ]
                        ),
                        descricao="Registro demonstrativo de ouvidoria/e-SIC para ambiente de gestão.",
                        solicitante_nome=f"Cidadão {idx:06d}",
                        solicitante_email=f"cidadao{idx:06d}@demo.local",
                        solicitante_telefone=f"(98) 9{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}",
                        prazo_resposta=prazo,
                        status=status,
                        respondido_em=respondido_em,
                        respondido_por=seed_user if respondido_em else None,
                        observacao="Gerado por seed municipal 100k.",
                        criado_por=seed_user,
                    )
                )
            OuvidoriaCadastro.objects.bulk_create(novos, batch_size=700)

        chamados_respondidos = list(
            OuvidoriaCadastro.objects.filter(
                municipio=municipio,
                status__in=[OuvidoriaCadastro.Status.RESPONDIDO, OuvidoriaCadastro.Status.CONCLUIDO],
            ).order_by("-id")[:400]
        )
        respostas_novas = []
        tramitacoes_novas = []
        resp_exist = set(OuvidoriaResposta.objects.filter(chamado__in=chamados_respondidos).values_list("chamado_id", flat=True))
        tram_exist = set(OuvidoriaTramitacao.objects.filter(chamado__in=chamados_respondidos).values_list("chamado_id", flat=True))
        for chamado in chamados_respondidos:
            if chamado.id not in resp_exist:
                respostas_novas.append(
                    OuvidoriaResposta(
                        municipio=municipio,
                        chamado=chamado,
                        resposta="Resposta oficial registrada no prazo legal com providências definidas.",
                        publico=True,
                        criado_por=seed_user,
                    )
                )
            if chamado.id not in tram_exist:
                tramitacoes_novas.append(
                    OuvidoriaTramitacao(
                        municipio=municipio,
                        chamado=chamado,
                        setor_origem=rnd.choice(todos_setores) if todos_setores else None,
                        setor_destino=rnd.choice(todos_setores) if todos_setores else None,
                        despacho="Encaminhado para análise técnica e retorno ao cidadão.",
                        ciencia=True,
                        criado_por=seed_user,
                    )
                )
        if respostas_novas:
            OuvidoriaResposta.objects.bulk_create(respostas_novas, batch_size=300)
        if tramitacoes_novas:
            OuvidoriaTramitacao.objects.bulk_create(tramitacoes_novas, batch_size=300)

        transparencia_target = 1800
        te_qs = TransparenciaEventoPublico.objects.filter(municipio=municipio)
        te_missing = max(0, transparencia_target - te_qs.count())
        if te_missing:
            novos = []
            modulos = [
                TransparenciaEventoPublico.Modulo.FINANCEIRO,
                TransparenciaEventoPublico.Modulo.CONTRATOS,
                TransparenciaEventoPublico.Modulo.COMPRAS,
                TransparenciaEventoPublico.Modulo.PROCESSOS,
                TransparenciaEventoPublico.Modulo.INTEGRACOES,
                TransparenciaEventoPublico.Modulo.OUTROS,
            ]
            for idx in range(te_missing):
                modulo = rnd.choice(modulos)
                valor = Decimal(str(round(rnd.uniform(1200, 980000), 2)))
                evento_dt = now - timedelta(days=rnd.randint(0, 730), minutes=rnd.randint(0, 1440))
                novos.append(
                    TransparenciaEventoPublico(
                        municipio=municipio,
                        modulo=modulo,
                        tipo_evento=rnd.choice(
                            [
                                "PAGAMENTO_EXECUTADO",
                                "CONTRATO_PUBLICADO",
                                "LICITACAO_HOMOLOGADA",
                                "PROCESSO_PROTOCOLADO",
                                "INTEGRACAO_EXECUTADA",
                                "DADOS_ATUALIZADOS",
                            ]
                        ),
                        titulo=f"Evento público {idx+1:05d} - {modulo}",
                        descricao="Registro público para painel de transparência ativa.",
                        referencia=f"SAN-TRP-{today.year}-{idx+1:06d}",
                        valor=valor,
                        data_evento=evento_dt,
                        dados={
                            "municipio": municipio.nome,
                            "fonte": "seed_100k",
                            "modulo": modulo,
                            "ano_referencia": evento_dt.year,
                        },
                        publico=True,
                    )
                )
            TransparenciaEventoPublico.objects.bulk_create(novos, batch_size=1000)

        self.stdout.write("9) Garantindo portal público e conteúdo base...")
        portal_result = ensure_portal_seed_for_municipio(municipio, autor=seed_user, force=True)

        resumo = {
            "Perfis ativos": Profile.objects.filter(municipio=municipio, ativo=True).count(),
            "Servidores RH": RhCadastro.objects.filter(municipio=municipio).count(),
            "Secretarias": Secretaria.objects.filter(municipio=municipio, ativo=True).count(),
            "Unidades": Unidade.objects.filter(secretaria__municipio=municipio, ativo=True).count(),
            "Setores": Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True).count(),
            "Cursos": Curso.objects.filter(turmas__unidade__in=unidades_edu).distinct().count(),
            "Turmas (ano atual)": Turma.objects.filter(unidade__in=unidades_edu, ano_letivo=today.year).count(),
            "Alunos (rede municipal)": Aluno.objects.filter(matriculas__turma__unidade__in=unidades_edu).distinct().count(),
            "Matrículas (rede municipal)": Matricula.objects.filter(turma__unidade__in=unidades_edu).count(),
            "Horários de aula": HorarioAula.objects.filter(turma__unidade__in=unidades_edu).count(),
            "Pacientes": PacienteSaude.objects.filter(unidade_referencia__in=unidades_saude).count(),
            "Profissionais saúde": ProfissionalSaude.objects.filter(unidade__in=unidades_saude).count(),
            "Atendimentos saúde": AtendimentoSaude.objects.filter(unidade__in=unidades_saude).count(),
            "Agendamentos saúde": AgendamentoSaude.objects.filter(unidade__in=unidades_saude).count(),
            "Fila saúde": FilaEsperaSaude.objects.filter(unidade__in=unidades_saude).count(),
            "Necessidades NEE": AlunoNecessidade.objects.filter(aluno__in=alunos_municipio_ids).count(),
            "Acompanhamentos NEE": AcompanhamentoNEE.objects.filter(aluno__in=alunos_municipio_ids).count(),
            "Planos clínicos NEE": PlanoClinicoNEE.objects.filter(aluno__in=alunos_municipio_ids).count(),
            "Contratos": ContratoAdministrativo.objects.filter(municipio=municipio).count(),
            "Medições de contrato": MedicaoContrato.objects.filter(contrato__municipio=municipio).count(),
            "Conectores": ConectorIntegracao.objects.filter(municipio=municipio).count(),
            "Execuções integrações": IntegracaoExecucao.objects.filter(municipio=municipio).count(),
            "Datasets BI": Dataset.objects.filter(municipio=municipio).count(),
            "Exports BI": ExportJob.objects.filter(dataset__municipio=municipio).count(),
            "Jobs conversor": ConversionJob.objects.filter(municipio=municipio).count(),
            "Templates comunicação": NotificationTemplate.objects.filter(municipio=municipio).count(),
            "Jobs comunicação": NotificationJob.objects.filter(municipio=municipio).count(),
            "Ouvidoria/e-SIC": OuvidoriaCadastro.objects.filter(municipio=municipio).count(),
            "Eventos transparência": TransparenciaEventoPublico.objects.filter(municipio=municipio, publico=True).count(),
        }

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Seed 100k concluído para {municipio.nome}/{municipio.uf}."))
        self.stdout.write(
            f"Portal público: config_criada={int(bool(portal_result.config_created))}, "
            f"banners={portal_result.banners_created}, noticias={portal_result.noticias_created}, "
            f"paginas={portal_result.paginas_created}, menus={portal_result.menus_created}, blocos={portal_result.blocos_created}"
        )
        self.stdout.write("")
        for chave, valor in resumo.items():
            self.stdout.write(f" - {chave}: {valor}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Usuário de referência para operação:"))
        self.stdout.write(f" - {seed_user.username} (senha padrão definida no comando)")
