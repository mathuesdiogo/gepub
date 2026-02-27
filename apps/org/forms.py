from django import forms

from .models import (
    Municipio,
    Secretaria,
    Unidade,
    Setor,
    SecretariaTemplate,
    SecretariaConfiguracao,
    SecretariaCadastroBase,
)


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = [
            "nome",
            "uf",
            "slug_site",
            "dominio_personalizado",
            "cnpj_prefeitura",
            "razao_social_prefeitura",
            "nome_fantasia_prefeitura",
            "endereco_prefeitura",
            "telefone_prefeitura",
            "email_prefeitura",
            "site_prefeitura",
            "nome_prefeito",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Governador Nunes Freire"}),
            "uf": forms.TextInput(attrs={"placeholder": "Ex.: MA"}),
            "slug_site": forms.TextInput(attrs={"placeholder": "Ex.: governador-archer"}),
            "dominio_personalizado": forms.TextInput(attrs={"placeholder": "Ex.: prefeitura.exemplo.gov.br"}),
            "cnpj_prefeitura": forms.TextInput(attrs={"placeholder": "00.000.000/0000-00"}),
            "razao_social_prefeitura": forms.TextInput(attrs={"placeholder": "Razão social da Prefeitura"}),
            "nome_fantasia_prefeitura": forms.TextInput(attrs={"placeholder": "Prefeitura Municipal de ..."}),
            "endereco_prefeitura": forms.Textarea(attrs={"rows": 3, "placeholder": "Endereço completo (opcional)"}),
            "telefone_prefeitura": forms.TextInput(attrs={"placeholder": "(00) 0000-0000"}),
            "email_prefeitura": forms.EmailInput(attrs={"placeholder": "contato@prefeitura.gov.br"}),
            "site_prefeitura": forms.URLInput(attrs={"placeholder": "https://..."}),
            "nome_prefeito": forms.TextInput(attrs={"placeholder": "Nome do prefeito(a)"}),
        }

    def clean_uf(self):
        uf = (self.cleaned_data.get("uf") or "").strip().upper()
        if len(uf) != 2:
            raise forms.ValidationError("UF deve ter 2 letras (ex.: MA).")
        return uf

    def clean_cnpj_prefeitura(self):
        cnpj = (self.cleaned_data.get("cnpj_prefeitura") or "").strip()
        if not cnpj:
            return ""

        digits = "".join(ch for ch in cnpj if ch.isdigit())
        if len(digits) != 14:
            raise forms.ValidationError("CNPJ inválido. Deve conter 14 dígitos.")
        return cnpj

    def clean_slug_site(self):
        value = (self.cleaned_data.get("slug_site") or "").strip().lower()
        if not value:
            return value
        value = value.replace("_", "-").replace(".", "-")
        return value


class SecretariaForm(forms.ModelForm):
    class Meta:
        model = Secretaria
        fields = "__all__"  # depois podemos restringir se você quiser

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if not user or not getattr(user, "is_authenticated", False):
            return

        from apps.core.rbac import get_profile, is_admin
        p = get_profile(user)

        # MUNICIPAL: trava município no município do usuário
        if (not is_admin(user)) and p and p.municipio_id:
            if "municipio" in self.fields:
                self.fields["municipio"].queryset = Municipio.objects.filter(id=p.municipio_id)
                self.fields["municipio"].initial = p.municipio_id
                self.fields["municipio"].disabled = True




