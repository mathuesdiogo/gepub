
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.educacao.models import Aluno


class BaseAlunoMixin:
    aluno_url_kwarg = "aluno_id"

    def get_aluno(self):
        if hasattr(self, "_aluno"):
            return self._aluno

        aluno_id = (
            self.kwargs.get("aluno_id")
            or self.kwargs.get("pk_aluno")
            or self.request.GET.get("aluno")
        )

        if aluno_id:
            self._aluno = get_object_or_404(Aluno, pk=aluno_id)
            return self._aluno

        if hasattr(self, "object") and self.object:
            return getattr(self.object, "aluno", None)

        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        aluno = self.get_aluno()
        if aluno:
            ctx["aluno"] = aluno
        return ctx


class BaseAlunoListView(BaseAlunoMixin, ListView):
    def get_queryset(self):
        qs = super().get_queryset()
        aluno = self.get_aluno()
        if aluno:
            qs = qs.filter(aluno=aluno)
        return qs


class BaseAlunoCreateView(BaseAlunoMixin, CreateView):
    def form_valid(self, form):
        aluno = self.get_aluno()
        if aluno:
            form.instance.aluno = aluno
        return super().form_valid(form)

    def get_success_url(self):
        aluno = self.get_aluno()
        return reverse("nee:aluno_hub", args=[aluno.pk])


class BaseAlunoUpdateView(BaseAlunoMixin, UpdateView):
    def get_success_url(self):
        aluno = self.get_aluno()
        return reverse("nee:aluno_hub", args=[aluno.pk])


class BaseAlunoDetailView(BaseAlunoMixin, DetailView):
    pass
