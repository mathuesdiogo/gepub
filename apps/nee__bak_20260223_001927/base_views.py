from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch, reverse

from apps.core.views_gepub import (
    BaseCreateViewGepub,
    BaseDetailViewGepub,
    BaseListViewGepub,
    BaseUpdateViewGepub,
)
from apps.educacao.models import Aluno




class BaseAlunoMixin:
    """Mixin padrão NEE para telas vinculadas a um aluno.

    IMPORTANTE (padrão GEPUB):
    - O core (Base*ViewGepub) passa `request` para vários hooks.
    - Por isso, aqui mantemos assinaturas compatíveis com o core.
    """

    aluno_kwarg: str = "aluno_id"  # URL kwarg padrão: <int:aluno_id>

    def get_aluno_id(self) -> int | None:
        aluno_id = (
            self.kwargs.get(self.aluno_kwarg)
            or self.kwargs.get("pk_aluno")
            or self.request.GET.get("aluno")
        )
        try:
            return int(aluno_id) if aluno_id is not None else None
        except (TypeError, ValueError):
            return None

    def get_aluno(self) -> Aluno | None:
        if hasattr(self, "_aluno") and getattr(self, "_aluno") is not None:
            return self._aluno  # type: ignore[attr-defined]

        aluno_id = self.get_aluno_id()
        if aluno_id:
            self._aluno = get_object_or_404(Aluno, pk=aluno_id)  # type: ignore[attr-defined]
            return self._aluno  # type: ignore[attr-defined]

        # fallback: views de Detail/Update podem ter `object.aluno`
        obj = getattr(self, "object", None)
        if obj is not None:
            return getattr(obj, "aluno", None)

        return None

    # ---- Reverse helpers

    def _reverse_aluno(self, name: str, aluno_id: int | None = None) -> str:
        """Reverse tentando primeiro com aluno_id (args/kwargs), depois sem args."""
        aluno_id = aluno_id or self.get_aluno_id() or (getattr(self.get_aluno(), "pk", None) if self.get_aluno() else None)
        # 1) args
        if aluno_id is not None:
            try:
                return reverse(name, args=[aluno_id])
            except NoReverseMatch:
                pass
            # 2) kwargs
            try:
                return reverse(name, kwargs={self.aluno_kwarg: aluno_id})
            except NoReverseMatch:
                pass
        # 3) sem args
        return reverse(name)


    # ---- Context (assinatura compatível com o core)

    def get_context_data(self, request, **kwargs):  # noqa: D401
        ctx = super().get_context_data(request, **kwargs)
        aluno = self.get_aluno()
        if aluno:
            ctx["aluno"] = aluno
        return ctx


class BaseAlunoListView(BaseAlunoMixin, BaseListViewGepub):
    """ListView escopada por aluno."""

    back_url_name: str = "nee:aluno_hub"

    # BaseListViewGepub chama get_queryset(request)
    def get_queryset(self, request, *args, **kwargs):
        qs = super().get_queryset(request, *args, **kwargs)
        aluno = self.get_aluno()
        if aluno:
            qs = qs.filter(aluno=aluno)
        return qs

    def get_actions(self, q: str = "", **kwargs):
        aluno = self.get_aluno()
        aluno_id = aluno.pk if aluno else self.get_aluno_id()
        return [
            {
                "label": "Voltar",
                "url": self._reverse_aluno(self.back_url_name, aluno_id),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            }
        ]


class BaseAlunoCreateView(BaseAlunoMixin, BaseCreateViewGepub):
    """CreateView padrão para models com FK aluno.

    - Remove select gigante de aluno (o aluno vem da URL)
    - Evita o erro "takes 2 positional arguments but 3 were given"
      usando a assinatura do core: form_valid(request, form)
    """

    back_url_name: str = "nee:aluno_hub"

    def form_valid(self, request, form):
        aluno = self.get_aluno()
        if aluno and hasattr(form, "instance") and getattr(form, "instance", None) is not None:
            if getattr(form.instance, "aluno_id", None) is None:
                form.instance.aluno = aluno

        # se existir campo autor (ex.: Acompanhamento), define automaticamente
        if hasattr(form, "instance") and getattr(form, "instance", None) is not None:
            if getattr(form.instance, "autor_id", None) is None and hasattr(form.instance, "autor"):
                form.instance.autor = request.user

        return super().form_valid(request, form)

    def get_actions(self, q: str = "", **kwargs):
        aluno = self.get_aluno()
        aluno_id = aluno.pk if aluno else self.get_aluno_id()
        return [
            {
                "label": "Voltar",
                "url": self._reverse_aluno(self.back_url_name, aluno_id),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            }
        ]

    # BaseCreateViewGepub chama get_success_url(request, obj)
    def get_success_url(self, request, obj=None):
        aluno_id = getattr(obj, "aluno_id", None) or self.get_aluno_id() or (self.get_aluno().pk if self.get_aluno() else None)
        return self._reverse_aluno(self.back_url_name, aluno_id)


class BaseAlunoUpdateView(BaseAlunoMixin, BaseUpdateViewGepub):
    back_url_name: str = "nee:aluno_hub"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        aluno_id = getattr(obj, "aluno_id", None) or self.get_aluno_id()
        return [
            {
                "label": "Voltar",
                "url": self._reverse_aluno(self.back_url_name, aluno_id),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            }
        ]

    def get_success_url(self, request, obj=None):
        aluno_id = getattr(obj, "aluno_id", None) or self.get_aluno_id()
        return self._reverse_aluno(self.back_url_name, aluno_id)


class BaseAlunoDetailView(BaseAlunoMixin, BaseDetailViewGepub):
    back_url_name: str = "nee:aluno_hub"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        aluno_id = getattr(obj, "aluno_id", None) or self.get_aluno_id()
        return [
            {
                "label": "Voltar",
                "url": self._reverse_aluno(self.back_url_name, aluno_id),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            }
        ]