class UnidadeForm(forms.ModelForm):
    class Meta:
        model = Unidade
        fields = [
            "secretaria",
            "nome",
            "tipo",
            "codigo_inep",
            "cnpj",
            "endereco",
            "telefone",
            "email",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Escola Municipal ..."}),
            "codigo_inep": forms.TextInput(attrs={"placeholder": "Código INEP (opcional)"}),
            "cnpj": forms.TextInput(attrs={"placeholder": "00.000.000/0000-00 (opcional)"}),
            "endereco": forms.Textarea(attrs={"rows": 3, "placeholder": "Endereço completo (opcional)"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 0000-0000"}),
            "email": forms.EmailInput(attrs={"placeholder": "contato@..."}),
        }
class SetorForm(forms.ModelForm):
    class Meta:
        model = Setor
        fields = ["unidade", "nome", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Secretaria Escolar"}),
        }

class MunicipioContatoForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = ["email_prefeitura", "telefone_prefeitura", "endereco_prefeitura", "site_prefeitura"]


class OnboardingMunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = [
            "nome",
            "uf",
            "cnpj_prefeitura",
            "nome_prefeito",
            "email_prefeitura",
            "telefone_prefeitura",
            "endereco_prefeitura",
            "site_prefeitura",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome do município"}),
            "uf": forms.TextInput(attrs={"placeholder": "UF"}),
            "cnpj_prefeitura": forms.TextInput(attrs={"placeholder": "00.000.000/0000-00"}),
            "nome_prefeito": forms.TextInput(attrs={"placeholder": "Nome do(a) prefeito(a)"}),
            "email_prefeitura": forms.EmailInput(attrs={"placeholder": "contato@prefeitura.gov.br"}),
            "telefone_prefeitura": forms.TextInput(attrs={"placeholder": "(00) 0000-0000"}),
            "endereco_prefeitura": forms.Textarea(attrs={"rows": 3, "placeholder": "Endereço da prefeitura"}),
            "site_prefeitura": forms.URLInput(attrs={"placeholder": "https://..."}),
        }

    def clean_uf(self):
        return (self.cleaned_data.get("uf") or "").strip().upper()


class OnboardingTemplateActivationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        templates = list(kwargs.pop("templates", []))
        super().__init__(*args, **kwargs)
        self.templates = templates

        for tpl in templates:
            slug = tpl.slug
            self.fields[f"ativar_{slug}"] = forms.BooleanField(
                label=f"Ativar {tpl.nome}",
                required=False,
                widget=forms.CheckboxInput(
                    attrs={
                        "class": "onboard-app-card__toggle-input",
                        "data-onboard-template-toggle": slug,
                        "aria-label": f"Ativar {tpl.nome}",
                    }
                ),
            )
            self.fields[f"qtd_{slug}"] = forms.IntegerField(
                label=f"Quantidade ({tpl.nome})",
                required=False,
                min_value=1,
                max_value=5,
                initial=1,
                widget=forms.NumberInput(
                    attrs={
                        "class": "onboard-app-card__input",
                        "min": 1,
                        "max": 5,
                        "step": 1,
                        "inputmode": "numeric",
                        "placeholder": "1",
                    }
                ),
            )
            self.fields[f"nome_{slug}"] = forms.CharField(
                label=f"Nome final da secretaria ({tpl.nome})",
                required=False,
                max_length=160,
                widget=forms.TextInput(
                    attrs={
                        "class": "onboard-app-card__input",
                        "placeholder": f"Ex.: {tpl.nome}",
                    }
                ),
            )
            self.fields[f"sigla_{slug}"] = forms.CharField(
                label=f"Sigla ({tpl.nome})",
                required=False,
                max_length=30,
                widget=forms.TextInput(
                    attrs={
                        "class": "onboard-app-card__input onboard-app-card__input--sigla",
                        "placeholder": "Ex.: SEMED",
                        "maxlength": 30,
                    }
                ),
            )

    def clean(self):
        cleaned_data = super().clean()
        for tpl in self.templates:
            key = f"sigla_{tpl.slug}"
            sigla = (cleaned_data.get(key) or "").strip()
            if sigla:
                cleaned_data[key] = sigla.upper()
        return cleaned_data

    def get_ativacoes(self) -> list[dict]:
        ativacoes: list[dict] = []
        for tpl in self.templates:
            slug = tpl.slug
            if not self.cleaned_data.get(f"ativar_{slug}"):
                continue
            ativacoes.append(
                {
                    "template": tpl,
                    "qtd": int(self.cleaned_data.get(f"qtd_{slug}") or 1),
                    "nome": (self.cleaned_data.get(f"nome_{slug}") or "").strip(),
                    "sigla": (self.cleaned_data.get(f"sigla_{slug}") or "").strip(),
                }
            )
        return ativacoes


class SecretariaConfiguracaoForm(forms.ModelForm):
    class Meta:
        model = SecretariaConfiguracao
        fields = [
            "secretaria",
            "chave",
            "descricao",
            "valor",
        ]
        widgets = {
            "valor": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, secretaria: Secretaria | None = None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if secretaria is not None:
            self.fields["secretaria"].queryset = Secretaria.objects.filter(pk=secretaria.pk)
            self.fields["secretaria"].initial = secretaria.pk
            self.fields["secretaria"].disabled = True


class SecretariaCadastroBaseForm(forms.ModelForm):
    class Meta:
        model = SecretariaCadastroBase
        fields = [
            "secretaria",
            "categoria",
            "codigo",
            "nome",
            "ordem",
            "ativo",
            "metadata",
        ]
        widgets = {
            "metadata": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, secretaria: Secretaria | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if secretaria is not None:
            self.fields["secretaria"].queryset = Secretaria.objects.filter(pk=secretaria.pk)
            self.fields["secretaria"].initial = secretaria.pk
            self.fields["secretaria"].disabled = True
