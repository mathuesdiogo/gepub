from __future__ import annotations
from educacao.models import Turma
from core.rbac import is_admin, scope_filter_turmas

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from educacao.models import Turma
from core.rbac import is_admin, scope_filter_turmas
from org.models import Municipio, Unidade
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



class UsuarioCreateForm(forms.Form):
    first_name = forms.CharField(label="Nome", max_length=80)
    last_name = forms.CharField(label="Sobrenome", max_length=80, required=False)
    email = forms.EmailField(label="E-mail", required=False)

    cpf = forms.CharField(label="CPF (senha inicial)", max_length=14)
    role = forms.ChoiceField(label="Função", choices=Profile.Role.choices)

    municipio = forms.ModelChoiceField(
        label="Município",
        queryset=Municipio.objects.filter(ativo=True).order_by("nome"),
        required=False,
    )
    unidade = forms.ModelChoiceField(
        label="Unidade",
        queryset=Unidade.objects.filter(ativo=True).order_by("nome"),
        required=False,
    )
    turmas = forms.ModelMultipleChoiceField(
    label="Turmas (somente para Professor)",
    queryset=Turma.objects.none(),
    required=False,
    )
    ativo = forms.BooleanField(label="Ativo", required=False, initial=True)

    def __init__(self, *args, user=None, **kwargs):
        instance = kwargs.get("instance")  # <-- PEGA o usuário sendo editado
        super().__init__(*args, **kwargs)
        self.user = user

        # ========= TURMAS (somente Professor) =========
        if "turmas" in self.fields and instance:
            # popula o campo com as turmas já vinculadas ao professor
            self.fields["turmas"].initial = instance.turmas_ministradas.all()



        if not user or not getattr(user, "is_authenticated", False):
            return
        qs_turmas = Turma.objects.select_related("unidade").all().order_by("-ano_letivo", "nome")
        if user and not is_admin(user):
            qs_turmas = scope_filter_turmas(user, qs_turmas)
        self.fields["turmas"].queryset = qs_turmas
        p = getattr(user, "profile", None)
        if not p:
            return

        allowed = {
            "MUNICIPAL": {"SECRETARIA", "UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
            "SECRETARIA": {"UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
            "UNIDADE": {"PROFESSOR", "ALUNO", "NEE", "LEITURA"},
        }

        role_me = (p.role or "").upper()
        if role_me in allowed:
            self.fields["role"].choices = [
                (value, label)
                for (value, label) in Profile.Role.choices
                if value in allowed[role_me]
            ]


        # =========================
        # MUNICÍPIO (fixo)
        # =========================
        if getattr(p, "municipio_id", None):
            self.fields["municipio"].queryset = Municipio.objects.filter(id=p.municipio_id)
            self.fields["municipio"].initial = p.municipio_id
            self.fields["municipio"].disabled = True

        # =========================
        # UNIDADE (fixa para gestor de escola)
        # =========================
        if getattr(p, "unidade_id", None):
            self.fields["unidade"].queryset = Unidade.objects.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id
            self.fields["unidade"].disabled = True

    def clean_cpf(self):
        cpf = (self.cleaned_data.get("cpf") or "").strip()
        digits = "".join(ch for ch in cpf if ch.isdigit())
        if len(digits) != 11:
            raise ValidationError("CPF inválido. Deve conter 11 dígitos.")
        return cpf



class UsuarioUpdateForm(forms.Form):
    first_name = forms.CharField(label="Nome", max_length=80)
    last_name = forms.CharField(label="Sobrenome", max_length=80, required=False)
    email = forms.EmailField(label="E-mail", required=False)

    cpf = forms.CharField(label="CPF", max_length=14, required=False)
    role = forms.ChoiceField(label="Função", choices=Profile.Role.choices)

    municipio = forms.ModelChoiceField(
        label="Município",
        queryset=Municipio.objects.filter(ativo=True).order_by("nome"),
        required=False,
    )
    unidade = forms.ModelChoiceField(
        label="Unidade",
        queryset=Unidade.objects.filter(ativo=True).order_by("nome"),
        required=False,
    )
    turmas = forms.ModelMultipleChoiceField(
        label="Turmas (somente para Professor)",
        queryset=Turma.objects.none(),
        required=False,
    )


    ativo = forms.BooleanField(label="Ativo", required=False)

    def __init__(self, *args, user=None, **kwargs):
        kwargs.pop("instance", None)   # <<< USUÁRIO QUE ESTÁ SENDO EDITADO
        edited_user = kwargs.pop("edited_user", None)
        super().__init__(*args, **kwargs)
        self.user = user

        # queryset de turmas (com escopo)
        qs_turmas = Turma.objects.select_related("unidade").all().order_by("-ano_letivo", "nome")
        if user and user.is_authenticated and not is_admin(user):
            qs_turmas = scope_filter_turmas(user, qs_turmas)
        self.fields["turmas"].queryset = qs_turmas

        # preenche seleção atual (se o usuário editado for professor e já tiver vínculo)
        if edited_user and hasattr(edited_user, "turmas_ministradas"):
            self.fields["turmas"].initial = list(
                edited_user.turmas_ministradas.values_list("pk", flat=True)
            )

        # ==== (mantém o resto do seu __init__ como já está) ====
        if not user or not user.is_authenticated:
            return

        p = getattr(user, "profile", None)
        if not p:
            return

        allowed = {
            "MUNICIPAL": {"SECRETARIA", "UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
            "SECRETARIA": {"UNIDADE", "PROFESSOR", "ALUNO", "NEE", "LEITURA"},
            "UNIDADE": {"PROFESSOR", "ALUNO", "NEE", "LEITURA"},
        }

        if p.role in allowed:
            self.fields["role"].choices = [(r, label) for r, label in Profile.Role.choices if r in allowed[p.role]]

        if getattr(p, "municipio_id", None):
            self.fields["municipio"].queryset = Municipio.objects.filter(id=p.municipio_id)
            self.fields["municipio"].initial = p.municipio_id
            self.fields["municipio"].disabled = True

        if getattr(p, "unidade_id", None):
            self.fields["unidade"].queryset = Unidade.objects.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id
            self.fields["unidade"].disabled = True



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
