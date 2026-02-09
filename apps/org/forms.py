from django import forms

from .models import Municipio, Secretaria, Unidade, Setor


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = [
            "nome",
            "uf",
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


class SecretariaForm(forms.ModelForm):
    class Meta:
        model = Secretaria
        fields = "__all__"  # depois podemos restringir se você quiser

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if not user or not getattr(user, "is_authenticated", False):
            return

        from core.rbac import get_profile, is_admin
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

