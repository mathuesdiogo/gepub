from __future__ import annotations

from django import forms

from apps.accounts.forms import AlterarSenhaForm
from apps.org.models import Municipio


class WizardPasswordStepForm(AlterarSenhaForm):
    pass


class WizardAdminStepForm(forms.Form):
    nome_completo = forms.CharField(label="Nome completo", max_length=160)
    codigo_acesso = forms.CharField(label="Código de acesso", max_length=60)
    cpf = forms.CharField(label="CPF", max_length=14)
    cargo_funcao = forms.CharField(label="Cargo/Função", max_length=120)
    telefone_whatsapp = forms.CharField(label="Telefone/WhatsApp", max_length=20)
    email = forms.EmailField(label="E-mail")

    def clean_codigo_acesso(self):
        value = (self.cleaned_data.get("codigo_acesso") or "").strip().lower()
        if len(value) < 4:
            raise forms.ValidationError("Código de acesso deve ter ao menos 4 caracteres.")
        if not all(ch.isalnum() or ch in {".", "-", "_"} for ch in value):
            raise forms.ValidationError("Use apenas letras, números, ponto, hífen ou sublinhado.")
        return value

    def clean_cpf(self):
        value = (self.cleaned_data.get("cpf") or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 11:
            raise forms.ValidationError("CPF inválido. Informe 11 dígitos.")
        return value

    def clean_telefone_whatsapp(self):
        value = (self.cleaned_data.get("telefone_whatsapp") or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError("Telefone inválido. Informe DDD + número.")
        return value


class WizardMunicipioStepForm(forms.ModelForm):
    municipio_nome = forms.CharField(label="Município", max_length=120)
    uf = forms.CharField(label="UF", max_length=2)

    class Meta:
        model = Municipio
        fields = [
            "razao_social_prefeitura",
            "nome_fantasia_prefeitura",
            "cnpj_prefeitura",
            "email_prefeitura",
            "telefone_prefeitura",
            "site_prefeitura",
        ]

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        initial = kwargs.setdefault("initial", {})
        if instance is not None:
            initial.setdefault("municipio_nome", instance.nome)
            initial.setdefault("uf", instance.uf)
        super().__init__(*args, **kwargs)

    def clean_municipio_nome(self):
        return (self.cleaned_data.get("municipio_nome") or "").strip()

    def clean_uf(self):
        uf = (self.cleaned_data.get("uf") or "").strip().upper()
        if len(uf) != 2:
            raise forms.ValidationError("UF deve ter 2 letras.")
        return uf

    def clean_cnpj_prefeitura(self):
        value = (self.cleaned_data.get("cnpj_prefeitura") or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 14:
            raise forms.ValidationError("CNPJ inválido. Informe 14 dígitos.")
        return value


class WizardEnderecoStepForm(forms.Form):
    cep = forms.CharField(label="CEP", max_length=9)
    logradouro = forms.CharField(label="Rua/Avenida", max_length=180)
    numero = forms.CharField(label="Número", max_length=30)
    complemento = forms.CharField(label="Complemento", max_length=120, required=False)
    bairro = forms.CharField(label="Bairro", max_length=120)
    cidade = forms.CharField(label="Cidade", max_length=120)
    uf = forms.CharField(label="UF", max_length=2)
    latitude = forms.DecimalField(label="Latitude", required=False, decimal_places=7, max_digits=10)
    longitude = forms.DecimalField(label="Longitude", required=False, decimal_places=7, max_digits=10)

    def clean_cep(self):
        value = (self.cleaned_data.get("cep") or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 8:
            raise forms.ValidationError("CEP inválido. Use 8 dígitos.")
        return f"{digits[:5]}-{digits[5:]}"

    def clean_uf(self):
        uf = (self.cleaned_data.get("uf") or "").strip().upper()
        if len(uf) != 2:
            raise forms.ValidationError("UF deve ter 2 letras.")
        return uf

    def clean(self):
        cleaned = super().clean()
        lat = cleaned.get("latitude")
        lng = cleaned.get("longitude")
        if (lat is None) ^ (lng is None):
            self.add_error("latitude", "Latitude e longitude devem ser informadas juntas.")
            self.add_error("longitude", "Latitude e longitude devem ser informadas juntas.")
        return cleaned


class WizardSecretariasStepForm(forms.Form):
    secretaria_gestao = forms.BooleanField(required=False, initial=True)
    secretaria_educacao = forms.BooleanField(required=False, initial=True)
    secretaria_saude = forms.BooleanField(required=False, initial=True)

    secretaria_assistencia_social = forms.BooleanField(required=False)
    secretaria_financas = forms.BooleanField(required=False)
    secretaria_obras = forms.BooleanField(required=False)
    secretaria_agricultura = forms.BooleanField(required=False)
    secretaria_cultura = forms.BooleanField(required=False)
    secretaria_esporte = forms.BooleanField(required=False)
    secretaria_meio_ambiente = forms.BooleanField(required=False)
    secretaria_transporte = forms.BooleanField(required=False)

    secretarias_personalizadas = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Uma secretaria por linha"}),
    )

    def clean(self):
        cleaned = super().clean()
        cleaned["secretaria_gestao"] = True
        cleaned["secretaria_educacao"] = True
        cleaned["secretaria_saude"] = True
        return cleaned


class WizardUnidadesStepForm(forms.Form):
    escolas = forms.CharField(
        label="Escolas (Educação)",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Uma escola por linha"}),
    )
    unidades_saude = forms.CharField(
        label="Unidades de Saúde",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Uma unidade por linha"}),
    )
    setores_gestao = forms.CharField(
        label="Setores iniciais da Gestão",
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "Administração\nRH\nProtocolo\nTI\nCompras/Licitação"}
        ),
        initial="Administração\nRH\nProtocolo\nTI\nCompras/Licitação",
    )

    def _split_lines(self, value: str) -> list[str]:
        return [line.strip() for line in (value or "").splitlines() if line.strip()]

    def clean(self):
        cleaned = super().clean()
        if not self._split_lines(cleaned.get("escolas") or ""):
            self.add_error("escolas", "Informe ao menos 1 escola.")
        if not self._split_lines(cleaned.get("unidades_saude") or ""):
            self.add_error("unidades_saude", "Informe ao menos 1 unidade de saúde.")
        if not self._split_lines(cleaned.get("setores_gestao") or ""):
            self.add_error("setores_gestao", "Informe ao menos 1 setor de gestão.")
        return cleaned


class WizardUsuariosStepForm(forms.Form):
    gestao_nome = forms.CharField(label="Usuário Gestão - Nome", max_length=160)
    gestao_cpf = forms.CharField(label="Usuário Gestão - CPF", max_length=14)
    gestao_email = forms.EmailField(label="Usuário Gestão - E-mail")
    gestao_telefone = forms.CharField(label="Usuário Gestão - Telefone", max_length=20)

    educacao_nome = forms.CharField(label="Usuário Educação - Nome", max_length=160)
    educacao_cpf = forms.CharField(label="Usuário Educação - CPF", max_length=14)
    educacao_email = forms.EmailField(label="Usuário Educação - E-mail")
    educacao_telefone = forms.CharField(label="Usuário Educação - Telefone", max_length=20)

    saude_nome = forms.CharField(label="Usuário Saúde - Nome", max_length=160)
    saude_cpf = forms.CharField(label="Usuário Saúde - CPF", max_length=14)
    saude_email = forms.EmailField(label="Usuário Saúde - E-mail")
    saude_telefone = forms.CharField(label="Usuário Saúde - Telefone", max_length=20)

    def clean(self):
        cleaned = super().clean()
        for prefix in ("gestao", "educacao", "saude"):
            cpf = (cleaned.get(f"{prefix}_cpf") or "").strip()
            cpf_digits = "".join(ch for ch in cpf if ch.isdigit())
            if len(cpf_digits) != 11:
                self.add_error(f"{prefix}_cpf", "CPF inválido. Informe 11 dígitos.")

            tel = (cleaned.get(f"{prefix}_telefone") or "").strip()
            tel_digits = "".join(ch for ch in tel if ch.isdigit())
            if len(tel_digits) < 10:
                self.add_error(f"{prefix}_telefone", "Telefone inválido. Informe DDD + número.")

        emails = [
            (cleaned.get("gestao_email") or "").strip().lower(),
            (cleaned.get("educacao_email") or "").strip().lower(),
            (cleaned.get("saude_email") or "").strip().lower(),
        ]
        if len(set(e for e in emails if e)) < len([e for e in emails if e]):
            raise forms.ValidationError("Os e-mails dos usuários iniciais devem ser diferentes.")

        return cleaned


class WizardModulosStepForm(forms.Form):
    ativar_educacao = forms.BooleanField(required=False, initial=True)
    ativar_saude = forms.BooleanField(required=False, initial=True)
    ativar_nee = forms.BooleanField(required=False, initial=True)

    ano_letivo_atual = forms.IntegerField(label="Ano letivo atual", min_value=2000, max_value=2100)

    configurar_smtp = forms.BooleanField(required=False)
    configurar_whatsapp = forms.BooleanField(required=False)
    configurar_sms = forms.BooleanField(required=False)

    def clean(self):
        cleaned = super().clean()
        cleaned["ativar_educacao"] = True
        cleaned["ativar_saude"] = True
        return cleaned


class WizardRevisaoStepForm(forms.Form):
    confirmar = forms.BooleanField(label="Confirmo que os dados estão corretos", required=True)
