"""URLs de l'API publique — aucune authentification (01_BACKEND.md §11)."""

from django.urls import path

from apps.public import views

app_name = "public"

urlpatterns = [
    path("registered-hosts/", views.RegisteredHostsView.as_view(), name="registered-hosts"),
    path("health/", views.HealthView.as_view(), name="health"),
]
