"""URLs de l'API machine — HMAC uniquement (01_BACKEND.md §9). Sous `/api/v1/machine/`."""

from django.urls import path

from apps.machine_api import views

app_name = "machine_api"

urlpatterns = [
    path("sessions/", views.MachineSessionCreateView.as_view(), name="session-create"),
    path("sessions/<uuid:pk>/close/", views.MachineSessionCloseView.as_view(), name="session-close"),
    path("events/", views.MachineEventsView.as_view(), name="events"),
    path("logs/", views.MachineLogsView.as_view(), name="logs"),
]
