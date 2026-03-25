from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.rbac import role_scope_base
from apps.org.models import LocalEstrutural, Municipio, Secretaria, Setor, Unidade

from .services_access_matrix import preview_role_options, role_label

User = get_user_model()


class AccessPreviewForm(forms.Form):
    MODE_CHOICES = [
        ("profile", "Visualizar como perfil"),
        ("context", "Visualizar como função em contexto"),
        ("user", "Visualizar como usuário"),
    ]

    mode = forms.ChoiceField(label="Modo", choices=MODE_CHOICES)
    role = forms.ChoiceField(label="Perfil/Função", choices=())
    target_user = forms.ModelChoiceField(
        label="Usuário alvo",
        queryset=User.objects.none(),
        required=False,
        help_text="Opcional nos modos de perfil/contexto. Obrigatório no modo usuário.",
    )

    municipio = forms.ModelChoiceField(label="Município", queryset=Municipio.objects.none(), required=False)
    secretaria = forms.ModelChoiceField(label="Secretaria", queryset=Secretaria.objects.none(), required=False)
    unidade = forms.ModelChoiceField(label="Unidade", queryset=Unidade.objects.none(), required=False)
    setor = forms.ModelChoiceField(label="Setor", queryset=Setor.objects.none(), required=False)
    local_estrutural = forms.ModelChoiceField(
        label="Local estrutural",
        queryset=LocalEstrutural.objects.none(),
        required=False,
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, actor_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor_user = actor_user

        for name in [
            "mode",
            "role",
            "target_user",
            "municipio",
            "secretaria",
            "unidade",
            "setor",
            "local_estrutural",
        ]:
            self.fields[name].widget.attrs.update({"class": "gp-input"})

        role_choices = preview_role_options()
        self.fields["role"].choices = role_choices

        actor_profile = getattr(actor_user, "profile", None)
        actor_is_platform_admin = bool(
            getattr(actor_user, "is_superuser", False)
            or role_scope_base(getattr(actor_profile, "role", None)) == "ADMIN"
        )

        municipios_qs = Municipio.objects.filter(ativo=True).order_by("nome")
        secretarias_qs = Secretaria.objects.filter(ativo=True).order_by("nome")
        unidades_qs = Unidade.objects.filter(ativo=True).order_by("nome")
        setores_qs = Setor.objects.filter(ativo=True).order_by("nome")
        locais_qs = LocalEstrutural.objects.filter(status=LocalEstrutural.Status.ATIVO).order_by("nome")

        users_qs = User.objects.select_related(
            "profile",
            "profile__municipio",
            "profile__secretaria",
            "profile__unidade",
            "profile__setor",
            "profile__local_estrutural",
        ).filter(profile__isnull=False)

        if not actor_is_platform_admin and actor_profile:
            if getattr(actor_profile, "municipio_id", None):
                municipio_id = actor_profile.municipio_id
                municipios_qs = municipios_qs.filter(pk=municipio_id)
                secretarias_qs = secretarias_qs.filter(municipio_id=municipio_id)
                unidades_qs = unidades_qs.filter(secretaria__municipio_id=municipio_id)
                setores_qs = setores_qs.filter(unidade__secretaria__municipio_id=municipio_id)
                locais_qs = locais_qs.filter(municipio_id=municipio_id)
                users_qs = users_qs.filter(profile__municipio_id=municipio_id)
            if getattr(actor_profile, "secretaria_id", None):
                secretaria_id = actor_profile.secretaria_id
                secretarias_qs = secretarias_qs.filter(pk=secretaria_id)
                unidades_qs = unidades_qs.filter(secretaria_id=secretaria_id)
                setores_qs = setores_qs.filter(unidade__secretaria_id=secretaria_id)
                locais_qs = locais_qs.filter(secretaria_id=secretaria_id)
                users_qs = users_qs.filter(profile__secretaria_id=secretaria_id)
            if getattr(actor_profile, "unidade_id", None):
                unidade_id = actor_profile.unidade_id
                unidades_qs = unidades_qs.filter(pk=unidade_id)
                setores_qs = setores_qs.filter(unidade_id=unidade_id)
                locais_qs = locais_qs.filter(unidade_id=unidade_id)
                users_qs = users_qs.filter(profile__unidade_id=unidade_id)
            if getattr(actor_profile, "setor_id", None):
                users_qs = users_qs.filter(profile__setor_id=actor_profile.setor_id)
            if getattr(actor_profile, "local_estrutural_id", None):
                users_qs = users_qs.filter(profile__local_estrutural_id=actor_profile.local_estrutural_id)

        self.fields["municipio"].queryset = municipios_qs
        self.fields["secretaria"].queryset = secretarias_qs
        self.fields["unidade"].queryset = unidades_qs
        self.fields["setor"].queryset = setores_qs
        self.fields["local_estrutural"].queryset = locais_qs
        self.fields["target_user"].queryset = users_qs.order_by("first_name", "last_name", "username")[:500]

    @staticmethod
    def _scope_from_profile(profile) -> dict:
        return {
            "municipio_id": getattr(profile, "municipio_id", None),
            "secretaria_id": getattr(profile, "secretaria_id", None),
            "unidade_id": getattr(profile, "unidade_id", None),
            "setor_id": getattr(profile, "setor_id", None),
            "local_estrutural_id": getattr(profile, "local_estrutural_id", None),
            "aluno_id": getattr(profile, "aluno_id", None),
        }

    @staticmethod
    def _scope_type_from_scope(scope: dict) -> str:
        if scope.get("local_estrutural_id"):
            return "local_estrutural"
        if scope.get("setor_id"):
            return "setor"
        if scope.get("unidade_id"):
            return "unidade"
        if scope.get("secretaria_id"):
            return "secretaria"
        if scope.get("municipio_id"):
            return "municipio"
        return "global"

    def clean(self):
        cleaned_data = super().clean()
        mode = (cleaned_data.get("mode") or "").strip().lower()
        role = (cleaned_data.get("role") or "").strip().upper()
        target_user = cleaned_data.get("target_user")

        if mode == "user":
            if not target_user:
                self.add_error("target_user", "Selecione um usuário para visualizar esse contexto.")
                return cleaned_data
            target_profile = getattr(target_user, "profile", None)
            if not target_profile:
                self.add_error("target_user", "Usuário selecionado não possui perfil válido.")
                return cleaned_data
            resolved_role = (getattr(target_profile, "role", None) or "LEITURA").strip().upper()
            resolved_scope = self._scope_from_profile(target_profile)
            cleaned_data["resolved_preview_type"] = "USER"
        else:
            if not role:
                self.add_error("role", "Informe o perfil/função para iniciar a visualização.")
                return cleaned_data
            resolved_role = role
            resolved_scope = {
                "municipio_id": getattr(cleaned_data.get("municipio"), "pk", None),
                "secretaria_id": getattr(cleaned_data.get("secretaria"), "pk", None),
                "unidade_id": getattr(cleaned_data.get("unidade"), "pk", None),
                "setor_id": getattr(cleaned_data.get("setor"), "pk", None),
                "local_estrutural_id": getattr(cleaned_data.get("local_estrutural"), "pk", None),
                "aluno_id": None,
            }
            cleaned_data["resolved_preview_type"] = "CONTEXT" if mode == "context" else "PROFILE"

        cleaned_data["resolved_role"] = resolved_role
        cleaned_data["resolved_scope"] = resolved_scope
        cleaned_data["resolved_scope_type"] = self._scope_type_from_scope(resolved_scope)
        return cleaned_data

    def build_payload(self) -> dict:
        cleaned_data = self.cleaned_data
        target_user = cleaned_data.get("target_user")
        resolved_role = cleaned_data.get("resolved_role")
        resolved_scope = cleaned_data.get("resolved_scope") or {}
        mode = (cleaned_data.get("mode") or "profile").strip().lower()

        payload = {
            "active": True,
            "mode": mode,
            "preview_type": cleaned_data.get("resolved_preview_type", "PROFILE"),
            "role": resolved_role,
            "role_label": role_label(resolved_role),
            "target_user_id": getattr(target_user, "pk", None),
            "target_user_label": (target_user.get_full_name() or target_user.username).strip() if target_user else "",
            "scope": resolved_scope,
            "scope_type": cleaned_data.get("resolved_scope_type", "global"),
            "read_only": True,
            "started_at": timezone.now().isoformat(),
        }
        return payload
