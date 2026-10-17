"""URLs internes du dashboard — toutes sous `/dashboard/`, session Django (01_BACKEND.md §6)."""

from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("docs/", views.DocsView.as_view(), name="docs"),
    path("projects/", views.ProjectListView.as_view(), name="project-list"),
    path("projects/new/", views.ProjectCreateView.as_view(), name="project-create"),
    path("projects/<uuid:pk>/", views.ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<uuid:pk>/edit/", views.ProjectEditView.as_view(), name="project-edit"),
    path("projects/<uuid:pk>/delete/", views.ProjectDeleteView.as_view(), name="project-delete"),
    path(
        "projects/<uuid:pk>/reveal-secret/",
        views.ProjectRevealSecretView.as_view(),
        name="project-reveal-secret",
    ),
    path(
        "projects/<uuid:pk>/regenerate-secret/",
        views.ProjectRegenerateSecretView.as_view(),
        name="project-regenerate-secret",
    ),
    path("account/", views.AccountView.as_view(), name="account"),
    path("account/delete/", views.AccountDeleteView.as_view(), name="account-delete"),
    path("sessions/<uuid:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
]
