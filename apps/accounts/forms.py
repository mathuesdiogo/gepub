from __future__ import annotations
from apps.educacao.models import Aluno, Turma
from apps.core.rbac import (
    allowed_roles_for_manager_role,
    is_admin,
    role_scope_base,
    scope_filter_alunos,
    scope_filter_turmas,
    scope_filter_unidades,
)
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.org.models import Municipio, Secretaria, Unidade, Setor, LocalEstrutural
from apps.saude.models import PacienteSaude
from .models import Profile
from django.contrib.auth.password_validation import validate_password
User = get_user_model()


class LoginCodigoForm(forms.Form):
    codigo_acesso = forms.CharField(label="Código de acesso", max_length=60)
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)


class AlterarSenhaPrimeiroAcessoForm(forms.Form):
    password1 = forms.CharField(
        label="Nova senha",
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Nova senha"}),
    )
    password2 = forms.CharField(
        label="Confirmar nova senha",
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Confirmar nova senha"}),
    )


class UsuarioPrefeituraOnboardingForm(forms.Form):
    nome_responsavel = forms.CharField(label="Nome do responsável", max_length=160)
    email = forms.EmailField(label="E-mail", required=False)
    codigo_acesso = forms.CharField(
        label="Código de acesso (opcional)",
        max_length=60,
        required=False,
        help_text="Se vazio, o sistema gera automaticamente no padrão PRIMEIRONOME.ANO (ex.: MARIA.2026).",
    )
    senha_inicial = forms.CharField(
        label="Senha inicial (opcional)",
        max_length=64,
        required=False,
        help_text="Se vazio, o sistema gera automaticamente.",
    )

    def clean_codigo_acesso(self):
        value = (self.cleaned_data.get("codigo_acesso") or "").strip().upper()
        if not value:
            return ""
        if not all(ch.isalnum() or ch in {".", "-", "_"} for ch in value):
            raise ValidationError("Use apenas letras, números, ponto, hífen ou sublinhado.")
        if len(value) < 4:
            raise ValidationError("Código de acesso deve ter ao menos 4 caracteres.")
        return value



