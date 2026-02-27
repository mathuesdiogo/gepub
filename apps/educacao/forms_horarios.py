from django import forms
from .models_horarios import AulaHorario


class AulaHorarioForm(forms.ModelForm):
    class Meta:
        model = AulaHorario
        fields = ["dia", "inicio", "fim", "disciplina", "professor", "sala", "observacoes"]

    def __init__(self, *args, grade=None, **kwargs):
        self.grade = grade
        super().__init__(*args, **kwargs)

        if self.grade is None and getattr(self.instance, "pk", None):
            self.grade = self.instance.grade

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("inicio")
        fim = cleaned.get("fim")
        dia = cleaned.get("dia")
        professor = cleaned.get("professor")
        sala = (cleaned.get("sala") or "").strip()

        if ini and fim and fim <= ini:
            self.add_error("fim", "A hora final deve ser maior que a hora inicial.")

        if not (self.grade and dia and ini and fim):
            return cleaned

        conflitos_turma = (
            AulaHorario.objects.filter(
                grade=self.grade,
                dia=dia,
                inicio__lt=fim,
                fim__gt=ini,
            )
            .exclude(pk=self.instance.pk)
        )
        if conflitos_turma.exists():
            conflito = conflitos_turma.select_related("grade__turma").first()
            self.add_error(
                None,
                (
                    "Conflito na turma: já existe aula nesse intervalo "
                    f"({conflito.inicio:%H:%M} às {conflito.fim:%H:%M})."
                ),
            )

        if professor:
            conflitos_professor = (
                AulaHorario.objects.filter(
                    dia=dia,
                    professor=professor,
                    inicio__lt=fim,
                    fim__gt=ini,
                )
                .exclude(pk=self.instance.pk)
                .select_related("grade__turma")
            )
            if conflitos_professor.exists():
                conflito = conflitos_professor.first()
                turma_nome = getattr(getattr(conflito, "grade", None), "turma", None)
                turma_nome = getattr(turma_nome, "nome", "outra turma")
                self.add_error(
                    "professor",
                    (
                        "Professor já alocado nesse horário "
                        f"na turma {turma_nome} ({conflito.inicio:%H:%M} às {conflito.fim:%H:%M})."
                    ),
                )

        if sala:
            conflitos_sala = (
                AulaHorario.objects.filter(
                    grade__turma__unidade_id=self.grade.turma.unidade_id,
                    dia=dia,
                    sala__iexact=sala,
                    inicio__lt=fim,
                    fim__gt=ini,
                )
                .exclude(pk=self.instance.pk)
                .select_related("grade__turma")
            )
            if conflitos_sala.exists():
                conflito = conflitos_sala.first()
                turma_nome = getattr(getattr(conflito, "grade", None), "turma", None)
                turma_nome = getattr(turma_nome, "nome", "outra turma")
                self.add_error(
                    "sala",
                    (
                        "Sala ocupada nesse intervalo "
                        f"na turma {turma_nome} ({conflito.inicio:%H:%M} às {conflito.fim:%H:%M})."
                    ),
                )

        return cleaned


# Compatibilidade com imports antigos
HorarioAulaForm = AulaHorarioForm
