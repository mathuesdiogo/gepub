from django.urls import path

from . import views

app_name = "comunicacao"

urlpatterns = [
    path("", views.index, name="index"),
    path("jobs/processar/", views.processar_fila, name="processar_fila"),
    path("jobs/requeue-failed/", views.requeue_failed_jobs, name="requeue_failed_jobs"),
    path("notifications/send", views.notifications_send, name="notifications_send"),
    path("notifications/trigger", views.notifications_trigger, name="notifications_trigger"),
    path("notifications/logs", views.notifications_logs, name="notifications_logs"),
    path("notifications/events-catalog", views.events_catalog_api, name="events_catalog_api"),
    path("templates/preview", views.template_preview_api, name="template_preview_api"),
    path("templates", views.templates_api, name="templates_api"),
    path("templates/<int:pk>", views.template_update_api, name="template_update_api"),
    path("channels/config", views.channels_config_api, name="channels_config_api"),
    path("channels/test", views.channel_test_api, name="channel_test_api"),
    path("tenant/settings", views.tenant_settings_api, name="tenant_settings_api"),
    path("webhooks/<str:provider>", views.provider_webhook_api, name="provider_webhook_api"),
]
