from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

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

    ativo = forms.BooleanField(label="Ativo", required=False, initial=True)

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

    ativo = forms.BooleanField(label="Ativo", required=False)

    def clean_cpf(self):
        cpf = (self.cleaned_data.get("cpf") or "").strip()
        if not cpf:
            return ""
        digits = "".join(ch for ch in cpf if ch.isdigit())
        if len(digits) != 11:
            raise ValidationError("CPF inválido. Deve conter 11 dígitos.")
        return cpf

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
