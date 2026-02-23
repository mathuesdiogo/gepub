from __future__ import annotations

"""
Base views do app NEE (padrão GEPUB).

Objetivo:
- Evitar o "ciclo" de bugs de assinatura (form_valid/get_context_data) entre
  Django CBVs e as BaseViews do core (apps.core.views_gepub).
- Padronizar o carregamento do aluno (scoping/RBAC) e o back_url.

IMPORTANTE:
Estas classes são para serem usadas junto das views do core:
BaseListViewGepub / BaseCreateViewGepub / BaseUpdateViewGepub / BaseDetailViewGepub.

Assinaturas esperadas pelas BaseViews do core:
- get_context_data(request, **kwargs)
- form_valid(request, form)
- get_success_url(request, obj=None)
"""

from django.urls import reverse
from django.shortcuts import get_object_or_404

from apps.core.views_gepub import (
    BaseListViewGepub,
    BaseCreateViewGepub,
    BaseUpdateViewGepub,
    BaseDetailViewGepub,
)

from apps.educacao.models import Aluno
from .utils import get_scoped_aluno


class AlunoContextMixin:
    """
    Resolve e injeta 'aluno' no contexto.
    - Por padrão, pega do kwargs['aluno_id'] (rotas /novo/<aluno_id>/ e /aluno/<aluno_id>/...)
    - Se não existir, tenta a partir do objeto (obj.aluno_id) quando possível.
    """
    aluno_kwarg: str = "aluno_id"
    aluno_context_name: str = "aluno"

    def get_aluno(self, request):
        # 1) via URL kwarg
        aluno_id = self.kwargs.get(self.aluno_kwarg)
        if aluno_id:
            # usa scoping/RBAC quando disponível
            try:
                aluno = get_scoped_aluno(request.user, int(aluno_id))
            except Exception:
                aluno = get_object_or_404(Aluno, pk=aluno_id)
            self._aluno = aluno
            return aluno

        # 2) via obj (detail/update)
        obj = getattr(self, "object", None) or getattr(self, "_obj", None)
        aluno_id = getattr(obj, "aluno_id", None)
        if aluno_id:
            try:
                aluno = get_scoped_aluno(request.user, int(aluno_id))
            except Exception:
                aluno = get_object_or_404(Aluno, pk=aluno_id)
            self._aluno = aluno
            return aluno

        return getattr(self, "_aluno", None)

    def get_context_data(self, request, **kwargs):
        ctx = super().get_context_data(request, **kwargs)
        aluno = self.get_aluno(request)
        if aluno is not None:
            ctx[self.aluno_context_name] = aluno
        return ctx

    # helper: voltar sempre pra HUB do NEE do aluno, a menos que a view sobrescreva
    def get_back_url(self, request):
        aluno = self.get_aluno(request)
        if aluno is None:
            return reverse("nee:index")

        back_name = getattr(self, "back_url_name", "") or ""
        if back_name:
            # back urls do NEE normalmente exigem aluno_id
            try:
                return reverse(back_name, args=[aluno.pk])
            except Exception:
                return reverse(back_name)
        return reverse("nee:aluno_hub", args=[aluno.pk])


class BaseAlunoListView(AlunoContextMixin, BaseListViewGepub):
    """Listagem 'por aluno'."""


class BaseAlunoCreateView(AlunoContextMixin, BaseCreateViewGepub):
    """Create 'por aluno': seta form.instance.aluno automaticamente."""

    def form_valid(self, request, form):
        aluno = self.get_aluno(request)
        if aluno is not None and hasattr(form, "instance"):
            form.instance.aluno = aluno
        return super().form_valid(request, form)


class BaseAlunoUpdateView(AlunoContextMixin, BaseUpdateViewGepub):
    """Update 'por aluno': mantém aluno no contexto."""


class BaseAlunoDetailView(AlunoContextMixin, BaseDetailViewGepub):
    """Detail 'por aluno': mantém aluno no contexto."""
