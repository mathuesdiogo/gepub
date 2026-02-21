from __future__ import annotations

import random
import string
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone


def _rand_name(prefix: str, n: int) -> str:
    return f"{prefix} {n:02d}"


def _rand_code(length: int = 8) -> str:
    # Código de acesso (ex: 8 dígitos/letras)
    alphabet = string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def _has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _get_field_names(model) -> set[str]:
    return {f.name for f in model._meta.get_fields()}


def _set_if_hasattr(obj, attr: str, value):
    if hasattr(obj, attr):
        setattr(obj, attr, value)


def _pick_fk_field(model, candidates: list[str]) -> str | None:
    names = _get_field_names(model)
    for c in candidates:
        if c in names:
            return c
    return None


def _bulk_create(model, objs, batch_size=2000):
    if not objs:
        return []
    return model.objects.bulk_create(objs, batch_size=batch_size, ignore_conflicts=False)


class Command(BaseCommand):
    help = "Seed massivo do GEPUB (municípios/secretarias/unidades/setores/turmas/alunos/usuários/NEE)"

    def add_arguments(self, parser):
        parser.add_argument("--municipios", type=int, default=10)
        parser.add_argument("--secretarias", type=int, default=10)
        parser.add_argument("--unidades", type=int, default=10)
        parser.add_argument("--setores", type=int, default=10)
        parser.add_argument("--turmas", type=int, default=10)  # por unidade
        parser.add_argument("--alunos", type=int, default=10)  # por turma
        parser.add_argument("--users-per-role", type=int, default=10)
        parser.add_argument("--necessidades", type=int, default=10)
        parser.add_argument("--code-len", type=int, default=8)
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        municipios_n = opts["municipios"]
        secretarias_n = opts["secretarias"]
        unidades_n = opts["unidades"]
        setores_n = opts["setores"]
        turmas_n = opts["turmas"]
        alunos_n = opts["alunos"]
        users_per_role = opts["users_per_role"]
        necessidades_n = opts["necessidades"]
        code_len = opts["code_len"]

        # Imports tardios (pra não quebrar loading do Django)
        from apps.org.models import Municipio, Secretaria, Unidade, Setor
        from apps.educacao.models import Turma, Aluno, Matricula
        from apps.accounts.models import Profile

        # NEE (opcional)
        TipoNecessidade = None
        try:
            from apps.nee.models import TipoNecessidade as _TipoNec
            TipoNecessidade = _TipoNec
        except Exception:
            TipoNecessidade = None

        User = get_user_model()

        self.stdout.write(self.style.WARNING("SEED GEPUB: iniciando..."))

        # ----------------------------
        # 1) Municípios
        # ----------------------------
        mun_objs = []
        for i in range(1, municipios_n + 1):
            mun = Municipio()
            # campos comuns
            if _has_field(Municipio, "nome"):
                mun.nome = _rand_name("Prefeitura", i)
            if _has_field(Municipio, "ativo"):
                mun.ativo = True
            mun_objs.append(mun)

        if dry:
            self.stdout.write(f"[dry-run] Criaria {len(mun_objs)} municípios")
            return

        municipios = _bulk_create(Municipio, mun_objs, batch_size=500)
        municipios = list(Municipio.objects.all().order_by("id")[:municipios_n])
        self.stdout.write(self.style.SUCCESS(f"Municípios: {len(municipios)}"))

        # ----------------------------
        # 2) Secretarias
        # ----------------------------
        sec_mun_fk = _pick_fk_field(Secretaria, ["municipio", "prefeitura"])
        sec_objs = []
        sec_index = 1
        for m in municipios:
            for j in range(1, secretarias_n + 1):
                s = Secretaria()
                if sec_mun_fk:
                    setattr(s, f"{sec_mun_fk}_id", m.id)
                if _has_field(Secretaria, "nome"):
                    s.nome = _rand_name(f"Secretaria {m.id}", j)
                if _has_field(Secretaria, "ativo"):
                    s.ativo = True
                sec_objs.append(s)
                sec_index += 1

        _bulk_create(Secretaria, sec_objs, batch_size=2000)
        secretarias = list(
            Secretaria.objects.select_related(sec_mun_fk if sec_mun_fk else None).all()
        )
        self.stdout.write(self.style.SUCCESS(f"Secretarias: {len(secretarias)}"))

        # ----------------------------
        # 3) Unidades
        # ----------------------------
        uni_sec_fk = _pick_fk_field(Unidade, ["secretaria"])
        uni_objs = []
        for s in secretarias:
            for k in range(1, unidades_n + 1):
                u = Unidade()
                if uni_sec_fk:
                    setattr(u, f"{uni_sec_fk}_id", s.id)
                if _has_field(Unidade, "nome"):
                    u.nome = _rand_name(f"Unidade {s.id}", k)
                if _has_field(Unidade, "ativo"):
                    u.ativo = True
                uni_objs.append(u)

        _bulk_create(Unidade, uni_objs, batch_size=5000)
        unidades = list(Unidade.objects.all())
        self.stdout.write(self.style.SUCCESS(f"Unidades: {len(unidades)}"))

        # ----------------------------
        # 4) Setores
        # ----------------------------
        set_uni_fk = _pick_fk_field(Setor, ["unidade"])
        set_objs = []
        for u in unidades:
            for t in range(1, setores_n + 1):
                st = Setor()
                if set_uni_fk:
                    setattr(st, f"{set_uni_fk}_id", u.id)
                if _has_field(Setor, "nome"):
                    st.nome = _rand_name(f"Setor {u.id}", t)
                if _has_field(Setor, "ativo"):
                    st.ativo = True
                set_objs.append(st)

        _bulk_create(Setor, set_objs, batch_size=10000)
        setores = list(Setor.objects.all())
        self.stdout.write(self.style.SUCCESS(f"Setores: {len(setores)}"))

        # ----------------------------
        # 5) Turmas (por unidade)
        # ----------------------------
        tur_objs = []
        ano = timezone.localdate().year
        turnos = ["MANHA", "TARDE", "NOITE", "INTEGRAL"]
        for u in unidades:
            for i in range(1, turmas_n + 1):
                tr = Turma()
                tr.unidade_id = u.id
                tr.nome = f"Turma {i:02d}"
                tr.ano_letivo = ano
                tr.turno = random.choice(turnos)
                tr.ativo = True
                tur_objs.append(tr)

        _bulk_create(Turma, tur_objs, batch_size=5000)
        turmas = list(Turma.objects.select_related("unidade").all())
        self.stdout.write(self.style.SUCCESS(f"Turmas: {len(turmas)}"))

        # ----------------------------
        # 6) Alunos + Matrículas (por turma)
        # ----------------------------
        alunos_objs = []
        matriculas_objs = []
        base_birth = date(2010, 1, 1)
        for tr in turmas:
            for i in range(1, alunos_n + 1):
                a = Aluno()
                a.nome = f"Aluno {tr.id}-{i:02d}"
                a.data_nascimento = base_birth + timedelta(days=random.randint(0, 5000))
                a.cpf = ""  # opcional
                a.nis = ""
                a.nome_mae = f"Mãe {tr.id}-{i:02d}"
                a.nome_pai = f"Pai {tr.id}-{i:02d}"
                a.telefone = ""
                a.email = ""
                a.endereco = ""
                a.ativo = True
                alunos_objs.append(a)

        # primeiro cria alunos
        created_alunos = _bulk_create(Aluno, alunos_objs, batch_size=10000)
        # pega IDs reais (bulk_create já retorna com PK no SQLite/Django 5 normalmente,
        # mas pra garantir, buscamos por prefixo)
        # Vamos mapear por nome:
        alunos_qs = Aluno.objects.filter(nome__startswith="Aluno ").values_list("id", "nome")
        aluno_id_by_nome = {n: i for i, n in alunos_qs}

        for tr in turmas:
            for i in range(1, alunos_n + 1):
                nome = f"Aluno {tr.id}-{i:02d}"
                aluno_id = aluno_id_by_nome.get(nome)
                if not aluno_id:
                    continue
                m = Matricula()
                m.aluno_id = aluno_id
                m.turma_id = tr.id
                m.data_matricula = timezone.localdate()
                m.situacao = Matricula.Situacao.ATIVA
                m.observacao = ""
                matriculas_objs.append(m)

        _bulk_create(Matricula, matriculas_objs, batch_size=20000)
        self.stdout.write(self.style.SUCCESS(f"Alunos: {Aluno.objects.count()} | Matrículas: {Matricula.objects.count()}"))

        # ----------------------------
        # 7) Tipos de Necessidade (NEE)
        # ----------------------------
        if TipoNecessidade:
            tipo_objs = []
            for i in range(1, necessidades_n + 1):
                tn = TipoNecessidade()
                # campos comuns
                if _has_field(TipoNecessidade, "nome"):
                    tn.nome = f"Tipo Necessidade {i:02d}"
                if _has_field(TipoNecessidade, "descricao"):
                    tn.descricao = f"Descrição {i:02d}"
                if _has_field(TipoNecessidade, "ativo"):
                    tn.ativo = True
                tipo_objs.append(tn)
            _bulk_create(TipoNecessidade, tipo_objs, batch_size=200)
            self.stdout.write(self.style.SUCCESS(f"Tipos de Necessidade: {TipoNecessidade.objects.count()}"))
        else:
            self.stdout.write(self.style.WARNING("NEE: TipoNecessidade não encontrado (ok)."))

        # ----------------------------
        # 8) Usuários + Profiles (10 por papel, exceto ADMIN)
        # ----------------------------
        # papéis conhecidos do seu RBAC
        roles = ["MUNICIPAL", "SECRETARIA", "UNIDADE", "PROFESSOR", "ALUNO", "LEITURA", "VISUALIZACAO", "NEE"]

        # Detecta campos do Profile para escopo
        profile_fields = _get_field_names(Profile)
        prof_has_mun = "municipio" in profile_fields
        prof_has_sec = "secretaria" in profile_fields
        prof_has_uni = "unidade" in profile_fields
        prof_has_codigo = any(n in profile_fields for n in ["codigo", "codigo_acesso", "codigo_login", "access_code"])

        # campo de código no Profile (se existir)
        profile_code_field = None
        for cand in ["codigo_acesso", "codigo", "codigo_login", "access_code"]:
            if cand in profile_fields:
                profile_code_field = cand
                break

        # campo de código no User (se existir)
        user_fields = _get_field_names(User)
        user_code_field = None
        for cand in ["codigo_acesso", "codigo", "access_code"]:
            if cand in user_fields:
                user_code_field = cand
                break

        created_users = 0
        for role in roles:
            for i in range(1, users_per_role + 1):
                code = _rand_code(code_len)
                username = f"{role.lower()}_{i:02d}_{code}"

                u = User.objects.create_user(
                    username=username,
                    password="12345678",  # dev only
                )
                _set_if_hasattr(u, "first_name", role.title())
                _set_if_hasattr(u, "last_name", f"Teste {i:02d}")
                _set_if_hasattr(u, "email", f"{username}@teste.local")

                if user_code_field:
                    setattr(u, user_code_field, code)
                    u.save(update_fields=[user_code_field])

                # Profile
                p = getattr(u, "profile", None)
                if not p:
                    # se o Profile não for criado automaticamente, cria aqui
                    p = Profile(user=u)

                if "role" in profile_fields:
                    p.role = role
                if "ativo" in profile_fields:
                    p.ativo = True

                # código de acesso no Profile
                if profile_code_field:
                    setattr(p, profile_code_field, code)

                # escopo por role
                if role == "MUNICIPAL" and prof_has_mun:
                    m = random.choice(municipios)
                    p.municipio_id = m.id

                if role == "SECRETARIA":
                    if prof_has_sec:
                        s = random.choice(secretarias)
                        p.secretaria_id = s.id
                    elif prof_has_mun:
                        m = random.choice(municipios)
                        p.municipio_id = m.id

                if role == "UNIDADE":
                    if prof_has_uni:
                        u0 = random.choice(unidades)
                        p.unidade_id = u0.id
                    elif prof_has_mun:
                        m = random.choice(municipios)
                        p.municipio_id = m.id

                if role == "PROFESSOR":
                    # opcional: vincular turmas depois (ManyToMany), se existir
                    if prof_has_uni:
                        u0 = random.choice(unidades)
                        p.unidade_id = u0.id
                    elif prof_has_mun:
                        m = random.choice(municipios)
                        p.municipio_id = m.id

                if role == "ALUNO":
                    # para ALUNO, normalmente não precisa de escopo, pois o portal é travado.
                    pass

                if role in {"LEITURA", "VISUALIZACAO", "NEE"}:
                    if prof_has_mun:
                        m = random.choice(municipios)
                        p.municipio_id = m.id

                p.save()
                created_users += 1

        self.stdout.write(self.style.SUCCESS(f"Usuários criados: {created_users} (senha dev: 12345678)"))

        # ----------------------------
        # 9) (Opcional) Vincular Professores a turmas (ManyToMany)
        # ----------------------------
        # Se quiser, vincula aleatoriamente cada professor a 2 turmas do seu escopo
        try:
            from apps.accounts.models import Profile as _Profile
            profs = User.objects.filter(profile__role="PROFESSOR").select_related("profile")
            for u in profs:
                qs = Turma.objects.all()
                # tenta escopo por unidade/município do profile
                pr = u.profile
                if getattr(pr, "unidade_id", None):
                    qs = qs.filter(unidade_id=pr.unidade_id)
                elif getattr(pr, "municipio_id", None):
                    qs = qs.filter(unidade__secretaria__municipio_id=pr.municipio_id)

                picked = list(qs.order_by("?")[:2])
                for t in picked:
                    t.professores.add(u)
            self.stdout.write(self.style.SUCCESS("Professores vinculados a turmas (2 cada, aleatório)."))
        except Exception:
            self.stdout.write(self.style.WARNING("Vínculo professor⇄turma não aplicado (ok)."))

        self.stdout.write(self.style.SUCCESS("SEED GEPUB: concluído ✅"))
