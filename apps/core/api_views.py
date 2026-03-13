from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.org.models import Municipio, Secretaria, SecretariaModuloAtivo, Unidade


class SecretariaSerializer(serializers.ModelSerializer):
    municipio_nome = serializers.CharField(source="municipio.nome", read_only=True)
    apps_ativos = serializers.SerializerMethodField()

    class Meta:
        model = Secretaria
        fields = (
            "id",
            "nome",
            "sigla",
            "tipo_modelo",
            "ativo",
            "municipio_id",
            "municipio_nome",
            "apps_ativos",
        )

    def get_apps_ativos(self, obj: Secretaria) -> list[str]:
        return [
            item.modulo
            for item in obj.modulos_ativos.all()
            if bool(getattr(item, "ativo", False))
        ]


class SecretariaListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SecretariaSerializer
    queryset = (
        Secretaria.objects.select_related("municipio")
        .prefetch_related("modulos_ativos")
        .order_by("nome")
    )
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "ativo": ["exact"],
        "tipo_modelo": ["exact"],
        "municipio_id": ["exact"],
    }
    search_fields = ["nome", "sigla", "municipio__nome"]
    ordering_fields = ["nome", "sigla", "municipio__nome", "id"]


class FrontendLabOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _month_label(dt):
        month_names = [
            "Jan",
            "Fev",
            "Mar",
            "Abr",
            "Mai",
            "Jun",
            "Jul",
            "Ago",
            "Set",
            "Out",
            "Nov",
            "Dez",
        ]
        return f"{month_names[dt.month - 1]}/{str(dt.year)[-2:]}"

    def get(self, request):
        municipio_id_raw = str(request.GET.get("municipio", "")).strip()
        municipio_id = int(municipio_id_raw) if municipio_id_raw.isdigit() else None

        municipios_qs = Municipio.objects.filter(ativo=True)
        secretarias_qs = Secretaria.objects.select_related("municipio")
        unidades_qs = Unidade.objects.all()
        modulos_qs = SecretariaModuloAtivo.objects.filter(ativo=True)

        if municipio_id:
            municipios_qs = municipios_qs.filter(pk=municipio_id)
            secretarias_qs = secretarias_qs.filter(municipio_id=municipio_id)
            modulos_qs = modulos_qs.filter(secretaria__municipio_id=municipio_id)
            unidades_qs = unidades_qs.filter(secretaria__municipio_id=municipio_id)

        top_modulos = list(
            modulos_qs.values("modulo")
            .annotate(total=Count("id"))
            .order_by("-total", "modulo")[:6]
        )
        top_modulos_payload = [
            {
                "nome": row["modulo"],
                "total": row["total"],
            }
            for row in top_modulos
        ]

        distribuicao_tipos = list(
            secretarias_qs.exclude(tipo_modelo="")
            .values("tipo_modelo")
            .annotate(total=Count("id"))
            .order_by("-total", "tipo_modelo")[:8]
        )
        distribuicao_tipos_payload = [
            {
                "nome": row["tipo_modelo"],
                "total": row["total"],
            }
            for row in distribuicao_tipos
        ]

        timeline_qs = (
            modulos_qs.annotate(mes=TruncMonth("criado_em"))
            .values("mes")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        timeline_map = {
            item["mes"].date().replace(day=1): item["total"]
            for item in timeline_qs
            if item.get("mes")
        }

        current = timezone.localdate().replace(day=1)
        range_months = []
        for _ in range(6):
            range_months.append(current)
            current = (current - timedelta(days=1)).replace(day=1)
        range_months.reverse()

        timeline_payload = [
            {
                "mes": self._month_label(month),
                "total": int(timeline_map.get(month, 0)),
            }
            for month in range_months
        ]

        municipios_payload = list(
            Municipio.objects.filter(ativo=True)
            .values("id", "nome", "uf")
            .order_by("nome")[:250]
        )

        return Response(
            {
                "kpis": {
                    "municipios": municipios_qs.count(),
                    "secretarias": secretarias_qs.count(),
                    "unidades": unidades_qs.count(),
                    "modulos": modulos_qs.count(),
                },
                "timeline": timeline_payload,
                "top_modulos": top_modulos_payload,
                "distribuicao_tipos": distribuicao_tipos_payload,
                "municipios": municipios_payload,
            }
        )
