from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from apps.core.api_views import FrontendLabOverviewAPIView, SecretariaListAPIView

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("frontend/overview/", FrontendLabOverviewAPIView.as_view(), name="frontend_overview"),
    path("frontend/secretarias/", SecretariaListAPIView.as_view(), name="frontend_secretarias"),
]
