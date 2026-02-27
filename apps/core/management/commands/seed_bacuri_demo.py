from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Popula dados ficticios completos para demonstracao da prefeitura de Bacuri."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="bacuri", help="Slug do municipio alvo (padrao: bacuri).")
        parser.add_argument(
            "--password",
            default="12345678",
            help="Senha padrao para os usuarios de demonstracao criados/atualizados.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Imports tardios para reduzir risco de carregamento circular.
        from apps.accounts.models import Profile
        from apps.almoxarifado.models import (
            AlmoxarifadoCadastro,
            AlmoxarifadoMovimento,
            AlmoxarifadoRequisicao,
        )
        from apps.compras.models import ProcessoLicitatorio, RequisicaoCompra, RequisicaoCompraItem
        from apps.contratos.models import AditivoContrato, ContratoAdministrativo, MedicaoContrato
        from apps.educacao.models import (
            Aluno,
            AlunoCertificado,
            AlunoDocumento,
            Curso,
            CursoDisciplina,
            Matricula,
            MatriculaCurso,
            Turma,
        )
        from apps.financeiro.models import (
            DespEmpenho,
            DespLiquidacao,
            DespPagamento,
            DespPagamentoResto,
            DespRestosPagar,
            FinanceiroContaBancaria,
            FinanceiroExercicio,
            FinanceiroLogEvento,
            FinanceiroUnidadeGestora,
            OrcCreditoAdicional,
            OrcDotacao,
            OrcFonteRecurso,
            RecArrecadacao,
            RecConciliacaoItem,
            TesExtratoImportacao,
            TesExtratoItem,
        )
        from apps.folha.models import (
            FolhaCadastro,
            FolhaCompetencia,
            FolhaIntegracaoFinanceiro,
            FolhaLancamento,
        )
        from apps.frota.models import FrotaAbastecimento, FrotaCadastro, FrotaManutencao, FrotaViagem
        from apps.org.models import (
            Municipio,
            MunicipioModuloAtivo,
            OnboardingStep,
            Secretaria,
            SecretariaModuloAtivo,
            Setor,
            Unidade,
        )
        from apps.ouvidoria.models import OuvidoriaCadastro, OuvidoriaResposta, OuvidoriaTramitacao
        from apps.ponto.models import (
            PontoCadastro,
            PontoFechamentoCompetencia,
            PontoOcorrencia,
            PontoVinculoEscala,
        )
        from apps.processos.models import ProcessoAdministrativo, ProcessoAndamento
        from apps.rh.models import RhCadastro, RhDocumento, RhMovimentacao
        from apps.saude.models import (
            AgendamentoSaude,
            AlergiaSaude,
            AtendimentoSaude,
            AuditoriaAcessoProntuarioSaude,
            AuditoriaAlteracaoSaude,
            BloqueioAgendaSaude,
            CidSaude,
            CheckInSaude,
            DispensacaoSaude,
            DocumentoClinicoSaude,
            EncaminhamentoSaude,
            EspecialidadeSaude,
            EvolucaoClinicaSaude,
            ExameColetaSaude,
            ExamePedidoSaude,
            ExameResultadoSaude,
            FilaEsperaSaude,
            GradeAgendaSaude,
            InternacaoRegistroSaude,
            InternacaoSaude,
            MedicamentoUsoContinuoSaude,
            PacienteSaude,
            PrescricaoItemSaude,
            PrescricaoSaude,
            ProcedimentoSaude,
            ProfissionalSaude,
            ProgramaSaude,
            SalaSaude,
            TriagemSaude,
            VacinacaoSaude,
        )
        from apps.tributos.models import TributoLancamento, TributosCadastro

        slug = (options["slug"] or "").strip().lower()
        password = options["password"]
        today = timezone.localdate()
        now = timezone.now()
        current_year = today.year
        previous_year = current_year - 1
        competencia_atual = f"{current_year}-{today.month:02d}"

        municipio = Municipio.objects.filter(slug_site=slug).first()
        if not municipio:
            municipio = Municipio.objects.filter(nome__iexact=slug).first()
        if not municipio:
            raise CommandError(f"Municipio nao encontrado para slug/nome '{slug}'.")

        self.stdout.write(self.style.WARNING(f"Seed Bacuri demo iniciado para: {municipio}"))

        User = get_user_model()

        def apply_updates(obj, **fields):
            changed = False
            for field, value in fields.items():
                if not hasattr(obj, field):
                    continue
                if getattr(obj, field) != value:
                    setattr(obj, field, value)
                    changed = True
            if changed:
                obj.save()
            return obj

        def ensure_secretaria(nome: str, tipo_modelo: str, aliases: list[str]) -> Secretaria:
            qs = Secretaria.objects.filter(municipio=municipio)
            secretaria = None
            if tipo_modelo:
                secretaria = qs.filter(tipo_modelo=tipo_modelo).order_by("id").first()
            if not secretaria:
                for alias in aliases:
                    secretaria = qs.filter(nome__icontains=alias).order_by("id").first()
                    if secretaria:
                        break
            if not secretaria:
                secretaria = Secretaria.objects.create(
                    municipio=municipio,
                    nome=nome,
                    tipo_modelo=tipo_modelo,
                    ativo=True,
                )
            return apply_updates(secretaria, nome=secretaria.nome or nome, tipo_modelo=tipo_modelo, ativo=True)

        def ensure_unidade(secretaria: Secretaria, nome: str, tipo: str) -> Unidade:
            unidade, _ = Unidade.objects.get_or_create(
                secretaria=secretaria,
                nome=nome,
                defaults={"tipo": tipo, "ativo": True},
            )
            return apply_updates(unidade, tipo=tipo, ativo=True)

        def ensure_setor(unidade: Unidade, nome: str) -> Setor:
            setor, _ = Setor.objects.get_or_create(unidade=unidade, nome=nome, defaults={"ativo": True})
            return apply_updates(setor, ativo=True)

        def ensure_user(
            username: str,
            full_name: str,
            role: str,
            secretaria: Secretaria | None,
            unidade: Unidade | None,
            setor: Setor | None,
            email: str,
            is_staff: bool = False,
            is_superuser: bool = False,
        ):
            name_parts = [part for part in full_name.strip().split(" ") if part]
            first_name = name_parts[0] if name_parts else full_name.strip()
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": True,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                },
            )
            apply_updates(
                user,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_staff=is_staff or user.is_staff,
                is_superuser=is_superuser or user.is_superuser,
            )
            user.set_password(password)
            user.save(update_fields=["password"])

            profile, _ = Profile.objects.get_or_create(user=user, defaults={"ativo": True})
            apply_updates(
                profile,
                role=role,
                municipio=municipio,
                secretaria=secretaria,
                unidade=unidade,
                setor=setor,
                ativo=True,
                bloqueado=False,
                must_change_password=False,
            )
            return user, profile

        def ensure_module(municipio_or_secretaria, module_name: str):
            if isinstance(municipio_or_secretaria, Secretaria):
                row, _ = SecretariaModuloAtivo.objects.get_or_create(
                    secretaria=municipio_or_secretaria,
                    modulo=module_name,
                    defaults={"ativo": True},
                )
            else:
                row, _ = MunicipioModuloAtivo.objects.get_or_create(
                    municipio=municipio_or_secretaria,
                    modulo=module_name,
                    defaults={"ativo": True},
                )
            if not row.ativo:
                row.ativo = True
                row.save(update_fields=["ativo"])
            return row

        def dt_at(base_date: date, hh: int, mm: int = 0) -> datetime:
            naive = datetime.combine(base_date, time(hh, mm))
            if timezone.is_aware(now):
                return timezone.make_aware(naive, timezone.get_current_timezone())
            return naive

        # 1) Estrutura institucional de referencia
        sec_admin = ensure_secretaria("Secretaria de Administração", "administracao", ["Administração"])
        sec_saude = ensure_secretaria("Secretaria de Saúde", "saude", ["Saúde"])
        sec_educacao = ensure_secretaria("Secretaria de Educação", "educacao", ["Educação"])
        sec_financas = ensure_secretaria("Secretaria de Finanças e Fazenda", "financas", ["Finanças", "Fazenda"])
        sec_obras = ensure_secretaria("Secretaria de Obras e Engenharia", "obras", ["Obras"])
        sec_agricultura = ensure_secretaria("Secretaria de Agricultura", "agricultura", ["Agricultura"])
        sec_assistencia = ensure_secretaria("Secretaria de Assistência Social", "assistencia", ["Assistência"])
        sec_transporte = ensure_secretaria("Secretaria de Transporte e Mobilidade", "transporte", ["Transporte"])
        sec_tecnologia = ensure_secretaria("Secretaria de Tecnologia e Inovação", "tecnologia", ["Tecnologia"])
        sec_servicos = ensure_secretaria("Secretaria de Serviços Públicos", "servicos_publicos", ["Serviços Públicos"])
        sec_planejamento = ensure_secretaria(
            "Secretaria de Planejamento e Controle Interno",
            "planejamento",
            ["Planejamento"],
        )

        un_admin = ensure_unidade(sec_admin, "Sede Administrativa Bacuri", Unidade.Tipo.ADMINISTRACAO)
        un_financas = ensure_unidade(sec_financas, "Tesouraria Municipal", Unidade.Tipo.FINANCAS)
        un_educacao = Unidade.objects.filter(secretaria__municipio=municipio, tipo=Unidade.Tipo.EDUCACAO).first()
        if not un_educacao:
            un_educacao = ensure_unidade(sec_educacao, "Escola Municipal Bacuri Sede", Unidade.Tipo.EDUCACAO)
        un_saude_ubs = ensure_unidade(sec_saude, "UBS Centro Bacuri", Unidade.Tipo.SAUDE)
        un_saude_hospital = ensure_unidade(sec_saude, "Hospital Municipal de Bacuri", Unidade.Tipo.SAUDE)
        un_obras = ensure_unidade(sec_obras, "Diretoria de Obras", Unidade.Tipo.INFRAESTRUTURA)
        un_agricultura = ensure_unidade(sec_agricultura, "Coordenação de Produção Rural", Unidade.Tipo.AGRICULTURA)
        un_assistencia = ensure_unidade(sec_assistencia, "CRAS Bacuri Sede", Unidade.Tipo.ASSISTENCIA)
        un_transporte = ensure_unidade(sec_transporte, "Central de Transportes", Unidade.Tipo.TRANSPORTE)
        un_tecnologia = ensure_unidade(sec_tecnologia, "Núcleo de Tecnologia da Informação", Unidade.Tipo.TECNOLOGIA)
        un_servicos = ensure_unidade(sec_servicos, "Coordenação de Limpeza Urbana", Unidade.Tipo.SERVICOS_PUBLICOS)
        un_planejamento = ensure_unidade(sec_planejamento, "Gestão Estratégica", Unidade.Tipo.PLANEJAMENTO)

        set_admin = ensure_setor(un_admin, "Administração Geral")
        set_rh = ensure_setor(un_admin, "Recursos Humanos")
        set_licitacoes = ensure_setor(un_admin, "Licitações e Contratos")
        set_almox = ensure_setor(un_admin, "Almoxarifado Central")
        set_ouvidoria = ensure_setor(un_admin, "Ouvidoria Municipal")
        set_fin_exec = ensure_setor(un_financas, "Execução Orçamentária")
        set_tributos = ensure_setor(un_financas, "Arrecadação e Tributos")
        set_saude_atendimento = ensure_setor(un_saude_ubs, "Atendimento Clínico")
        set_saude_enfermagem = ensure_setor(un_saude_ubs, "Enfermagem")
        set_saude_farmacia = ensure_setor(un_saude_ubs, "Farmácia")
        set_obras_exec = ensure_setor(un_obras, "Fiscalização de Obras")
        set_transporte_frota = ensure_setor(un_transporte, "Gestão de Frota")
        set_educacao_coord = ensure_setor(un_educacao, "Coordenação Pedagógica")
        set_tecnologia_suporte = ensure_setor(un_tecnologia, "Suporte Técnico")
        set_assistencia_atendimento = ensure_setor(un_assistencia, "Atendimento Social")

        # 2) Ativacao de modulos no municipio e por secretaria
        municipality_modules = [
            "educacao",
            "nee",
            "saude",
            "financeiro",
            "processos",
            "compras",
            "contratos",
            "integracoes",
            "rh",
            "ponto",
            "folha",
            "patrimonio",
            "almoxarifado",
            "frota",
            "ouvidoria",
            "tributos",
        ]
        for module_name in municipality_modules:
            ensure_module(municipio, module_name)

        modules_by_secretaria = {
            sec_admin: ["processos", "rh", "ponto", "folha", "almoxarifado", "ouvidoria"],
            sec_saude: ["saude", "almoxarifado"],
            sec_educacao: ["educacao", "nee"],
            sec_financas: ["financeiro", "tributos", "compras", "contratos"],
            sec_obras: ["compras", "contratos", "frota", "processos"],
            sec_agricultura: ["processos", "frota", "almoxarifado"],
            sec_assistencia: ["processos", "ouvidoria"],
            sec_transporte: ["frota", "processos"],
            sec_tecnologia: ["integracoes", "processos"],
            sec_servicos: ["processos", "frota", "almoxarifado"],
            sec_planejamento: ["processos", "financeiro"],
        }
        for secretaria, module_names in modules_by_secretaria.items():
            for module_name in module_names:
                ensure_module(secretaria, module_name)

        # 3) Usuarios e perfis de demonstracao
        user_municipal, _ = ensure_user(
            "bacuri.gestor.municipal",
            "Gabriela Nunes",
            Profile.Role.MUNICIPAL,
            sec_admin,
            un_admin,
            set_admin,
            "gabriela.nunes@bacuri.ma.gov.br",
            is_staff=True,
        )
        user_rh, _ = ensure_user(
            "bacuri.rh.ana",
            "Ana Beatriz Lima",
            Profile.Role.UNIDADE,
            sec_admin,
            un_admin,
            set_rh,
            "ana.lima@bacuri.ma.gov.br",
        )
        user_contador, _ = ensure_user(
            "bacuri.contador.carlos",
            "Carlos Eduardo Alves",
            Profile.Role.UNIDADE,
            sec_financas,
            un_financas,
            set_fin_exec,
            "carlos.alves@bacuri.ma.gov.br",
        )
        user_licitacoes, _ = ensure_user(
            "bacuri.licitacoes.julia",
            "Julia Ferreira Sousa",
            Profile.Role.UNIDADE,
            sec_admin,
            un_admin,
            set_licitacoes,
            "julia.sousa@bacuri.ma.gov.br",
        )
        user_medico, _ = ensure_user(
            "bacuri.medico.bruno",
            "Bruno Henrique Azevedo",
            Profile.Role.UNIDADE,
            sec_saude,
            un_saude_ubs,
            set_saude_atendimento,
            "bruno.azevedo@bacuri.ma.gov.br",
        )
        user_enfermeira, _ = ensure_user(
            "bacuri.enfermeira.lucia",
            "Lucia Maria Cardoso",
            Profile.Role.UNIDADE,
            sec_saude,
            un_saude_ubs,
            set_saude_enfermagem,
            "lucia.cardoso@bacuri.ma.gov.br",
        )
        user_farmaceutica, _ = ensure_user(
            "bacuri.farmaceutica.helena",
            "Helena Rocha Menezes",
            Profile.Role.UNIDADE,
            sec_saude,
            un_saude_ubs,
            set_saude_farmacia,
            "helena.menezes@bacuri.ma.gov.br",
        )
        user_professor, _ = ensure_user(
            "bacuri.professora.maria",
            "Maria Clara Ribeiro",
            Profile.Role.PROFESSOR,
            sec_educacao,
            un_educacao,
            set_educacao_coord,
            "maria.ribeiro@bacuri.ma.gov.br",
        )
        user_motorista, _ = ensure_user(
            "bacuri.motorista.joao",
            "Joao Pedro Barbosa",
            Profile.Role.UNIDADE,
            sec_transporte,
            un_transporte,
            set_transporte_frota,
            "joao.barbosa@bacuri.ma.gov.br",
        )
        user_ouvidoria, _ = ensure_user(
            "bacuri.ouvidoria.paulo",
            "Paulo Vinicius Costa",
            Profile.Role.UNIDADE,
            sec_admin,
            un_admin,
            set_ouvidoria,
            "paulo.costa@bacuri.ma.gov.br",
        )

        # 4) Educacao (base para saude/boletim/certificados)
        curso_regular, _ = Curso.objects.get_or_create(
            nome="Ensino Regular Municipal",
            codigo="REG-BAC-2026",
            defaults={
                "modalidade_oferta": Curso.ModalidadeOferta.REGULAR,
                "eixo_tecnologico": "",
                "carga_horaria": 800,
                "ativo": True,
            },
        )
        apply_updates(curso_regular, modalidade_oferta=Curso.ModalidadeOferta.REGULAR, carga_horaria=800, ativo=True)

        curso_robotica, _ = Curso.objects.get_or_create(
            nome="Curso Livre de Robótica Educacional",
            codigo="ROB-BAC-2026",
            defaults={
                "modalidade_oferta": Curso.ModalidadeOferta.LIVRE,
                "eixo_tecnologico": "Informação e Comunicação",
                "carga_horaria": 120,
                "ativo": True,
            },
        )
        apply_updates(curso_robotica, modalidade_oferta=Curso.ModalidadeOferta.LIVRE, carga_horaria=120, ativo=True)

        for ordem, disciplina in enumerate(
            [
                ("Pensamento Computacional", CursoDisciplina.TipoAula.TEORICA, 30),
                ("Programação em Blocos", CursoDisciplina.TipoAula.LABORATORIO, 45),
                ("Robótica Aplicada", CursoDisciplina.TipoAula.OFICINA, 45),
            ],
            start=1,
        ):
            CursoDisciplina.objects.get_or_create(
                curso=curso_robotica,
                nome=disciplina[0],
                defaults={
                    "tipo_aula": disciplina[1],
                    "carga_horaria": disciplina[2],
                    "ordem": ordem,
                    "obrigatoria": True,
                    "ativo": True,
                },
            )

        turma_regular, _ = Turma.objects.get_or_create(
            unidade=un_educacao,
            nome="6º Ano A",
            ano_letivo=current_year,
            defaults={
                "turno": Turma.Turno.MANHA,
                "modalidade": Turma.Modalidade.REGULAR,
                "etapa": Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS,
                "forma_oferta": Turma.FormaOferta.PRESENCIAL,
                "curso": curso_regular,
                "ativo": True,
            },
        )
        apply_updates(
            turma_regular,
            turno=Turma.Turno.MANHA,
            modalidade=Turma.Modalidade.REGULAR,
            etapa=Turma.Etapa.FUNDAMENTAL_ANOS_FINAIS,
            forma_oferta=Turma.FormaOferta.PRESENCIAL,
            curso=curso_regular,
            ativo=True,
        )
        turma_regular.professores.add(user_professor)

        turma_robotica, _ = Turma.objects.get_or_create(
            unidade=un_educacao,
            nome="Oficina de Robótica",
            ano_letivo=current_year,
            defaults={
                "turno": Turma.Turno.TARDE,
                "modalidade": Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
                "etapa": Turma.Etapa.FIC,
                "forma_oferta": Turma.FormaOferta.PRESENCIAL,
                "curso": curso_robotica,
                "ativo": True,
            },
        )
        apply_updates(
            turma_robotica,
            turno=Turma.Turno.TARDE,
            modalidade=Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
            etapa=Turma.Etapa.FIC,
            forma_oferta=Turma.FormaOferta.PRESENCIAL,
            curso=curso_robotica,
            ativo=True,
        )
        turma_robotica.professores.add(user_professor)

        alunos_definidos = [
            ("Aluno Bacuri Rafael Nunes", date(current_year - 11, 5, 17), "12345678901"),
            ("Aluno Bacuri Amanda Costa", date(current_year - 10, 8, 9), "98765432100"),
            ("Aluno Bacuri Tiago Pereira", date(current_year - 11, 2, 27), "32165498700"),
            ("Aluno Bacuri Joana Alves", date(current_year - 10, 11, 3), "65498732100"),
        ]
        alunos = []
        for nome_aluno, nascimento, cpf in alunos_definidos:
            aluno, _ = Aluno.objects.get_or_create(
                nome=nome_aluno,
                defaults={
                    "data_nascimento": nascimento,
                    "cpf": cpf,
                    "nome_mae": f"{nome_aluno.split()[2]} Maria",
                    "nome_pai": f"{nome_aluno.split()[2]} Jose",
                    "telefone": "(98) 99100-0000",
                    "email": f"{nome_aluno.lower().replace(' ', '.')}@aluno.bacuri.ma.gov.br",
                    "endereco": "Rua Principal, Centro, Bacuri/MA",
                    "ativo": True,
                },
            )
            apply_updates(aluno, ativo=True)
            alunos.append(aluno)
            Matricula.objects.get_or_create(
                aluno=aluno,
                turma=turma_regular,
                defaults={
                    "data_matricula": date(current_year, 1, 20),
                    "situacao": Matricula.Situacao.ATIVA,
                    "resultado_final": "",
                    "concluinte": False,
                },
            )

        for aluno in alunos[:3]:
            MatriculaCurso.objects.get_or_create(
                aluno=aluno,
                curso=curso_robotica,
                turma=turma_robotica,
                defaults={
                    "data_matricula": date(current_year, 2, 5),
                    "situacao": MatriculaCurso.Situacao.EM_ANDAMENTO,
                    "cadastrado_por": user_professor,
                    "observacao": "Matrícula complementar em curso livre.",
                },
            )

        for aluno in alunos[:2]:
            AlunoDocumento.objects.get_or_create(
                aluno=aluno,
                tipo=AlunoDocumento.Tipo.HISTORICO,
                titulo=f"Histórico parcial {current_year}",
                defaults={
                    "numero_documento": f"HIST-{current_year}-{aluno.id}",
                    "data_emissao": today - timedelta(days=30),
                    "observacao": "Documento ficticio para ambiente de demonstracao.",
                    "enviado_por": user_professor,
                    "ativo": True,
                },
            )
            AlunoCertificado.objects.get_or_create(
                aluno=aluno,
                curso=curso_robotica,
                tipo=AlunoCertificado.Tipo.CERTIFICADO_CURSO,
                titulo="Certificado parcial - Robótica Educacional",
                defaults={
                    "data_emissao": today - timedelta(days=10),
                    "carga_horaria": 40,
                    "resultado_final": "Em andamento",
                    "observacao": "Documento ficticio para homologacao visual.",
                    "emitido_por": user_professor,
                    "ativo": True,
                },
            )

        # 5) Financeiro + compras + contratos + processos
        exercicio_atual, _ = FinanceiroExercicio.objects.get_or_create(
            municipio=municipio,
            ano=current_year,
            defaults={
                "status": FinanceiroExercicio.Status.ABERTO,
                "inicio_em": date(current_year, 1, 1),
                "fim_em": date(current_year, 12, 31),
                "fechamento_mensal_ate": max(1, today.month - 1),
                "observacoes": "Exercicio de demonstracao Bacuri.",
            },
        )
        apply_updates(
            exercicio_atual,
            status=FinanceiroExercicio.Status.ABERTO,
            fechamento_mensal_ate=max(1, today.month - 1),
        )

        exercicio_anterior, _ = FinanceiroExercicio.objects.get_or_create(
            municipio=municipio,
            ano=previous_year,
            defaults={
                "status": FinanceiroExercicio.Status.ENCERRADO,
                "inicio_em": date(previous_year, 1, 1),
                "fim_em": date(previous_year, 12, 31),
                "fechamento_mensal_ate": 12,
                "observacoes": "Exercicio encerrado ficticio.",
            },
        )
        apply_updates(exercicio_anterior, status=FinanceiroExercicio.Status.ENCERRADO, fechamento_mensal_ate=12)

        ug_principal, _ = FinanceiroUnidadeGestora.objects.get_or_create(
            municipio=municipio,
            codigo="001",
            defaults={
                "nome": "Prefeitura Municipal de Bacuri",
                "secretaria": sec_financas,
                "unidade": un_financas,
                "ativo": True,
            },
        )
        apply_updates(ug_principal, nome="Prefeitura Municipal de Bacuri", secretaria=sec_financas, unidade=un_financas, ativo=True)

        conta_bb, _ = FinanceiroContaBancaria.objects.get_or_create(
            unidade_gestora=ug_principal,
            banco_codigo="001",
            agencia="1450-2",
            conta="12345-6",
            defaults={
                "municipio": municipio,
                "banco_nome": "Banco do Brasil",
                "tipo_conta": FinanceiroContaBancaria.TipoConta.MOVIMENTO,
                "saldo_atual": Decimal("258430.72"),
                "ativo": True,
            },
        )
        apply_updates(conta_bb, municipio=municipio, banco_nome="Banco do Brasil", ativo=True)

        fonte_fpm, _ = OrcFonteRecurso.objects.get_or_create(
            municipio=municipio,
            codigo="1500",
            defaults={"nome": "Recursos não vinculados de impostos", "ativo": True},
        )
        fonte_sus, _ = OrcFonteRecurso.objects.get_or_create(
            municipio=municipio,
            codigo="1600",
            defaults={"nome": "Transferências fundo a fundo do SUS", "ativo": True},
        )
        apply_updates(fonte_fpm, ativo=True)
        apply_updates(fonte_sus, ativo=True)

        dotacao_admin, _ = OrcDotacao.objects.get_or_create(
            exercicio=exercicio_atual,
            unidade_gestora=ug_principal,
            programa_codigo="04.122.0001",
            acao_codigo="2001",
            elemento_despesa="3.3.90.39",
            fonte=fonte_fpm,
            defaults={
                "municipio": municipio,
                "secretaria": sec_admin,
                "programa_nome": "Gestão administrativa",
                "acao_nome": "Manutenção da administração geral",
                "valor_inicial": Decimal("600000.00"),
                "valor_atualizado": Decimal("720000.00"),
                "valor_empenhado": Decimal("0.00"),
                "valor_liquidado": Decimal("0.00"),
                "valor_pago": Decimal("0.00"),
                "ativo": True,
            },
        )
        dotacao_saude, _ = OrcDotacao.objects.get_or_create(
            exercicio=exercicio_atual,
            unidade_gestora=ug_principal,
            programa_codigo="10.301.0008",
            acao_codigo="2091",
            elemento_despesa="3.3.90.30",
            fonte=fonte_sus,
            defaults={
                "municipio": municipio,
                "secretaria": sec_saude,
                "programa_nome": "Atenção básica em saúde",
                "acao_nome": "Manutenção da atenção primária",
                "valor_inicial": Decimal("950000.00"),
                "valor_atualizado": Decimal("1120000.00"),
                "valor_empenhado": Decimal("0.00"),
                "valor_liquidado": Decimal("0.00"),
                "valor_pago": Decimal("0.00"),
                "ativo": True,
            },
        )
        apply_updates(dotacao_admin, municipio=municipio, secretaria=sec_admin, ativo=True)
        apply_updates(dotacao_saude, municipio=municipio, secretaria=sec_saude, ativo=True)

        OrcCreditoAdicional.objects.get_or_create(
            municipio=municipio,
            exercicio=exercicio_atual,
            dotacao=dotacao_saude,
            numero_ato=f"DECRETO-{current_year}-017",
            defaults={
                "tipo": OrcCreditoAdicional.Tipo.SUPLEMENTAR,
                "data_ato": today - timedelta(days=45),
                "valor": Decimal("120000.00"),
                "origem_recurso": "Superavit financeiro",
                "descricao": "Reforço da dotação da atenção básica.",
                "criado_por": user_contador,
            },
        )

        processo_compra, _ = ProcessoAdministrativo.objects.get_or_create(
            municipio=municipio,
            numero=f"PROC-{current_year}-0001",
            defaults={
                "secretaria": sec_admin,
                "unidade": un_admin,
                "setor": set_licitacoes,
                "tipo": "COMPRA",
                "assunto": "Aquisição de insumos para UBS e escolas",
                "solicitante_nome": "Coordenação de Compras",
                "descricao": "Processo administrativo para aquisição de materiais de consumo.",
                "status": ProcessoAdministrativo.Status.EM_TRAMITACAO,
                "responsavel_atual": user_licitacoes,
                "data_abertura": today - timedelta(days=60),
                "prazo_final": today + timedelta(days=20),
                "criado_por": user_municipal,
            },
        )
        apply_updates(
            processo_compra,
            secretaria=sec_admin,
            unidade=un_admin,
            setor=set_licitacoes,
            status=ProcessoAdministrativo.Status.EM_TRAMITACAO,
            responsavel_atual=user_licitacoes,
        )
        ProcessoAndamento.objects.get_or_create(
            processo=processo_compra,
            tipo=ProcessoAndamento.Tipo.ENCAMINHAMENTO,
            data_evento=today - timedelta(days=58),
            defaults={
                "setor_origem": set_admin,
                "setor_destino": set_licitacoes,
                "despacho": "Encaminhado ao setor de licitações para formalização do termo de referência.",
                "prazo": today - timedelta(days=45),
                "criado_por": user_municipal,
            },
        )
        ProcessoAndamento.objects.get_or_create(
            processo=processo_compra,
            tipo=ProcessoAndamento.Tipo.DESPACHO,
            data_evento=today - timedelta(days=40),
            defaults={
                "setor_origem": set_licitacoes,
                "setor_destino": set_fin_exec,
                "despacho": "Dotação confirmada e processo apto à fase externa.",
                "prazo": today - timedelta(days=35),
                "criado_por": user_licitacoes,
            },
        )

        requisicao, _ = RequisicaoCompra.objects.get_or_create(
            municipio=municipio,
            numero=f"REQ-{current_year}-0012",
            defaults={
                "processo": processo_compra,
                "secretaria": sec_saude,
                "unidade": un_saude_ubs,
                "setor": set_saude_farmacia,
                "objeto": "Aquisição de medicamentos e material de enfermagem",
                "justificativa": "Reposição de estoque para atendimento da atenção básica.",
                "valor_estimado": Decimal("84500.00"),
                "data_necessidade": today + timedelta(days=15),
                "status": RequisicaoCompra.Status.HOMOLOGADA,
                "fornecedor_nome": "Farma Norte Distribuidora LTDA",
                "fornecedor_documento": "12.345.678/0001-90",
                "dotacao": dotacao_saude,
                "criado_por": user_licitacoes,
                "aprovado_por": user_contador,
                "aprovado_em": now - timedelta(days=30),
            },
        )
        apply_updates(
            requisicao,
            processo=processo_compra,
            secretaria=sec_saude,
            unidade=un_saude_ubs,
            setor=set_saude_farmacia,
            status=RequisicaoCompra.Status.HOMOLOGADA,
            dotacao=dotacao_saude,
            aprovado_por=user_contador,
        )

        RequisicaoCompraItem.objects.get_or_create(
            requisicao=requisicao,
            descricao="Dipirona sódica 500mg comprimido",
            defaults={
                "unidade_medida": "CX",
                "quantidade": Decimal("350.00"),
                "valor_unitario": Decimal("28.50"),
            },
        )
        RequisicaoCompraItem.objects.get_or_create(
            requisicao=requisicao,
            descricao="Luva de procedimento tamanho M",
            defaults={
                "unidade_medida": "CX",
                "quantidade": Decimal("420.00"),
                "valor_unitario": Decimal("22.90"),
            },
        )

        licitacao, _ = ProcessoLicitatorio.objects.get_or_create(
            municipio=municipio,
            numero_processo=f"PE-{current_year}-0005",
            defaults={
                "requisicao": requisicao,
                "modalidade": ProcessoLicitatorio.Modalidade.PREGAO,
                "objeto": requisicao.objeto,
                "status": ProcessoLicitatorio.Status.HOMOLOGADO,
                "data_abertura": today - timedelta(days=32),
                "vencedor_nome": "Farma Norte Distribuidora LTDA",
            },
        )
        apply_updates(
            licitacao,
            requisicao=requisicao,
            status=ProcessoLicitatorio.Status.HOMOLOGADO,
            vencedor_nome="Farma Norte Distribuidora LTDA",
        )

        empenho, _ = DespEmpenho.objects.get_or_create(
            exercicio=exercicio_atual,
            numero=f"EMP-{current_year}-0456",
            defaults={
                "municipio": municipio,
                "unidade_gestora": ug_principal,
                "dotacao": dotacao_saude,
                "data_empenho": today - timedelta(days=25),
                "fornecedor_nome": "Farma Norte Distribuidora LTDA",
                "fornecedor_documento": "12.345.678/0001-90",
                "objeto": "Aquisição de medicamentos e material de enfermagem - PE 0005",
                "tipo": DespEmpenho.Tipo.ORDINARIO,
                "valor_empenhado": Decimal("79000.00"),
                "valor_liquidado": Decimal("43000.00"),
                "valor_pago": Decimal("43000.00"),
                "status": DespEmpenho.Status.PAGO,
                "criado_por": user_contador,
            },
        )
        apply_updates(
            empenho,
            municipio=municipio,
            unidade_gestora=ug_principal,
            dotacao=dotacao_saude,
            valor_empenhado=Decimal("79000.00"),
            valor_liquidado=Decimal("43000.00"),
            valor_pago=Decimal("43000.00"),
            status=DespEmpenho.Status.PAGO,
        )
        if requisicao.empenho_id != empenho.id:
            requisicao.empenho = empenho
            requisicao.save(update_fields=["empenho"])

        liquidacao, _ = DespLiquidacao.objects.get_or_create(
            empenho=empenho,
            numero=f"LIQ-{current_year}-0188",
            defaults={
                "data_liquidacao": today - timedelta(days=15),
                "documento_fiscal": "NF-887761",
                "observacao": "Liquidação parcial conforme entrega recebida pela farmácia.",
                "valor_liquidado": Decimal("43000.00"),
                "criado_por": user_contador,
            },
        )
        apply_updates(liquidacao, valor_liquidado=Decimal("43000.00"), documento_fiscal="NF-887761")

        pagamento, _ = DespPagamento.objects.get_or_create(
            liquidacao=liquidacao,
            ordem_pagamento=f"OP-{current_year}-0322",
            defaults={
                "conta_bancaria": conta_bb,
                "data_pagamento": today - timedelta(days=10),
                "valor_pago": Decimal("43000.00"),
                "status": DespPagamento.Status.PAGO,
                "criado_por": user_contador,
            },
        )
        apply_updates(pagamento, conta_bancaria=conta_bb, valor_pago=Decimal("43000.00"), status=DespPagamento.Status.PAGO)

        resto, _ = DespRestosPagar.objects.get_or_create(
            exercicio_inscricao=exercicio_atual,
            numero_inscricao=f"RP-{current_year}-0021",
            defaults={
                "municipio": municipio,
                "exercicio_origem": exercicio_anterior,
                "empenho": empenho,
                "tipo": DespRestosPagar.Tipo.PROCESSADO,
                "data_inscricao": today - timedelta(days=8),
                "valor_inscrito": Decimal("9000.00"),
                "valor_pago": Decimal("3000.00"),
                "status": DespRestosPagar.Status.PARCIAL,
                "observacao": "Restos a pagar processado de contrato de manutenção.",
                "criado_por": user_contador,
            },
        )
        apply_updates(
            resto,
            municipio=municipio,
            exercicio_origem=exercicio_anterior,
            empenho=empenho,
            valor_inscrito=Decimal("9000.00"),
            valor_pago=Decimal("3000.00"),
            status=DespRestosPagar.Status.PARCIAL,
        )

        DespPagamentoResto.objects.get_or_create(
            resto=resto,
            ordem_pagamento=f"OPRP-{current_year}-0007",
            defaults={
                "conta_bancaria": conta_bb,
                "data_pagamento": today - timedelta(days=6),
                "valor": Decimal("3000.00"),
                "status": DespPagamentoResto.Status.PAGO,
                "criado_por": user_contador,
            },
        )

        receita_fpm, _ = RecArrecadacao.objects.get_or_create(
            municipio=municipio,
            exercicio=exercicio_atual,
            unidade_gestora=ug_principal,
            data_arrecadacao=today - timedelta(days=4),
            rubrica_codigo="1.7.1.8.01.2.1",
            documento=f"ARREC-{current_year}-1001",
            defaults={
                "conta_bancaria": conta_bb,
                "rubrica_nome": "Cota-parte do FPM",
                "valor": Decimal("182450.32"),
                "origem": "Transferência constitucional",
                "criado_por": user_contador,
            },
        )
        apply_updates(receita_fpm, conta_bancaria=conta_bb, valor=Decimal("182450.32"))

        receita_iss, _ = RecArrecadacao.objects.get_or_create(
            municipio=municipio,
            exercicio=exercicio_atual,
            unidade_gestora=ug_principal,
            data_arrecadacao=today - timedelta(days=2),
            rubrica_codigo="1.1.1.4.51.1.1",
            documento=f"ARREC-{current_year}-1020",
            defaults={
                "conta_bancaria": conta_bb,
                "rubrica_nome": "ISSQN",
                "valor": Decimal("15890.00"),
                "origem": "Arrecadação própria",
                "criado_por": user_contador,
            },
        )
        apply_updates(receita_iss, conta_bancaria=conta_bb, valor=Decimal("15890.00"))

        importacao_extrato, _ = TesExtratoImportacao.objects.get_or_create(
            municipio=municipio,
            exercicio=exercicio_atual,
            conta_bancaria=conta_bb,
            arquivo_nome=f"extrato_bb_{current_year}_{today.month:02d}.csv",
            defaults={
                "formato": TesExtratoImportacao.Formato.CSV,
                "status": TesExtratoImportacao.Status.PROCESSADA,
                "periodo_inicio": today.replace(day=1),
                "periodo_fim": today,
                "total_itens": 2,
                "total_creditos": Decimal("198340.32"),
                "total_debitos": Decimal("43000.00"),
                "criado_por": user_contador,
            },
        )
        apply_updates(importacao_extrato, total_itens=2, total_creditos=Decimal("198340.32"), total_debitos=Decimal("43000.00"))

        extrato_credito, _ = TesExtratoItem.objects.get_or_create(
            importacao=importacao_extrato,
            municipio=municipio,
            conta_bancaria=conta_bb,
            data_movimento=today - timedelta(days=4),
            documento=receita_fpm.documento,
            defaults={
                "historico": "Recebimento cota FPM",
                "identificador_externo": f"EXT-FPM-{current_year}",
                "valor": Decimal("182450.32"),
                "saldo_informado": Decimal("225430.32"),
            },
        )
        extrato_debito, _ = TesExtratoItem.objects.get_or_create(
            importacao=importacao_extrato,
            municipio=municipio,
            conta_bancaria=conta_bb,
            data_movimento=today - timedelta(days=10),
            documento=pagamento.ordem_pagamento,
            defaults={
                "historico": "Pagamento fornecedor saúde",
                "identificador_externo": f"EXT-PAG-{current_year}",
                "valor": Decimal("-43000.00"),
                "saldo_informado": Decimal("43000.00"),
            },
        )

        RecConciliacaoItem.objects.get_or_create(
            municipio=municipio,
            extrato_item=extrato_credito,
            defaults={
                "referencia_tipo": RecConciliacaoItem.ReferenciaTipo.RECEITA,
                "receita": receita_fpm,
                "observacao": "Conciliação automática da arrecadação do FPM.",
                "conciliado_por": user_contador,
            },
        )
        RecConciliacaoItem.objects.get_or_create(
            municipio=municipio,
            extrato_item=extrato_debito,
            defaults={
                "referencia_tipo": RecConciliacaoItem.ReferenciaTipo.PAGAMENTO,
                "desp_pagamento": pagamento,
                "observacao": "Conciliação automática de pagamento liquidado.",
                "conciliado_por": user_contador,
            },
        )

        FinanceiroLogEvento.objects.get_or_create(
            municipio=municipio,
            evento="SEED_DEMO",
            entidade="DespEmpenho",
            entidade_id=str(empenho.id),
            defaults={
                "antes": {},
                "depois": {
                    "numero": empenho.numero,
                    "valor_empenhado": str(empenho.valor_empenhado),
                    "status": empenho.status,
                },
                "observacao": "Registro de seed demonstrativo Bacuri.",
                "usuario": user_contador,
            },
        )

        contrato, _ = ContratoAdministrativo.objects.get_or_create(
            municipio=municipio,
            numero=f"CT-{current_year}-0034",
            defaults={
                "processo_licitatorio": licitacao,
                "requisicao_compra": requisicao,
                "objeto": "Fornecimento de medicamentos e materiais de enfermagem",
                "fornecedor_nome": "Farma Norte Distribuidora LTDA",
                "fornecedor_documento": "12.345.678/0001-90",
                "fiscal_nome": "Lucia Maria Cardoso",
                "valor_total": Decimal("79000.00"),
                "vigencia_inicio": today - timedelta(days=20),
                "vigencia_fim": today + timedelta(days=345),
                "status": ContratoAdministrativo.Status.ATIVO,
                "empenho": empenho,
                "criado_por": user_licitacoes,
            },
        )
        apply_updates(
            contrato,
            processo_licitatorio=licitacao,
            requisicao_compra=requisicao,
            empenho=empenho,
            status=ContratoAdministrativo.Status.ATIVO,
            valor_total=Decimal("79000.00"),
        )

        AditivoContrato.objects.get_or_create(
            contrato=contrato,
            numero=f"ADT-{current_year}-0001",
            defaults={
                "tipo": AditivoContrato.Tipo.VALOR,
                "data_ato": today - timedelta(days=5),
                "valor_aditivo": Decimal("12000.00"),
                "descricao": "Aditivo de quantitativo por aumento da demanda da rede básica.",
            },
        )

        MedicaoContrato.objects.get_or_create(
            contrato=contrato,
            numero=f"MED-{current_year}-0001",
            defaults={
                "competencia": competencia_atual,
                "data_medicao": today - timedelta(days=12),
                "valor_medido": Decimal("43000.00"),
                "observacao": "Medição referente à primeira entrega.",
                "status": MedicaoContrato.Status.LIQUIDADA,
                "atestado_por": user_enfermeira,
                "atestado_em": now - timedelta(days=11),
                "liquidacao": liquidacao,
                "criado_por": user_licitacoes,
            },
        )

        # Recalcula agregados principais da dotacao.
        # Recalcula agregados principais da dotacao.
        dotacao_saude.valor_empenhado = sum(
            (obj.valor_empenhado for obj in DespEmpenho.objects.filter(dotacao=dotacao_saude)),
            Decimal("0.00"),
        )
        dotacao_saude.valor_liquidado = sum(
            (obj.valor_liquidado for obj in DespEmpenho.objects.filter(dotacao=dotacao_saude)),
            Decimal("0.00"),
        )
        dotacao_saude.valor_pago = sum(
            (obj.valor_pago for obj in DespEmpenho.objects.filter(dotacao=dotacao_saude)),
            Decimal("0.00"),
        )
        dotacao_saude.save(update_fields=["valor_empenhado", "valor_liquidado", "valor_pago"])

        # 6) RH, ponto e folha
        servidores_base = [
            (user_municipal, sec_admin, un_admin, set_admin, "Gestora Municipal", "Chefe do Executivo", Decimal("12000.00")),
            (user_rh, sec_admin, un_admin, set_rh, "Analista de RH", "Gestão de Pessoas", Decimal("4300.00")),
            (user_contador, sec_financas, un_financas, set_fin_exec, "Contador", "Contabilidade Pública", Decimal("7800.00")),
            (user_licitacoes, sec_admin, un_admin, set_licitacoes, "Pregoeira", "Licitações", Decimal("5200.00")),
            (user_medico, sec_saude, un_saude_ubs, set_saude_atendimento, "Médico Clínico", "Médico", Decimal("9800.00")),
            (user_enfermeira, sec_saude, un_saude_ubs, set_saude_enfermagem, "Enfermeira", "Enfermagem", Decimal("5400.00")),
            (user_farmaceutica, sec_saude, un_saude_ubs, set_saude_farmacia, "Farmacêutica", "Farmácia", Decimal("5100.00")),
            (user_professor, sec_educacao, un_educacao, set_educacao_coord, "Professora", "Docência", Decimal("4800.00")),
            (user_motorista, sec_transporte, un_transporte, set_transporte_frota, "Motorista", "Condução de Veículos", Decimal("3200.00")),
            (user_ouvidoria, sec_admin, un_admin, set_ouvidoria, "Atendente de Ouvidoria", "Atendimento ao Cidadão", Decimal("3600.00")),
        ]

        rh_cadastros = []
        for idx, (usr, secretaria, unidade, setor, cargo, funcao, salario) in enumerate(servidores_base, start=1):
            cadastro, _ = RhCadastro.objects.get_or_create(
                municipio=municipio,
                codigo=f"RH-BAC-{idx:04d}",
                defaults={
                    "servidor": usr,
                    "secretaria": secretaria,
                    "unidade": unidade,
                    "setor": setor,
                    "matricula": f"MAT{current_year}{idx:04d}",
                    "nome": usr.get_full_name() or usr.username,
                    "cargo": cargo,
                    "funcao": funcao,
                    "regime": RhCadastro.Regime.ESTATUTARIO,
                    "data_admissao": date(previous_year, 2, min(28, idx + 1)),
                    "situacao_funcional": RhCadastro.SituacaoFuncional.ATIVO,
                    "salario_base": salario,
                    "status": RhCadastro.Status.ATIVO,
                    "criado_por": user_rh,
                },
            )
            apply_updates(
                cadastro,
                servidor=usr,
                secretaria=secretaria,
                unidade=unidade,
                setor=setor,
                nome=usr.get_full_name() or usr.username,
                cargo=cargo,
                funcao=funcao,
                salario_base=salario,
                status=RhCadastro.Status.ATIVO,
                situacao_funcional=RhCadastro.SituacaoFuncional.ATIVO,
            )
            rh_cadastros.append(cadastro)

        RhMovimentacao.objects.get_or_create(
            municipio=municipio,
            servidor=rh_cadastros[4],
            tipo=RhMovimentacao.Tipo.PROGRESSAO,
            data_inicio=today - timedelta(days=90),
            defaults={
                "status": RhMovimentacao.Status.APROVADA,
                "secretaria_destino": sec_saude,
                "unidade_destino": un_saude_ubs,
                "setor_destino": set_saude_atendimento,
                "observacao": "Progressão horizontal por desempenho.",
                "aprovado_por": user_municipal,
                "aprovado_em": now - timedelta(days=89),
                "criado_por": user_rh,
            },
        )

        RhDocumento.objects.get_or_create(
            municipio=municipio,
            numero=f"PORT-{current_year}-0123",
            defaults={
                "servidor": rh_cadastros[4],
                "tipo": RhDocumento.Tipo.PORTARIA,
                "data_documento": today - timedelta(days=85),
                "descricao": "Portaria de progressão funcional do servidor.",
                "criado_por": user_rh,
            },
        )

        escala_admin, _ = PontoCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="ESC-ADM-01",
            defaults={
                "secretaria": sec_admin,
                "unidade": un_admin,
                "setor": set_admin,
                "nome": "Escala Administrativa",
                "tipo_turno": PontoCadastro.Turno.INTEGRAL,
                "hora_entrada": time(8, 0),
                "hora_saida": time(14, 0),
                "carga_horaria_semanal": Decimal("30.00"),
                "tolerancia_entrada_min": 10,
                "dias_semana": "SEG,TER,QUA,QUI,SEX",
                "status": PontoCadastro.Status.ATIVO,
                "criado_por": user_rh,
            },
        )
        escala_saude, _ = PontoCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="ESC-SAU-01",
            defaults={
                "secretaria": sec_saude,
                "unidade": un_saude_ubs,
                "setor": set_saude_atendimento,
                "nome": "Escala Atenção Básica",
                "tipo_turno": PontoCadastro.Turno.MATUTINO,
                "hora_entrada": time(7, 0),
                "hora_saida": time(13, 0),
                "carga_horaria_semanal": Decimal("30.00"),
                "tolerancia_entrada_min": 15,
                "dias_semana": "SEG,TER,QUA,QUI,SEX",
                "status": PontoCadastro.Status.ATIVO,
                "criado_por": user_rh,
            },
        )
        apply_updates(escala_admin, status=PontoCadastro.Status.ATIVO)
        apply_updates(escala_saude, status=PontoCadastro.Status.ATIVO)

        vinculos = [
            (user_municipal, escala_admin, un_admin, set_admin),
            (user_rh, escala_admin, un_admin, set_rh),
            (user_licitacoes, escala_admin, un_admin, set_licitacoes),
            (user_ouvidoria, escala_admin, un_admin, set_ouvidoria),
            (user_medico, escala_saude, un_saude_ubs, set_saude_atendimento),
            (user_enfermeira, escala_saude, un_saude_ubs, set_saude_enfermagem),
            (user_farmaceutica, escala_saude, un_saude_ubs, set_saude_farmacia),
        ]
        for usuario, escala, unidade, setor in vinculos:
            PontoVinculoEscala.objects.get_or_create(
                municipio=municipio,
                escala=escala,
                servidor=usuario,
                data_inicio=date(current_year, 1, 2),
                defaults={
                    "unidade": unidade,
                    "setor": setor,
                    "ativo": True,
                    "observacao": "Vínculo inicial de escala no seed demo.",
                    "criado_por": user_rh,
                },
            )

        PontoOcorrencia.objects.get_or_create(
            municipio=municipio,
            servidor=user_medico,
            data_ocorrencia=today - timedelta(days=7),
            competencia=competencia_atual,
            tipo=PontoOcorrencia.Tipo.ATRASO,
            defaults={
                "minutos": 18,
                "descricao": "Atraso por deslocamento intermunicipal.",
                "status": PontoOcorrencia.Status.APROVADA,
                "avaliado_por": user_rh,
                "avaliado_em": now - timedelta(days=6),
                "criado_por": user_medico,
            },
        )
        PontoOcorrencia.objects.get_or_create(
            municipio=municipio,
            servidor=user_enfermeira,
            data_ocorrencia=today - timedelta(days=4),
            competencia=competencia_atual,
            tipo=PontoOcorrencia.Tipo.HORA_EXTRA,
            defaults={
                "minutos": 120,
                "descricao": "Cobertura de plantão estendido na UBS.",
                "status": PontoOcorrencia.Status.PENDENTE,
                "criado_por": user_enfermeira,
            },
        )

        fechamento_ponto, _ = PontoFechamentoCompetencia.objects.get_or_create(
            municipio=municipio,
            competencia=competencia_atual,
            defaults={
                "status": PontoFechamentoCompetencia.Status.ABERTA,
                "total_servidores": len(vinculos),
                "total_ocorrencias": PontoOcorrencia.objects.filter(
                    municipio=municipio,
                    competencia=competencia_atual,
                ).count(),
                "total_pendentes": PontoOcorrencia.objects.filter(
                    municipio=municipio,
                    competencia=competencia_atual,
                    status=PontoOcorrencia.Status.PENDENTE,
                ).count(),
                "observacao": "Fechamento parcial da competência corrente.",
                "criado_por": user_rh,
            },
        )
        apply_updates(
            fechamento_ponto,
            total_servidores=len(vinculos),
            total_ocorrencias=PontoOcorrencia.objects.filter(
                municipio=municipio,
                competencia=competencia_atual,
            ).count(),
            total_pendentes=PontoOcorrencia.objects.filter(
                municipio=municipio,
                competencia=competencia_atual,
                status=PontoOcorrencia.Status.PENDENTE,
            ).count(),
        )

        folha_salario, _ = FolhaCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="RUB-0001",
            defaults={
                "secretaria": sec_admin,
                "unidade": un_admin,
                "setor": set_rh,
                "nome": "Salário base",
                "tipo_evento": FolhaCadastro.TipoEvento.PROVENTO,
                "natureza": FolhaCadastro.Natureza.FIXO,
                "valor_referencia": Decimal("0.00"),
                "status": FolhaCadastro.Status.ATIVO,
                "criado_por": user_rh,
            },
        )
        folha_gratificacao, _ = FolhaCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="RUB-0105",
            defaults={
                "secretaria": sec_admin,
                "unidade": un_admin,
                "setor": set_rh,
                "nome": "Gratificação de desempenho",
                "tipo_evento": FolhaCadastro.TipoEvento.PROVENTO,
                "natureza": FolhaCadastro.Natureza.VARIAVEL,
                "valor_referencia": Decimal("350.00"),
                "status": FolhaCadastro.Status.ATIVO,
                "criado_por": user_rh,
            },
        )
        folha_inss, _ = FolhaCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="RUB-9001",
            defaults={
                "secretaria": sec_admin,
                "unidade": un_admin,
                "setor": set_rh,
                "nome": "INSS",
                "tipo_evento": FolhaCadastro.TipoEvento.DESCONTO,
                "natureza": FolhaCadastro.Natureza.FIXO,
                "valor_referencia": Decimal("0.00"),
                "status": FolhaCadastro.Status.ATIVO,
                "criado_por": user_rh,
            },
        )

        folha_competencia, _ = FolhaCompetencia.objects.get_or_create(
            municipio=municipio,
            competencia=competencia_atual,
            defaults={
                "status": FolhaCompetencia.Status.PROCESSADA,
                "total_colaboradores": len(servidores_base),
                "criado_por": user_rh,
            },
        )
        apply_updates(folha_competencia, status=FolhaCompetencia.Status.PROCESSADA, total_colaboradores=len(servidores_base))

        total_proventos = Decimal("0.00")
        total_descontos = Decimal("0.00")
        for cadastro in rh_cadastros:
            servidor_usuario = cadastro.servidor
            if not servidor_usuario:
                continue
            base = cadastro.salario_base or Decimal("0.00")
            gratificacao = Decimal("350.00")
            desconto_inss = (base * Decimal("0.11")).quantize(Decimal("0.01"))

            l1, _ = FolhaLancamento.objects.get_or_create(
                municipio=municipio,
                competencia=folha_competencia,
                servidor=servidor_usuario,
                evento=folha_salario,
                defaults={
                    "quantidade": Decimal("1.00"),
                    "valor_unitario": base,
                    "valor_calculado": base,
                    "status": FolhaLancamento.Status.VALIDADO,
                    "criado_por": user_rh,
                },
            )
            apply_updates(l1, valor_unitario=base, valor_calculado=base, status=FolhaLancamento.Status.VALIDADO)

            l2, _ = FolhaLancamento.objects.get_or_create(
                municipio=municipio,
                competencia=folha_competencia,
                servidor=servidor_usuario,
                evento=folha_gratificacao,
                defaults={
                    "quantidade": Decimal("1.00"),
                    "valor_unitario": gratificacao,
                    "valor_calculado": gratificacao,
                    "status": FolhaLancamento.Status.VALIDADO,
                    "criado_por": user_rh,
                },
            )
            apply_updates(l2, valor_unitario=gratificacao, valor_calculado=gratificacao, status=FolhaLancamento.Status.VALIDADO)

            l3, _ = FolhaLancamento.objects.get_or_create(
                municipio=municipio,
                competencia=folha_competencia,
                servidor=servidor_usuario,
                evento=folha_inss,
                defaults={
                    "quantidade": Decimal("1.00"),
                    "valor_unitario": desconto_inss,
                    "valor_calculado": desconto_inss,
                    "status": FolhaLancamento.Status.VALIDADO,
                    "criado_por": user_rh,
                },
            )
            apply_updates(l3, valor_unitario=desconto_inss, valor_calculado=desconto_inss, status=FolhaLancamento.Status.VALIDADO)

            total_proventos += base + gratificacao
            total_descontos += desconto_inss

        total_liquido = total_proventos - total_descontos
        apply_updates(
            folha_competencia,
            total_colaboradores=len(servidores_base),
            total_proventos=total_proventos,
            total_descontos=total_descontos,
            total_liquido=total_liquido,
            status=FolhaCompetencia.Status.PROCESSADA,
        )

        FolhaIntegracaoFinanceiro.objects.get_or_create(
            municipio=municipio,
            competencia=folha_competencia,
            defaults={
                "status": FolhaIntegracaoFinanceiro.Status.CONCLUIDA,
                "total_enviado": total_liquido,
                "referencia_financeiro": empenho.numero,
                "observacao": "Integração fictícia de folha com financeiro.",
                "enviado_em": now - timedelta(days=1),
                "enviado_por": user_contador,
            },
        )

        # 7) Almoxarifado
        itens_almox = [
            ("ALM-0001", "Papel A4 75g", "CX", Decimal("15.00"), Decimal("120.00")),
            ("ALM-0002", "Luva de procedimento M", "CX", Decimal("80.00"), Decimal("640.00")),
            ("ALM-0003", "Álcool 70% 1L", "LT", Decimal("30.00"), Decimal("95.00")),
            ("ALM-0004", "Tonner impressora laser", "UN", Decimal("5.00"), Decimal("18.00")),
        ]
        almox_items = []
        for codigo, nome_item, um, estoque_min, saldo in itens_almox:
            item, _ = AlmoxarifadoCadastro.objects.get_or_create(
                municipio=municipio,
                codigo=codigo,
                defaults={
                    "secretaria": sec_admin,
                    "unidade": un_admin,
                    "setor": set_almox,
                    "nome": nome_item,
                    "unidade_medida": um,
                    "estoque_minimo": estoque_min,
                    "saldo_atual": saldo,
                    "valor_medio": Decimal("0.00"),
                    "status": AlmoxarifadoCadastro.Status.ATIVO,
                    "criado_por": user_rh,
                },
            )
            apply_updates(
                item,
                secretaria=sec_admin,
                unidade=un_admin,
                setor=set_almox,
                estoque_minimo=estoque_min,
                saldo_atual=saldo,
                status=AlmoxarifadoCadastro.Status.ATIVO,
            )
            almox_items.append(item)

        movimentos = [
            (almox_items[0], AlmoxarifadoMovimento.Tipo.ENTRADA, Decimal("200.00"), Decimal("31.90"), f"NF-{current_year}-A4"),
            (almox_items[1], AlmoxarifadoMovimento.Tipo.ENTRADA, Decimal("720.00"), Decimal("23.80"), f"NF-{current_year}-LUV"),
            (almox_items[1], AlmoxarifadoMovimento.Tipo.SAIDA, Decimal("80.00"), Decimal("23.80"), f"REQ-{current_year}-SAU"),
            (almox_items[2], AlmoxarifadoMovimento.Tipo.ENTRADA, Decimal("120.00"), Decimal("8.95"), f"NF-{current_year}-ALC"),
            (almox_items[3], AlmoxarifadoMovimento.Tipo.ENTRADA, Decimal("30.00"), Decimal("310.00"), f"NF-{current_year}-TON"),
        ]
        for item, tipo_mov, qtd, valor, documento in movimentos:
            AlmoxarifadoMovimento.objects.get_or_create(
                municipio=municipio,
                item=item,
                tipo=tipo_mov,
                data_movimento=today - timedelta(days=12),
                quantidade=qtd,
                documento=documento,
                defaults={
                    "valor_unitario": valor,
                    "observacao": "Movimento gerado por seed de demonstração.",
                    "criado_por": user_rh,
                },
            )

        AlmoxarifadoRequisicao.objects.get_or_create(
            municipio=municipio,
            numero=f"ALMREQ-{current_year}-0011",
            item=almox_items[1],
            defaults={
                "secretaria_solicitante": sec_saude,
                "unidade_solicitante": un_saude_ubs,
                "setor_solicitante": set_saude_farmacia,
                "quantidade": Decimal("50.00"),
                "justificativa": "Reposição de luvas para atendimento ambulatorial.",
                "status": AlmoxarifadoRequisicao.Status.ATENDIDA,
                "aprovado_por": user_rh,
                "aprovado_em": now - timedelta(days=9),
                "atendido_por": user_rh,
                "atendido_em": now - timedelta(days=8),
                "criado_por": user_farmaceutica,
            },
        )

        # 8) Saude
        especialidade_clinica, _ = EspecialidadeSaude.objects.get_or_create(nome="Clínica Geral", defaults={"cbo": "225125", "ativo": True})
        especialidade_pediatria, _ = EspecialidadeSaude.objects.get_or_create(nome="Pediatria", defaults={"cbo": "225124", "ativo": True})
        especialidade_enfermagem, _ = EspecialidadeSaude.objects.get_or_create(nome="Enfermagem", defaults={"cbo": "223505", "ativo": True})
        apply_updates(especialidade_clinica, ativo=True)
        apply_updates(especialidade_pediatria, ativo=True)
        apply_updates(especialidade_enfermagem, ativo=True)

        sala_consulta_1, _ = SalaSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            nome="Consultório 01",
            defaults={"setor": set_saude_atendimento, "capacidade": 2, "ativo": True},
        )
        sala_procedimento, _ = SalaSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            nome="Sala de Procedimentos",
            defaults={"setor": set_saude_enfermagem, "capacidade": 3, "ativo": True},
        )
        apply_updates(sala_consulta_1, ativo=True)
        apply_updates(sala_procedimento, ativo=True)

        profissional_medico, _ = ProfissionalSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            nome="Dr. Bruno Henrique Azevedo",
            cargo=ProfissionalSaude.Cargo.MEDICO,
            defaults={
                "especialidade": especialidade_clinica,
                "cpf": "35698741000",
                "conselho_numero": "CRM/MA 12345",
                "cbo": "225125",
                "carga_horaria_semanal": 30,
                "telefone": "(98) 99221-0001",
                "email": "bruno.azevedo@bacuri.ma.gov.br",
                "ativo": True,
            },
        )
        profissional_enfermeira, _ = ProfissionalSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            nome="Lucia Maria Cardoso",
            cargo=ProfissionalSaude.Cargo.ENFERMEIRO,
            defaults={
                "especialidade": especialidade_enfermagem,
                "cpf": "74185296300",
                "conselho_numero": "COREN/MA 77881",
                "cbo": "223505",
                "carga_horaria_semanal": 40,
                "telefone": "(98) 99221-0002",
                "email": "lucia.cardoso@bacuri.ma.gov.br",
                "ativo": True,
            },
        )
        profissional_pediatra, _ = ProfissionalSaude.objects.get_or_create(
            unidade=un_saude_hospital,
            nome="Dra. Renata Gonçalves",
            cargo=ProfissionalSaude.Cargo.MEDICO,
            defaults={
                "especialidade": especialidade_pediatria,
                "cpf": "96385274199",
                "conselho_numero": "CRM/MA 99881",
                "cbo": "225124",
                "carga_horaria_semanal": 20,
                "telefone": "(98) 99221-0010",
                "email": "renata.goncalves@bacuri.ma.gov.br",
                "ativo": True,
            },
        )
        apply_updates(profissional_medico, especialidade=especialidade_clinica, ativo=True)
        apply_updates(profissional_enfermeira, especialidade=especialidade_enfermagem, ativo=True)
        apply_updates(profissional_pediatra, especialidade=especialidade_pediatria, ativo=True)

        programa_hiperdia, _ = ProgramaSaude.objects.get_or_create(
            nome="Hiperdia Municipal",
            tipo=ProgramaSaude.Tipo.PROGRAMA,
            defaults={"ativo": True},
        )
        apply_updates(programa_hiperdia, ativo=True)

        paciente_base, _ = PacienteSaude.objects.get_or_create(
            unidade_referencia=un_saude_ubs,
            nome="Rafael Nunes da Silva",
            defaults={
                "aluno": alunos[0],
                "programa": programa_hiperdia,
                "data_nascimento": alunos[0].data_nascimento,
                "sexo": PacienteSaude.Sexo.MASCULINO,
                "cartao_sus": "898001234567890",
                "cpf": "12345678901",
                "telefone": "(98) 98981-1200",
                "email": "rafael.silva@email.local",
                "endereco": "Rua da Paz, 45 - Centro - Bacuri/MA",
                "responsavel_nome": "Mariana Nunes",
                "responsavel_telefone": "(98) 98981-1201",
                "vulnerabilidades": "Acompanhamento nutricional.",
                "ativo": True,
            },
        )
        apply_updates(
            paciente_base,
            aluno=alunos[0],
            programa=programa_hiperdia,
            ativo=True,
            unidade_referencia=un_saude_ubs,
        )

        atendimento_1, _ = AtendimentoSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            profissional=profissional_medico,
            data=today - timedelta(days=3),
            tipo=AtendimentoSaude.Tipo.CONSULTA,
            paciente_nome=paciente_base.nome,
            defaults={
                "aluno": alunos[0],
                "paciente_cpf": "12345678901",
                "observacoes": "Paciente com quadro de gripe e febre moderada.",
                "cid": "J11",
            },
        )
        apply_updates(
            atendimento_1,
            aluno=alunos[0],
            paciente_cpf="12345678901",
            observacoes="Paciente com quadro de gripe e febre moderada.",
            cid="J11",
        )

        agendamento_inicio = dt_at(today + timedelta(days=2), 9, 0)
        agendamento_fim = dt_at(today + timedelta(days=2), 9, 30)
        agendamento_1, _ = AgendamentoSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            profissional=profissional_medico,
            paciente_nome=paciente_base.nome,
            inicio=agendamento_inicio,
            defaults={
                "especialidade": especialidade_clinica,
                "sala": sala_consulta_1,
                "aluno": alunos[0],
                "paciente_cpf": "12345678901",
                "fim": agendamento_fim,
                "tipo": AgendamentoSaude.Tipo.RETORNO,
                "status": AgendamentoSaude.Status.MARCADO,
                "motivo": "Retorno pós-tratamento.",
            },
        )
        apply_updates(
            agendamento_1,
            especialidade=especialidade_clinica,
            sala=sala_consulta_1,
            aluno=alunos[0],
            paciente_cpf="12345678901",
            fim=agendamento_fim,
            status=AgendamentoSaude.Status.MARCADO,
        )

        DocumentoClinicoSaude.objects.get_or_create(
            atendimento=atendimento_1,
            tipo=DocumentoClinicoSaude.Tipo.ATESTADO,
            titulo="Atestado médico de 2 dias",
            defaults={
                "conteudo": "Paciente necessita de afastamento escolar por 2 dias para recuperação.",
                "criado_por": user_medico,
            },
        )

        AuditoriaAcessoProntuarioSaude.objects.get_or_create(
            usuario=user_enfermeira,
            atendimento=atendimento_1,
            aluno=alunos[0],
            acao="VISUALIZACAO",
            defaults={"ip": "127.0.0.1"},
        )

        TriagemSaude.objects.get_or_create(
            atendimento=atendimento_1,
            defaults={
                "pa_sistolica": 110,
                "pa_diastolica": 70,
                "frequencia_cardiaca": 88,
                "temperatura": Decimal("37.8"),
                "saturacao_o2": 98,
                "peso_kg": Decimal("42.30"),
                "altura_cm": Decimal("151.00"),
                "classificacao_risco": "VERDE",
                "observacoes": "Sem sinais de gravidade.",
            },
        )

        EvolucaoClinicaSaude.objects.get_or_create(
            atendimento=atendimento_1,
            tipo=EvolucaoClinicaSaude.Tipo.MEDICO,
            texto="Paciente orientado, prescrição de sintomático e hidratação oral.",
            autor=user_medico,
        )

        Problema_ativo_defaults = {
            "descricao": "Rinite alérgica",
            "cid": "J30.4",
            "status": "ATIVO",
            "observacoes": "Controlado com medicação contínua.",
        }
        # Usa get_or_create direto para manter compatibilidade com versões anteriores do modelo.
        from apps.saude.models import ProblemaAtivoSaude

        ProblemaAtivoSaude.objects.get_or_create(
            aluno=alunos[0],
            descricao=Problema_ativo_defaults["descricao"],
            defaults=Problema_ativo_defaults,
        )

        AlergiaSaude.objects.get_or_create(
            aluno=alunos[0],
            agente="Dipirona",
            defaults={
                "reacao": "Prurido leve",
                "gravidade": AlergiaSaude.Gravidade.LEVE,
                "ativo": True,
            },
        )

        prescricao_1, _ = PrescricaoSaude.objects.get_or_create(
            atendimento=atendimento_1,
            versao=1,
            defaults={
                "status": PrescricaoSaude.Status.ATIVA,
                "observacoes": "Prescrição inicial da consulta.",
                "criado_por": user_medico,
            },
        )
        PrescricaoItemSaude.objects.get_or_create(
            prescricao=prescricao_1,
            medicamento="Paracetamol 500mg",
            defaults={
                "dose": "1 comprimido",
                "via": "Oral",
                "frequencia": "8/8h",
                "duracao": "5 dias",
                "orientacoes": "Não exceder 4g ao dia.",
            },
        )

        exame_1, _ = ExamePedidoSaude.objects.get_or_create(
            atendimento=atendimento_1,
            nome_exame="Hemograma completo",
            defaults={
                "prioridade": ExamePedidoSaude.Prioridade.ROTINA,
                "justificativa": "Avaliação clínica complementar.",
                "hipotese_diagnostica": "Infecção viral",
                "status": ExamePedidoSaude.Status.RESULTADO,
                "criado_por": user_medico,
            },
        )
        ExameResultadoSaude.objects.get_or_create(
            pedido=exame_1,
            defaults={
                "texto_resultado": "Sem alterações relevantes para a faixa etária.",
                "data_resultado": today - timedelta(days=1),
                "criado_por": user_medico,
            },
        )
        ExameColetaSaude.objects.get_or_create(
            pedido=exame_1,
            defaults={
                "status": ExameColetaSaude.Status.RESULTADO_RECEBIDO,
                "data_coleta": dt_at(today - timedelta(days=2), 8, 30),
                "local_coleta": "Laboratório Municipal de Bacuri",
                "encaminhado_para": "Laboratório Central",
                "observacoes": "Fluxo concluído com laudo recebido.",
                "atualizado_por": user_enfermeira,
            },
        )

        GradeAgendaSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            profissional=profissional_medico,
            dia_semana=GradeAgendaSaude.DiaSemana.SEGUNDA,
            inicio=time(8, 0),
            defaults={
                "sala": sala_consulta_1,
                "especialidade": especialidade_clinica,
                "fim": time(12, 0),
                "duracao_minutos": 30,
                "intervalo_minutos": 5,
                "ativo": True,
            },
        )
        BloqueioAgendaSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            profissional=profissional_medico,
            inicio=dt_at(today + timedelta(days=7), 13, 0),
            fim=dt_at(today + timedelta(days=7), 16, 0),
            motivo="Capacitação da equipe APS",
            defaults={"criado_por": user_enfermeira},
        )

        FilaEsperaSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            paciente_nome="Amanda Costa Soares",
            prioridade=FilaEsperaSaude.Prioridade.MEDIA,
            defaults={
                "especialidade": especialidade_pediatria,
                "aluno": alunos[1],
                "paciente_contato": "(98) 98981-8800",
                "status": FilaEsperaSaude.Status.AGUARDANDO,
                "observacoes": "Aguardando vaga para pediatria.",
            },
        )

        AuditoriaAlteracaoSaude.objects.get_or_create(
            entidade="AtendimentoSaude",
            objeto_id=str(atendimento_1.id),
            campo="observacoes",
            valor_novo=atendimento_1.observacoes,
            defaults={
                "valor_anterior": "",
                "justificativa": "Complemento de evolução clínica para auditoria.",
                "alterado_por": user_medico,
            },
        )

        ProcedimentoSaude.objects.get_or_create(
            atendimento=atendimento_1,
            tipo=ProcedimentoSaude.Tipo.AMBULATORIAL,
            descricao="Nebulização",
            defaults={
                "materiais": "Soro fisiológico 0,9%",
                "intercorrencias": "",
                "realizado_em": now - timedelta(days=3, hours=1),
                "criado_por": user_enfermeira,
            },
        )

        VacinacaoSaude.objects.get_or_create(
            atendimento=atendimento_1,
            vacina="Influenza Trivalente",
            defaults={
                "dose": "Dose anual",
                "lote": "IFL-2026-01",
                "fabricante": "Instituto Butantan",
                "unidade_aplicadora": un_saude_ubs,
                "aplicador": profissional_enfermeira,
                "data_aplicacao": today - timedelta(days=3),
                "reacoes": "",
                "criado_por": user_enfermeira,
            },
        )

        EncaminhamentoSaude.objects.get_or_create(
            atendimento=atendimento_1,
            unidade_origem=un_saude_ubs,
            unidade_destino=un_saude_hospital,
            especialidade_destino=especialidade_pediatria,
            prioridade=EncaminhamentoSaude.Prioridade.PRIORITARIO,
            defaults={
                "status": EncaminhamentoSaude.Status.EM_ANALISE,
                "justificativa": "Avaliação pediátrica especializada.",
                "observacoes_regulacao": "Aguardando confirmação da agenda hospitalar.",
                "criado_por": user_medico,
            },
        )

        CidSaude.objects.get_or_create(codigo="J11", defaults={"descricao": "Influenza (gripe), vírus não identificado", "ativo": True})

        checkin_chegada = dt_at(today, 7, 30)
        CheckInSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            paciente_nome=paciente_base.nome,
            chegada_em=checkin_chegada,
            defaults={
                "agendamento": agendamento_1,
                "atendimento": atendimento_1,
                "paciente": paciente_base,
                "motivo_visita": "Retorno clínico",
                "queixa_principal": "Melhora parcial dos sintomas.",
                "classificacao_risco": "VERDE",
                "status": CheckInSaude.Status.FINALIZADO,
                "criado_por": user_enfermeira,
            },
        )

        MedicamentoUsoContinuoSaude.objects.get_or_create(
            paciente=paciente_base,
            medicamento="Loratadina 10mg",
            defaults={
                "dose": "1 comprimido",
                "via": "Oral",
                "frequencia": "1x ao dia",
                "inicio": today - timedelta(days=30),
                "observacoes": "Uso contínuo em períodos de crise alérgica.",
                "ativo": True,
                "criado_por": user_medico,
            },
        )

        DispensacaoSaude.objects.get_or_create(
            unidade=un_saude_ubs,
            paciente=paciente_base,
            medicamento="Paracetamol 500mg",
            quantidade=Decimal("10.00"),
            dispensado_em=dt_at(today - timedelta(days=3), 10, 15),
            defaults={
                "atendimento": atendimento_1,
                "unidade_medida": "comprimidos",
                "lote": "PARA-500-26A",
                "validade": today + timedelta(days=300),
                "orientacoes": "Tomar conforme prescrição médica.",
                "dispensado_por": user_farmaceutica,
            },
        )

        internacao_1, _ = InternacaoSaude.objects.get_or_create(
            unidade=un_saude_hospital,
            paciente=paciente_base,
            data_admissao=dt_at(today - timedelta(days=1), 14, 0),
            defaults={
                "profissional_responsavel": profissional_pediatra,
                "tipo": InternacaoSaude.Tipo.OBSERVACAO,
                "status": InternacaoSaude.Status.ATIVA,
                "leito": "OBS-03",
                "motivo": "Observação clínica por broncoespasmo.",
                "resumo_alta": "",
                "criado_por": user_medico,
            },
        )
        InternacaoRegistroSaude.objects.get_or_create(
            internacao=internacao_1,
            tipo=InternacaoRegistroSaude.Tipo.EVOLUCAO,
            texto="Paciente estável, saturando em ar ambiente, sem febre.",
            defaults={"criado_por": user_medico},
        )

        # 9) Tributos
        contribuinte_pf, _ = TributosCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="CONTRIB-0001",
            defaults={
                "secretaria": sec_financas,
                "unidade": un_financas,
                "setor": set_tributos,
                "nome": "Joana Pereira Costa",
                "documento": "12345678901",
                "tipo_pessoa": TributosCadastro.TipoPessoa.PF,
                "inscricao_municipal": "IM-10001",
                "endereco": "Rua da Matriz, 120, Centro",
                "email": "joana.costa@email.local",
                "telefone": "(98) 98888-1111",
                "status": TributosCadastro.Status.ATIVO,
                "criado_por": user_contador,
            },
        )
        contribuinte_pj, _ = TributosCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="CONTRIB-0002",
            defaults={
                "secretaria": sec_financas,
                "unidade": un_financas,
                "setor": set_tributos,
                "nome": "Mercantil Bacuri LTDA",
                "documento": "22.334.556/0001-70",
                "tipo_pessoa": TributosCadastro.TipoPessoa.PJ,
                "inscricao_municipal": "IM-20044",
                "endereco": "Av. Principal, 1000, Centro",
                "email": "financeiro@mercantilbacuri.com",
                "telefone": "(98) 98888-2222",
                "status": TributosCadastro.Status.ATIVO,
                "criado_por": user_contador,
            },
        )

        TributoLancamento.objects.get_or_create(
            municipio=municipio,
            contribuinte=contribuinte_pf,
            tipo_tributo=TributoLancamento.TipoTributo.IPTU,
            exercicio=current_year,
            referencia="IPTU-LOTE-01",
            defaults={
                "valor_principal": Decimal("480.00"),
                "desconto": Decimal("20.00"),
                "data_vencimento": date(current_year, 6, 30),
                "status": TributoLancamento.Status.PAGO,
                "data_pagamento": today - timedelta(days=20),
                "banco_recebedor": "Banco do Brasil",
                "criado_por": user_contador,
            },
        )
        TributoLancamento.objects.get_or_create(
            municipio=municipio,
            contribuinte=contribuinte_pj,
            tipo_tributo=TributoLancamento.TipoTributo.ISS,
            exercicio=current_year,
            competencia=competencia_atual,
            referencia="ISS-DECL-00089",
            defaults={
                "valor_principal": Decimal("1350.00"),
                "data_vencimento": today + timedelta(days=10),
                "status": TributoLancamento.Status.EMITIDO,
                "criado_por": user_contador,
            },
        )

        # 10) Frota
        veiculo_ambulancia, _ = FrotaCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="FROTA-0001",
            defaults={
                "secretaria": sec_saude,
                "unidade": un_saude_hospital,
                "setor": set_saude_atendimento,
                "placa": "PTS3A21",
                "nome": "Ambulância Sprinter",
                "marca_modelo": "Mercedes Sprinter",
                "ano_fabricacao": current_year - 2,
                "combustivel": FrotaCadastro.Combustivel.DIESEL,
                "quilometragem_atual": 42850,
                "situacao": FrotaCadastro.Situacao.DISPONIVEL,
                "status": FrotaCadastro.Status.ATIVO,
                "criado_por": user_motorista,
            },
        )
        veiculo_caminhao, _ = FrotaCadastro.objects.get_or_create(
            municipio=municipio,
            codigo="FROTA-0002",
            defaults={
                "secretaria": sec_obras,
                "unidade": un_obras,
                "setor": set_obras_exec,
                "placa": "QRS8J55",
                "nome": "Caminhão Basculante",
                "marca_modelo": "VW Constellation",
                "ano_fabricacao": current_year - 4,
                "combustivel": FrotaCadastro.Combustivel.DIESEL,
                "quilometragem_atual": 118420,
                "situacao": FrotaCadastro.Situacao.DISPONIVEL,
                "status": FrotaCadastro.Status.ATIVO,
                "criado_por": user_motorista,
            },
        )
        apply_updates(veiculo_ambulancia, status=FrotaCadastro.Status.ATIVO, situacao=FrotaCadastro.Situacao.DISPONIVEL)
        apply_updates(veiculo_caminhao, status=FrotaCadastro.Status.ATIVO, situacao=FrotaCadastro.Situacao.DISPONIVEL)

        FrotaAbastecimento.objects.get_or_create(
            municipio=municipio,
            veiculo=veiculo_ambulancia,
            data_abastecimento=today - timedelta(days=5),
            defaults={
                "litros": Decimal("68.00"),
                "valor_total": Decimal("421.60"),
                "quilometragem": 42720,
                "posto": "Posto Bacuri Centro",
                "criado_por": user_motorista,
            },
        )
        FrotaAbastecimento.objects.get_or_create(
            municipio=municipio,
            veiculo=veiculo_caminhao,
            data_abastecimento=today - timedelta(days=3),
            defaults={
                "litros": Decimal("140.00"),
                "valor_total": Decimal("868.00"),
                "quilometragem": 118200,
                "posto": "Posto Bacuri BR",
                "criado_por": user_motorista,
            },
        )
        FrotaManutencao.objects.get_or_create(
            municipio=municipio,
            veiculo=veiculo_caminhao,
            tipo=FrotaManutencao.Tipo.PREVENTIVA,
            data_inicio=today - timedelta(days=15),
            defaults={
                "status": FrotaManutencao.Status.CONCLUIDA,
                "data_fim": today - timedelta(days=13),
                "oficina": "Oficina Municipal",
                "descricao": "Troca de óleo e revisão de freios.",
                "valor_total": Decimal("2350.00"),
                "criado_por": user_motorista,
            },
        )
        FrotaViagem.objects.get_or_create(
            municipio=municipio,
            veiculo=veiculo_ambulancia,
            motorista=user_motorista,
            destino="Hospital Regional de Cururupu",
            data_saida=today - timedelta(days=2),
            defaults={
                "finalidade": "Transferência de paciente para exame especializado.",
                "data_retorno": today - timedelta(days=2),
                "km_saida": 42690,
                "km_retorno": 42815,
                "status": FrotaViagem.Status.CONCLUIDA,
                "criado_por": user_motorista,
            },
        )

        # 11) Ouvidoria / e-SIC
        chamado_ouvidoria, _ = OuvidoriaCadastro.objects.get_or_create(
            municipio=municipio,
            protocolo=f"OUV-{current_year}-00045",
            defaults={
                "secretaria": sec_admin,
                "unidade": un_admin,
                "setor": set_ouvidoria,
                "assunto": "Solicitação de melhoria na iluminação pública",
                "tipo": OuvidoriaCadastro.Tipo.RECLAMACAO,
                "prioridade": OuvidoriaCadastro.Prioridade.MEDIA,
                "descricao": "Moradores solicitam reforço de iluminação na Rua do Porto.",
                "solicitante_nome": "Comunidade Rua do Porto",
                "solicitante_email": "moradores.porto@email.local",
                "solicitante_telefone": "(98) 98877-3300",
                "prazo_resposta": today + timedelta(days=12),
                "status": OuvidoriaCadastro.Status.RESPONDIDO,
                "respondido_em": now - timedelta(days=1),
                "respondido_por": user_ouvidoria,
                "criado_por": user_ouvidoria,
            },
        )
        apply_updates(
            chamado_ouvidoria,
            status=OuvidoriaCadastro.Status.RESPONDIDO,
            respondido_por=user_ouvidoria,
            respondido_em=now - timedelta(days=1),
        )

        OuvidoriaTramitacao.objects.get_or_create(
            municipio=municipio,
            chamado=chamado_ouvidoria,
            setor_origem=set_ouvidoria,
            setor_destino=set_obras_exec,
            despacho="Encaminhado à Secretaria de Obras para vistoria da via.",
            defaults={"ciencia": True, "criado_por": user_ouvidoria},
        )
        OuvidoriaResposta.objects.get_or_create(
            municipio=municipio,
            chamado=chamado_ouvidoria,
            resposta=(
                "A Secretaria de Obras executará a substituição de 3 luminárias "
                "na Rua do Porto até o próximo cronograma semanal."
            ),
            defaults={"publico": True, "criado_por": user_ouvidoria},
        )

        # 12) Onboarding: marca passos como concluídos para facilitar demonstração
        for ordem, (modulo, codigo, titulo) in enumerate(
            [
                ("administracao", "config-org", "Estrutura organizacional configurada"),
                ("financeiro", "dotacoes", "Dotações e execução inicial cadastradas"),
                ("saude", "profissionais", "Profissionais e agenda de saúde cadastrados"),
                ("educacao", "turmas", "Turmas e matrículas registradas"),
                ("ouvidoria", "atendimento", "Atendimento ao cidadão operacional"),
            ],
            start=1,
        ):
            step, _ = OnboardingStep.objects.get_or_create(
                municipio=municipio,
                secretaria=None,
                modulo=modulo,
                codigo=codigo,
                defaults={
                    "titulo": titulo,
                    "descricao": "Gerado automaticamente pelo seed de demonstração.",
                    "ordem": ordem,
                    "status": OnboardingStep.Status.CONCLUIDO,
                },
            )
            apply_updates(step, titulo=titulo, ordem=ordem, status=OnboardingStep.Status.CONCLUIDO)

        # 13) Sumario final
        scope_secretaria = Secretaria.objects.filter(municipio=municipio)
        scope_unidade = Unidade.objects.filter(secretaria__municipio=municipio)
        scope_setor = Setor.objects.filter(unidade__secretaria__municipio=municipio)

        resumo = {
            "Secretarias": scope_secretaria.count(),
            "Unidades": scope_unidade.count(),
            "Setores": scope_setor.count(),
            "Usuarios (profiles no municipio)": Profile.objects.filter(municipio=municipio, ativo=True).count(),
            "RH cadastros": RhCadastro.objects.filter(municipio=municipio).count(),
            "Ponto escalas": PontoCadastro.objects.filter(municipio=municipio).count(),
            "Ponto ocorrencias": PontoOcorrencia.objects.filter(municipio=municipio).count(),
            "Folha competencias": FolhaCompetencia.objects.filter(municipio=municipio).count(),
            "Processos administrativos": ProcessoAdministrativo.objects.filter(municipio=municipio).count(),
            "Requisicoes de compra": RequisicaoCompra.objects.filter(municipio=municipio).count(),
            "Licitacoes": ProcessoLicitatorio.objects.filter(municipio=municipio).count(),
            "Contratos": ContratoAdministrativo.objects.filter(municipio=municipio).count(),
            "Dotacoes": OrcDotacao.objects.filter(municipio=municipio).count(),
            "Empenhos": DespEmpenho.objects.filter(municipio=municipio).count(),
            "Pagamentos": DespPagamento.objects.filter(liquidacao__empenho__municipio=municipio).count(),
            "Receitas": RecArrecadacao.objects.filter(municipio=municipio).count(),
            "Itens almoxarifado": AlmoxarifadoCadastro.objects.filter(municipio=municipio).count(),
            "Movimentos almoxarifado": AlmoxarifadoMovimento.objects.filter(municipio=municipio).count(),
            "Pacientes saude": PacienteSaude.objects.filter(unidade_referencia__secretaria__municipio=municipio).count(),
            "Profissionais saude": ProfissionalSaude.objects.filter(unidade__secretaria__municipio=municipio).count(),
            "Atendimentos saude": AtendimentoSaude.objects.filter(unidade__secretaria__municipio=municipio).count(),
            "Contribuintes": TributosCadastro.objects.filter(municipio=municipio).count(),
            "Lancamentos tributarios": TributoLancamento.objects.filter(municipio=municipio).count(),
            "Veiculos frota": FrotaCadastro.objects.filter(municipio=municipio).count(),
            "Chamados ouvidoria": OuvidoriaCadastro.objects.filter(municipio=municipio).count(),
        }

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed concluido com sucesso. Resumo Bacuri:"))
        for chave, valor in resumo.items():
            self.stdout.write(f" - {chave}: {valor}")

        self.stdout.write("")
        self.stdout.write("Usuarios principais criados/atualizados (senha padrao informada no comando):")
        for username in [
            "bacuri.gestor.municipal",
            "bacuri.rh.ana",
            "bacuri.contador.carlos",
            "bacuri.licitacoes.julia",
            "bacuri.medico.bruno",
            "bacuri.enfermeira.lucia",
            "bacuri.farmaceutica.helena",
            "bacuri.professora.maria",
            "bacuri.motorista.joao",
            "bacuri.ouvidoria.paulo",
        ]:
            self.stdout.write(f" - {username}")
