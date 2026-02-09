from __future__ import annotations

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from org.models import Municipio, Secretaria, Unidade


class Command(BaseCommand):
    help = "Cria dados de teste (2 municípios, secretarias, unidades e usuários com roles) para validar RBAC."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Apaga dados (usuários não-superuser, organização e educação/nee se existirem) antes de criar.",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="123456",
            help="Senha padrão para os usuários criados (default: 123456).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        flush = options["flush"]
        password = options["password"]

        User = get_user_model()

        if flush:
            self.stdout.write(self.style.WARNING("Limpando dados..."))

            # EDUCAÇÃO (se existir)
            try:
                from educacao.models import Matricula, Turma, Aluno
                Matricula.objects.all().delete()
                Turma.objects.all().delete()
                Aluno.objects.all().delete()
            except Exception:
                pass

            # NEE (se existir)
            try:
                from nee.models import Atendimento, Avaliacao, Encaminhamento
                Atendimento.objects.all().delete()
                Avaliacao.objects.all().delete()
                Encaminhamento.objects.all().delete()
            except Exception:
                pass

            # ORG
            Unidade.objects.all().delete()
            Secretaria.objects.all().delete()
            Municipio.objects.all().delete()

            # USERS (mantém superuser)
            User.objects.exclude(is_superuser=True).delete()

        self.stdout.write(self.style.SUCCESS("Criando municípios..."))

        m1 = Municipio.objects.create(
            nome="Governador Nunes Freire",
            uf="MA",
            cnpj_prefeitura="00.000.000/0001-00",
            razao_social_prefeitura="Prefeitura Municipal de Governador Nunes Freire",
            nome_fantasia_prefeitura="Prefeitura de Governador Nunes Freire",
            endereco_prefeitura="Centro, Governador Nunes Freire - MA",
            telefone_prefeitura="(98) 99999-0000",
            email_prefeitura="contato@gnf.ma.gov.br",
            site_prefeitura="https://gnf.ma.gov.br",
            nome_prefeito="Prefeito(a) Teste",
            ativo=True,
        )

        m2 = Municipio.objects.create(
            nome="Município Teste 2",
            uf="MA",
            cnpj_prefeitura="11.111.111/0001-11",
            razao_social_prefeitura="Prefeitura Municipal do Município Teste 2",
            nome_fantasia_prefeitura="Prefeitura do Município Teste 2",
            endereco_prefeitura="Centro, Município Teste 2 - MA",
            telefone_prefeitura="(98) 99999-1111",
            email_prefeitura="contato@teste2.ma.gov.br",
            site_prefeitura="https://teste2.ma.gov.br",
            nome_prefeito="Prefeito(a) Teste 2",
            ativo=True,
        )

        self.stdout.write(self.style.SUCCESS("Criando secretarias/unidades..."))

        def mk_secretaria(mun: Municipio, nome: str, sigla: str):
            # Ajuste aqui se seu model de Secretaria não tiver "sigla"
            kwargs = {"municipio": mun, "nome": nome}
            try:
                obj = Secretaria.objects.create(**kwargs, sigla=sigla)  # type: ignore
            except TypeError:
                obj = Secretaria.objects.create(**kwargs)
            return obj

        def mk_unidade(sec: Secretaria, nome: str):
            # Ajuste aqui se sua Unidade tiver campos obrigatórios extras
            return Unidade.objects.create(secretaria=sec, nome=nome)

        s1a = mk_secretaria(m1, "Secretaria de Educação", "SEMED")
        s1b = mk_secretaria(m1, "Secretaria de Saúde", "SEMUS")
        u1a = mk_unidade(s1a, "Escola Municipal 1")
        u1b = mk_unidade(s1a, "Escola Municipal 2")

        s2a = mk_secretaria(m2, "Secretaria de Educação", "SEMED")
        u2a = mk_unidade(s2a, "Escola Teste 2 - A")

        self.stdout.write(self.style.SUCCESS("Criando usuários..."))

        def create_user(username: str, role: str, *, municipio=None, secretaria=None, unidade=None):
            u = User.objects.create_user(username=username, password=password)
            # Profile automático (se você usa signals). Se não existir, vai dar erro aqui — aí me avisa.
            p = u.profile
            p.role = role

            # Setar escopo se os campos existirem no Profile
            if hasattr(p, "municipio"):
                p.municipio = municipio
            if hasattr(p, "secretaria"):
                p.secretaria = secretaria
            if hasattr(p, "unidade"):
                p.unidade = unidade

            p.save()
            return u

        created = []

        # Município 1
        created.append(create_user("mun1_municipal", "MUNICIPAL", municipio=m1))
        created.append(create_user("mun1_leitura", "LEITURA", municipio=m1))
        created.append(create_user("mun1_nee", "NEE", municipio=m1))
        created.append(create_user("mun1_sec_semad", "SECRETARIA", municipio=m1, secretaria=s1a))
        created.append(create_user("mun1_unid_1", "UNIDADE", municipio=m1, secretaria=s1a, unidade=u1a))
        created.append(create_user("mun1_prof_1", "PROFESSOR", municipio=m1, unidade=u1a))
        created.append(create_user("mun1_aluno_1", "ALUNO", municipio=m1, unidade=u1a))

        # Município 2
        created.append(create_user("mun2_municipal", "MUNICIPAL", municipio=m2))
        created.append(create_user("mun2_leitura", "LEITURA", municipio=m2))
        created.append(create_user("mun2_sec_edu", "SECRETARIA", municipio=m2, secretaria=s2a))
        created.append(create_user("mun2_unid_a", "UNIDADE", municipio=m2, secretaria=s2a, unidade=u2a))

        self.stdout.write(self.style.SUCCESS("\n✅ Seed concluído! Dados de login:"))
        self.stdout.write(self.style.WARNING(f"Senha padrão: {password}\n"))

        for u in created:
            p = u.profile
            codigo = getattr(p, "codigo_acesso", None)
            self.stdout.write(
                f"- {u.username:16} | role={p.role:10} | codigo_acesso={codigo}"
            )

        self.stdout.write(self.style.SUCCESS("\nUse o codigo_acesso + senha para entrar no login.\n"))