class _UsuarioBaseForm(forms.Form):
    first_name = forms.CharField(label="Nome", max_length=80)
    last_name = forms.CharField(label="Sobrenome", max_length=80, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    role = forms.ChoiceField(label="Função", choices=Profile.Role.choices)
    municipio = forms.ModelChoiceField(label="Município", queryset=Municipio.objects.none(), required=False)
    secretaria = forms.ModelChoiceField(label="Secretaria", queryset=Secretaria.objects.none(), required=False)
    unidade = forms.ModelChoiceField(label="Unidade", queryset=Unidade.objects.none(), required=False)
    setor = forms.ModelChoiceField(label="Setor", queryset=Setor.objects.none(), required=False)
    local_estrutural = forms.ModelChoiceField(
        label="Local estrutural",
        queryset=LocalEstrutural.objects.none(),
        required=False,
    )
    turmas = forms.ModelMultipleChoiceField(
        label="Turmas (somente para perfis docentes)",
        queryset=Turma.objects.none(),
        required=False,
    )
    aluno = forms.ModelChoiceField(
        label="Aluno vinculado",
        queryset=Aluno.objects.none(),
        required=False,
    )
    paciente = forms.ModelChoiceField(
        label="Paciente vinculado",
        queryset=PacienteSaude.objects.none(),
        required=False,
    )
    ativo = forms.BooleanField(label="Ativo", required=False, initial=True)

    def __init__(self, *args, user=None, edited_user=None, **kwargs):
        kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        self.user = user
        self.edited_user = edited_user

        self.fields["municipio"].queryset = Municipio.objects.filter(ativo=True).order_by("nome")
        self.fields["secretaria"].queryset = (
            Secretaria.objects.select_related("municipio")
            .filter(ativo=True)
            .order_by("nome")
        )
        self.fields["unidade"].queryset = (
            Unidade.objects.select_related("secretaria", "secretaria__municipio")
            .filter(ativo=True)
            .order_by("nome")
        )
        self.fields["setor"].queryset = (
            Setor.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")
            .filter(ativo=True)
            .order_by("nome")
        )
        self.fields["local_estrutural"].queryset = (
            LocalEstrutural.objects.select_related("unidade", "secretaria", "municipio")
            .filter(status=LocalEstrutural.Status.ATIVO)
            .order_by("nome")
        )

        turmas_qs = Turma.objects.select_related("unidade").all().order_by("-ano_letivo", "nome")
        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            turmas_qs = scope_filter_turmas(user, turmas_qs)
        self.fields["turmas"].queryset = turmas_qs

        alunos_qs = Aluno.objects.filter(ativo=True).order_by("nome")
        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            alunos_qs = scope_filter_alunos(user, alunos_qs)
        self.fields["aluno"].queryset = alunos_qs

        pacientes_qs = (
            PacienteSaude.objects.select_related("unidade_referencia", "unidade_referencia__secretaria", "aluno")
            .filter(ativo=True)
            .order_by("nome")
        )
        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            unidades_saude_qs = scope_filter_unidades(
                user,
                Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE, ativo=True),
            )
            pacientes_qs = pacientes_qs.filter(
                unidade_referencia_id__in=unidades_saude_qs.values_list("id", flat=True)
            )
        self.fields["paciente"].queryset = pacientes_qs

        if edited_user and hasattr(edited_user, "turmas_ministradas"):
            self.fields["turmas"].initial = list(edited_user.turmas_ministradas.values_list("pk", flat=True))

        self._apply_role_choices()
        self._apply_scope_lock()
        self._apply_chained_filters()

    def _selected_value(self, field_name: str):
        if self.data:
            val = (self.data.get(field_name) or "").strip()
            return val or None
        initial = self.initial.get(field_name)
        if hasattr(initial, "pk"):
            return str(initial.pk)
        return str(initial) if initial else None

    def _apply_role_choices(self):
        user = self.user
        if not user or not getattr(user, "is_authenticated", False):
            return
        p = getattr(user, "profile", None)
        if not p:
            return
        role_me = (p.role or "").upper()
        if role_me == "ADMIN":
            return
        allowed = allowed_roles_for_manager_role(role_me)
        self.fields["role"].choices = [
            (value, label)
            for (value, label) in Profile.Role.choices
            if value in allowed
        ]

    def _apply_scope_lock(self):
        user = self.user
        if not user or not getattr(user, "is_authenticated", False) or is_admin(user):
            return
        p = getattr(user, "profile", None)
        if not p:
            return

        if getattr(p, "municipio_id", None):
            self.fields["municipio"].queryset = Municipio.objects.filter(id=p.municipio_id)
            self.fields["municipio"].initial = p.municipio_id
            self.fields["municipio"].disabled = True

        if getattr(p, "secretaria_id", None):
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(id=p.secretaria_id)
            self.fields["secretaria"].initial = p.secretaria_id
            self.fields["secretaria"].disabled = True

        if getattr(p, "unidade_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id
            self.fields["unidade"].disabled = True

        if getattr(p, "setor_id", None):
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(id=p.setor_id)
            self.fields["setor"].initial = p.setor_id
            self.fields["setor"].disabled = True

        if getattr(p, "local_estrutural_id", None):
            self.fields["local_estrutural"].queryset = self.fields["local_estrutural"].queryset.filter(
                id=p.local_estrutural_id
            )
            self.fields["local_estrutural"].initial = p.local_estrutural_id
            self.fields["local_estrutural"].disabled = True

    def _apply_chained_filters(self):
        selected_municipio = self._selected_value("municipio")
        selected_secretaria = self._selected_value("secretaria")
        selected_unidade = self._selected_value("unidade")

        if selected_municipio and selected_municipio.isdigit():
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(
                municipio_id=int(selected_municipio)
            )
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
                secretaria__municipio_id=int(selected_municipio)
            )
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(
                unidade__secretaria__municipio_id=int(selected_municipio)
            )
            self.fields["local_estrutural"].queryset = self.fields["local_estrutural"].queryset.filter(
                municipio_id=int(selected_municipio)
            )

        if selected_secretaria and selected_secretaria.isdigit():
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
                secretaria_id=int(selected_secretaria)
            )
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(
                unidade__secretaria_id=int(selected_secretaria)
            )
            self.fields["local_estrutural"].queryset = self.fields["local_estrutural"].queryset.filter(
                secretaria_id=int(selected_secretaria)
            )

        if selected_unidade and selected_unidade.isdigit():
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(
                unidade_id=int(selected_unidade)
            )
            self.fields["local_estrutural"].queryset = self.fields["local_estrutural"].queryset.filter(
                unidade_id=int(selected_unidade)
            )

    def clean(self):
        cleaned = super().clean()
        municipio = cleaned.get("municipio")
        secretaria = cleaned.get("secretaria")
        unidade = cleaned.get("unidade")
        setor = cleaned.get("setor")
        local_estrutural = cleaned.get("local_estrutural")
        aluno = cleaned.get("aluno")
        paciente = cleaned.get("paciente")
        role = ((cleaned.get("role") or "") + "").strip().upper()

        if secretaria and municipio and secretaria.municipio_id != municipio.id:
            self.add_error("secretaria", "A secretaria não pertence ao município selecionado.")

        if unidade and secretaria and unidade.secretaria_id != secretaria.id:
            self.add_error("unidade", "A unidade não pertence à secretaria selecionada.")

        if unidade and municipio and unidade.secretaria and unidade.secretaria.municipio_id != municipio.id:
            self.add_error("unidade", "A unidade não pertence ao município selecionado.")

        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor", "O setor não pertence à unidade selecionada.")
        elif setor and secretaria and setor.unidade and setor.unidade.secretaria_id != secretaria.id:
            self.add_error("setor", "O setor não pertence à secretaria selecionada.")
        elif setor and municipio and setor.unidade and setor.unidade.secretaria and setor.unidade.secretaria.municipio_id != municipio.id:
            self.add_error("setor", "O setor não pertence ao município selecionado.")

        if local_estrutural and unidade and local_estrutural.unidade_id != unidade.id:
            self.add_error("local_estrutural", "O local estrutural não pertence à unidade selecionada.")
        elif local_estrutural and secretaria and local_estrutural.secretaria_id != secretaria.id:
            self.add_error("local_estrutural", "O local estrutural não pertence à secretaria selecionada.")
        elif local_estrutural and municipio and local_estrutural.municipio_id != municipio.id:
            self.add_error("local_estrutural", "O local estrutural não pertence ao município selecionado.")

        if paciente and unidade and paciente.unidade_referencia_id != unidade.id:
            self.add_error("paciente", "O paciente não pertence à unidade selecionada.")
        elif paciente and secretaria and paciente.unidade_referencia and paciente.unidade_referencia.secretaria_id != secretaria.id:
            self.add_error("paciente", "O paciente não pertence à secretaria selecionada.")
        elif (
            paciente
            and municipio
            and paciente.unidade_referencia
            and paciente.unidade_referencia.secretaria
            and paciente.unidade_referencia.secretaria.municipio_id != municipio.id
        ):
            self.add_error("paciente", "O paciente não pertence ao município selecionado.")

        role_base = role_scope_base(role)
        if role_base == "MUNICIPAL":
            if not municipio:
                self.add_error("municipio", "Campo obrigatório para perfil municipal.")
        elif role_base == "SECRETARIA":
            if not municipio:
                self.add_error("municipio", "Campo obrigatório para perfil de secretaria.")
            if not secretaria:
                self.add_error("secretaria", "Campo obrigatório para perfil de secretaria.")
        elif role_base in {"UNIDADE", "PROFESSOR"}:
            if not municipio:
                self.add_error("municipio", "Campo obrigatório para perfil de unidade.")
            if not secretaria:
                self.add_error("secretaria", "Campo obrigatório para perfil de unidade.")
            if not unidade:
                self.add_error("unidade", "Campo obrigatório para perfil de unidade.")

        if role == Profile.Role.ALUNO:
            if not aluno:
                self.add_error("aluno", "Selecione o aluno vinculado para o perfil Aluno.")
            cleaned["paciente"] = None
        elif role == Profile.Role.CIDADAO:
            if not paciente and not aluno:
                self.add_error("paciente", "Selecione o paciente vinculado para o perfil Cidadão.")
            if paciente and paciente.aluno_id and not aluno:
                cleaned["aluno"] = paciente.aluno
                aluno = cleaned["aluno"]
            if paciente and aluno and paciente.aluno_id and paciente.aluno_id != aluno.id:
                self.add_error("aluno", "O aluno não corresponde ao paciente informado.")
        else:
            cleaned["aluno"] = None
            cleaned["paciente"] = None

        return cleaned

    def clean_cpf(self):
        cpf = (self.cleaned_data.get("cpf") or "").strip()
        if not cpf:
            return cpf
        digits = "".join(ch for ch in cpf if ch.isdigit())
        if len(digits) != 11:
            raise ValidationError("CPF inválido. Deve conter 11 dígitos.")
        return cpf


class UsuarioCreateForm(_UsuarioBaseForm):
    cpf = forms.CharField(label="CPF", max_length=14)


class UsuarioUpdateForm(_UsuarioBaseForm):
    cpf = forms.CharField(label="CPF", max_length=14, required=False)



class AlterarSenhaForm(forms.Form):
    old_password = forms.CharField(
        label="Senha atual",
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Senha atual"}),
    )
    new_password1 = forms.CharField(
        label="Nova senha",
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Nova senha"}),
    )
    new_password2 = forms.CharField(
        label="Confirmar nova senha",
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Confirmar nova senha"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_password(self):
        old = self.cleaned_data.get("old_password") or ""
        if not self.user or not self.user.check_password(old):
            raise ValidationError("Senha atual incorreta.")
        return old

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1") or ""
        p2 = cleaned.get("new_password2") or ""

        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", "As senhas não conferem.")

        # valida força da senha (usa VALIDATORS do settings)
        if p1:
            validate_password(p1, self.user)

        return cleaned
