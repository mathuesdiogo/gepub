from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from org.models import Municipio, Unidade
from .models import Profile

User = get_user_model()


class LoginCodigoForm(forms.Form):
    codigo_acesso = forms.CharField(label="Código de acesso", max_length=60)
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)


class AlterarSenhaPrimeiroAcessoForm(forms.Form):
    password1 = forms.CharField(label="Nova senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar nova senha", widget=forms.PasswordInput)


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
