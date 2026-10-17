"""
Vues templates du tableau de bord développeur (01_BACKEND.md §8, 06_FRONTEND_GUIDE.md §8).

Règles appliquées partout :
- `DeveloperRequiredMixin` sur toutes les vues ; `WritableDeveloperRequiredMixin` sur les
  actions d'écriture/sensibles (refus 403 pour un compte suspendu) ;
- aucune logique métier ici : les créations/régénérations passent par `apps/projects/services.py` ;
- isolation multi-tenant : on ne charge JAMAIS un projet par `pk` seul, toujours via
  `Project.objects.for_tenant(developer)` (404 si le projet appartient à un autre développeur).
"""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Value
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.generic import ListView, TemplateView, View

from apps.audit.models import AccessLog
from apps.dashboard.forms import AccountForm, ConfirmByNameForm, ProjectForm
from apps.dashboard.mixins import DeveloperRequiredMixin, WritableDeveloperRequiredMixin
from apps.dashboard.presenters import (
    CRITICAL_TYPES,
    LOG_KIND_LABELS,
    LOG_LEVEL_LABELS,
    label_for_type,
    log_row,
    present_event,
    sdk_status_row,
)
from apps.events.models import Event
from apps.projects.models import Project
from apps.projects.services import ProjectService
from apps.sdklogs.models import SdkLog
from apps.sdklogs.status import compute_sdk_status
from apps.sessions.models import ExamSession

from datetime import timedelta

# Onglets valides du détail projet. Un onglet inconnu ou absent retombe sur "overview"
# (06_FRONTEND_GUIDE.md §8.6).
PROJECT_TABS = {"overview", "keys", "sessions", "logs", "integration", "settings"}


def get_project_or_404(request, pk, *, include_archived=False):
    """Récupère un projet scopé sur le développeur courant, ou renvoie 404.

    404 (et non 403) pour un projet d'un autre développeur : on ne révèle pas son existence
    (06_FRONTEND_GUIDE.md §8, règle transversale).
    """
    qs = Project.objects.for_tenant(request.user.developer_profile)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return get_object_or_404(qs, pk=pk)


class HomeView(DeveloperRequiredMixin, TemplateView):
    """Accueil `/dashboard/` (06_FRONTEND_GUIDE.md §8.3)."""

    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        developer = self.request.user.developer_profile
        projects = Project.objects.for_tenant(developer).filter(is_archived=False)
        now = timezone.now()

        ctx["projects_count"] = projects.count()
        ctx["recent_projects"] = projects.order_by("-created_at")[:3]
        ctx["create_url"] = reverse("dashboard:project-create")

        # Sessions visibles = celles des projets (non archivés) du développeur.
        sessions = ExamSession.objects.for_tenant(developer).filter(project__is_archived=False)
        ctx["active_sessions_count"] = sessions.filter(status=ExamSession.Status.ACTIVE).count()

        events = Event.objects.for_tenant(developer).filter(
            session__project__is_archived=False,
            received_at__gte=now - timedelta(hours=24),
        )
        ctx["critical_events_24h"] = events.filter(type__in=CRITICAL_TYPES).count()

        # « Alertes à examiner » : 10 sessions des 7 derniers jours au risque ≥ seuil élevé,
        # triées par score décroissant (06_FRONTEND_GUIDE.md §8.3).
        ctx["alerts"] = list(
            sessions.filter(
                risk_score__gte=settings.RISK_THRESHOLDS["high"],
                started_at__gte=now - timedelta(days=7),
            )
            .select_related("project")
            .order_by("-risk_score")[:10]
        )
        return ctx


class DocsView(LoginRequiredMixin, TemplateView):
    """Documentation des ENDPOINTS, intégrée au dashboard (`/dashboard/docs/`).

    Contenu adapté au rôle : un **développeur** ne voit que les endpoints que sa plateforme
    (SDK / LMS) utilise pour communiquer avec le backend (API machine HMAC + API publique) ; le
    **superutilisateur** (propriétaire du système) voit en plus les surfaces de gestion (API JWT :
    authentification, projets, sessions). Le filtrage est fait dans le template.

    Pourquoi une page maison plutôt que Redoc : Redoc/Swagger chargent leur moteur depuis un CDN
    tiers ; si ce CDN est bloqué, la page reste blanche. Cette page est rendue CÔTÉ SERVEUR (les
    exemples de code sont colorés par Pygments, cf. `code_extras`). La documentation du SDK
    (JavaScript) fera l'objet d'une étape ultérieure.
    """

    template_name = "dashboard/docs.html"

    def dispatch(self, request, *args, **kwargs):
        # Un superutilisateur n'a pas forcément de profil Developer : on ne lui applique pas la
        # règle « espace développeur obligatoire » — il doit pouvoir documenter toutes les surfaces.
        if request.user.is_authenticated and not request.user.is_superuser:
            if getattr(request.user, "developer_profile", None) is None:
                messages.error(request, "Votre compte n'est pas rattaché à un espace développeur.")
                return redirect("account_login")
        return super().dispatch(request, *args, **kwargs)


class ProjectListView(DeveloperRequiredMixin, ListView):
    """Liste des projets `/dashboard/projects/` (UC-2, 06_FRONTEND_GUIDE.md §8.4)."""

    template_name = "dashboard/project_list.html"
    context_object_name = "projects"
    paginate_by = 25

    def get_queryset(self):
        developer = self.request.user.developer_profile
        qs = Project.objects.for_tenant(developer).filter(is_archived=False).order_by("-created_at")
        # Le compteur de sessions n'est ajouté que si l'app `sessions` est branchée (étape 2),
        # sinon l'annotation référencerait une relation inexistante.
        if _has_sessions():
            qs = qs.annotate(sessions_count=Count("exam_sessions"))
        else:
            qs = qs.annotate(sessions_count=Value(0))
        params = self.request.GET
        query = params.get("q", "").strip()
        if query:
            qs = qs.filter(name__icontains=query)

        # Filtre par état du projet (actif / suspendu / désactivé) — valeur contrôlée par liste
        # blanche : jamais de valeur arbitraire issue de l'URL.
        status = params.get("status", "").strip()
        if status in dict(Project.Status.choices):
            qs = qs.filter(status=status)

        # Filtre par période de création (bornes incluses, format <input type="date">).
        date_from = params.get("date_from", "").strip()
        date_to = params.get("date_to", "").strip()
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET
        ctx["q"] = params.get("q", "").strip()
        ctx["filter_status"] = params.get("status", "").strip()
        ctx["date_from"] = params.get("date_from", "").strip()
        ctx["date_to"] = params.get("date_to", "").strip()
        ctx["status_choices"] = Project.Status.choices
        ctx["has_filters"] = any(
            [ctx["q"], ctx["filter_status"], ctx["date_from"], ctx["date_to"]]
        )
        ctx["create_url"] = reverse("dashboard:project-create")
        return ctx


class ProjectCreateView(WritableDeveloperRequiredMixin, View):
    """Création d'un projet `/dashboard/projects/new/` (UC-2, §8.5)."""

    template_name = "dashboard/project_form.html"

    def _context(self, form):
        return {"form": form, "project_list_url": reverse("dashboard:project-list")}

    def get(self, request):
        return render(request, self.template_name, self._context(ProjectForm()))

    def post(self, request):
        form = ProjectForm(request.POST)
        if form.is_valid():
            # Toute la logique métier (création + génération des clés + audit) vit dans le service.
            project = ProjectService.create_project(
                request.user.developer_profile, **form.cleaned_data
            )
            messages.success(request, "Projet créé. Vos clés API sont prêtes.")
            url = reverse("dashboard:project-detail", args=[project.id]) + "?tab=keys"
            return redirect(url)
        return render(request, self.template_name, self._context(form))


class ProjectDetailView(DeveloperRequiredMixin, TemplateView):
    """Détail d'un projet à onglets `/dashboard/projects/<uuid>/` (§8.6)."""

    template_name = "dashboard/project_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = get_project_or_404(self.request, self.kwargs["pk"])
        tab = self.request.GET.get("tab", "overview")
        if tab not in PROJECT_TABS:
            tab = "overview"

        ctx["project"] = project
        ctx["tab"] = tab
        ctx["edit_url"] = reverse("dashboard:project-edit", args=[project.id])
        ctx["delete_url"] = reverse("dashboard:project-delete", args=[project.id])
        # URL du SDK injectée dans l'onglet « Intégration » (jamais codée en dur, §8.6.4).
        ctx["sdk_cdn_url"] = settings.SDK_CDN_URL
        # État de fonctionnement du SDK (en ligne / dégradé / hors ligne) : affiché sur la vue
        # d'ensemble ET en tête du journal.
        ctx["sdk_status"] = sdk_status_row(compute_sdk_status(project))

        if tab == "overview":
            sessions = project.exam_sessions.all()
            ctx["sessions_total"] = sessions.count()
            ctx["sessions_active"] = sessions.filter(status=ExamSession.Status.ACTIVE).count()
            ctx["events_30d"] = Event.objects.filter(
                session__project=project,
                received_at__gte=timezone.now() - timedelta(days=30),
            ).count()
        elif tab == "sessions":
            _fill_sessions_tab(ctx, project, self.request)
        elif tab == "logs":
            _fill_logs_tab(ctx, project, self.request)
        elif tab == "settings":
            # Le formulaire d'édition est réutilisé dans l'onglet Paramètres (mêmes validations
            # que §8.5) ; l'action du <form> pointe vers la vue d'édition.
            ctx["settings_form"] = ProjectForm(instance=project)
        return ctx


def _fill_sessions_tab(ctx, project, request):
    """Prépare la liste filtrée + paginée des sessions d'un projet (06 §8.6.3)."""
    qs = project.exam_sessions.select_related("project")

    exam_id = request.GET.get("exam_id", "").strip()
    student_id = request.GET.get("student_id", "").strip()
    status = request.GET.get("status", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if exam_id:
        qs = qs.filter(exam_id__icontains=exam_id)
    if student_id:
        qs = qs.filter(student_id__icontains=student_id)
    if status in dict(ExamSession.Status.choices):
        qs = qs.filter(status=status)
    # Période : bornes incluses sur la date de début (format HTML <input type="date">).
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)

    # Tri contrôlé par liste blanche : jamais de tri par un champ arbitraire fourni par l'URL.
    sort = request.GET.get("sort", "-started_at")
    allowed_sorts = {"started_at", "-started_at", "risk_score", "-risk_score", "exam_id", "-exam_id",
                     "student_id", "-student_id", "status", "-status"}
    qs = qs.order_by(sort if sort in allowed_sorts else "-started_at")

    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    ctx["sessions_page"] = page_obj
    ctx["sessions_count"] = page_obj.paginator.count
    # Compteur « N sessions pour l'examen X » (06 §8.6.3).
    ctx["filter_exam_id"] = exam_id
    ctx["filters"] = {
        "exam_id": exam_id,
        "student_id": student_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "sort": sort,
    }


def _fill_logs_tab(ctx, project, request):
    """Prépare la liste filtrée + paginée du journal SDK d'un projet (onglet « Journal SDK »)."""
    qs = SdkLog.objects.filter(project=project).select_related("session")

    level = request.GET.get("level", "").strip()
    kind = request.GET.get("kind", "").strip()
    query = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    # Valeurs contrôlées par liste blanche : jamais de valeur arbitraire issue de l'URL.
    if level in dict(SdkLog.Level.choices):
        qs = qs.filter(level=level)
    if kind in dict(SdkLog.Kind.choices):
        qs = qs.filter(kind=kind)
    if query:
        qs = qs.filter(message__icontains=query)
    # Période : bornes incluses sur la date de RÉCEPTION serveur (format <input type="date">).
    if date_from:
        qs = qs.filter(received_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(received_at__date__lte=date_to)

    # Tri par défaut : du plus récent au plus ancien (Meta.ordering) — pas de tri par l'URL.
    page_obj = Paginator(qs, 50).get_page(request.GET.get("page"))
    ctx["logs_page"] = page_obj
    ctx["logs_count"] = page_obj.paginator.count
    ctx["log_rows"] = [log_row(log) for log in page_obj.object_list]
    # (valeur, libellé lisible) pour l'alimentation des listes déroulantes de filtre.
    ctx["level_choices"] = [
        (value, LOG_LEVEL_LABELS.get(value, value)) for value, _ in SdkLog.Level.choices
    ]
    ctx["kind_choices"] = [
        (value, LOG_KIND_LABELS.get(value, value)) for value, _ in SdkLog.Kind.choices
    ]
    ctx["filters"] = {
        "level": level,
        "kind": kind,
        "q": query,
        "date_from": date_from,
        "date_to": date_to,
    }
    has_filters = any([level, kind, query, date_from, date_to])
    ctx["has_log_filters"] = has_filters

    # Flux temps réel (polling) : l'endpoint JSON renvoie les entrées reçues depuis `logs_since`.
    ctx["logs_feed_url"] = reverse("dashboard:project-logs-feed", args=[project.id])
    # On n'AJOUTE en tête que sur la 1re page sans filtre — sinon un ajout en tête violerait le
    # filtre / la pagination affichés (on se contente alors de rafraîchir le badge d'état).
    ctx["live_enabled"] = (page_obj.number == 1) and not has_filters
    latest = (
        SdkLog.objects.filter(project=project)
        .order_by("-received_at")
        .values_list("received_at", flat=True)
        .first()
    )
    ctx["logs_since"] = latest.isoformat() if latest else ""


class SessionDetailView(DeveloperRequiredMixin, TemplateView):
    """Détail d'une session + chronologie des événements (UC-6, 06 §8.8)."""

    template_name = "dashboard/session_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        developer = self.request.user.developer_profile
        # Isolation multi-tenant : 404 si la session appartient à un autre développeur.
        session = get_object_or_404(
            ExamSession.objects.for_tenant(developer).select_related("project"),
            pk=self.kwargs["pk"],
        )
        ctx["session"] = session
        ctx["project"] = session.project
        ctx["project_url"] = reverse("dashboard:project-detail", args=[session.project_id]) + "?tab=sessions"

        events = session.events.all()
        # Résumé : décompte par type, les plus fréquents d'abord (libellés lisibles).
        ctx["summary"] = [
            {"label": label_for_type(row["type"]), "n": row["n"]}
            for row in events.values("type").annotate(n=Count("id")).order_by("-n")
        ]
        ctx["summary_total"] = events.count()

        # Filtres de la chronologie (GET) : type, source, « critiques seulement ».
        type_filter = self.request.GET.get("type", "").strip()
        source_filter = self.request.GET.get("source", "").strip()
        critical_only = self.request.GET.get("critical") == "1"
        if type_filter in dict(Event.Type.choices):
            events = events.filter(type=type_filter)
        if source_filter in dict(Event.Source.choices):
            events = events.filter(source=source_filter)
        if critical_only:
            events = events.filter(type__in=CRITICAL_TYPES)

        # Tri CROISSANT sur l'horodatage (chronologie), 50 événements par page.
        page_obj = Paginator(events.order_by("occurred_at"), 50).get_page(self.request.GET.get("page"))
        # On pré-calcule la présentation lisible de chaque événement dans la vue (le template
        # ne doit pas appeler de logique Python ; il ne fait qu'afficher du texte).
        ctx["event_rows"] = [
            {"event": event, "presentation": present_event(event)} for event in page_obj.object_list
        ]
        ctx["events_page"] = page_obj
        ctx["type_choices"] = Event.Type.choices
        ctx["source_choices"] = Event.Source.choices
        ctx["filters"] = {"type": type_filter, "source": source_filter, "critical": critical_only}
        return ctx


def _has_sessions():
    """Vrai si le modèle ExamSession existe (étape 2). Évite de casser le détail projet
    avant que l'app `sessions` ne soit branchée."""
    from django.apps import apps

    return apps.is_installed("apps.sessions")


class ProjectEditView(WritableDeveloperRequiredMixin, View):
    """Modification d'un projet `/dashboard/projects/<uuid>/edit/` (§8.5)."""

    template_name = "dashboard/project_form.html"

    def get(self, request, pk):
        project = get_project_or_404(request, pk)
        return render(request, self.template_name, self._context(project, ProjectForm(instance=project)))

    def post(self, request, pk):
        project = get_project_or_404(request, pk)
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            ProjectService.update_project(project, **form.cleaned_data)
            messages.success(request, "Projet mis à jour.")
            return redirect("dashboard:project-detail", pk=project.id)
        return render(request, self.template_name, self._context(project, form))

    @staticmethod
    def _context(project, form):
        return {
            "form": form,
            "project": project,
            "project_list_url": reverse("dashboard:project-list"),
            "project_detail_url": reverse("dashboard:project-detail", args=[project.id]),
        }


class ProjectDeleteView(WritableDeveloperRequiredMixin, View):
    """Archivage d'un projet `/dashboard/projects/<uuid>/delete/` (§8.7).

    Voir la note de `apps/projects/models.py` : « suppression » = archivage (is_archived),
    pour rester compatible avec l'immuabilité des événements (§17 point 1).
    """

    template_name = "dashboard/project_confirm_delete.html"

    def get(self, request, pk):
        project = get_project_or_404(request, pk)
        form = ConfirmByNameForm(expected_value=project.name)
        return render(request, self.template_name, self._context(project, form))

    def post(self, request, pk):
        project = get_project_or_404(request, pk)
        form = ConfirmByNameForm(request.POST, expected_value=project.name)
        if form.is_valid():
            ProjectService.archive_project(project)
            messages.success(request, f"Le projet « {project.name} » a été archivé.")
            return redirect("dashboard:project-list")
        return render(request, self.template_name, self._context(project, form))

    @staticmethod
    def _context(project, form):
        return {
            "project": project,
            "form": form,
            "detail_url": reverse("dashboard:project-detail", args=[project.id]),
        }


@method_decorator(never_cache, name="dispatch")
class ProjectRevealSecretView(WritableDeveloperRequiredMixin, View):
    """Révélation de la clé secrète (UC-3, §8.6.2) — POST JSON uniquement.

    La réponse porte `Cache-Control: no-store` (via `never_cache`) et chaque appel écrit une
    entrée d'audit. La valeur n'apparaît jamais dans le HTML initial.
    """

    def post(self, request, pk):
        project = get_project_or_404(request, pk)
        AccessLog.record(
            action=AccessLog.Action.REVEAL_SECRET,
            actor=request.user,
            developer=project.developer,
            resource_type="Project",
            resource_id=str(project.id),
            request=request,
        )
        response = JsonResponse({"secret_key": project.secret_key})
        response["Cache-Control"] = "no-store"
        return response


class ProjectRegenerateSecretView(WritableDeveloperRequiredMixin, View):
    """Régénération de la clé secrète (UC-3, §8.6.2) — POST puis redirection."""

    def post(self, request, pk):
        project = get_project_or_404(request, pk)
        ProjectService.regenerate_secret_key(project, actor=request.user, request=request)
        messages.success(
            request,
            "Nouvelle clé secrète générée. L'ancienne est désormais invalide.",
        )
        url = reverse("dashboard:project-detail", args=[project.id]) + "?tab=keys"
        return redirect(url)


class _ProjectStatusChangeView(WritableDeveloperRequiredMixin, View):
    """Base des actions de cycle de vie d'un projet (suspendre / désactiver / réactiver).

    Toute la logique d'écriture (changement d'état + audit) vit dans `ProjectService` : ces vues
    ne font que résoudre le projet scopé sur le développeur, appeler le service et rediriger.
    """

    service_method = ""
    success_message = ""

    def post(self, request, pk):
        project = get_project_or_404(request, pk)
        getattr(ProjectService, self.service_method)(project, actor=request.user, request=request)
        messages.success(request, self.success_message.format(name=project.name))
        return redirect(self._next(request, project))

    @staticmethod
    def _next(request, project):
        # Retour à la page d'origine (liste ou détail) si elle est fournie et sûre.
        candidate = request.POST.get("next", "")
        if candidate and url_has_allowed_host_and_scheme(
            candidate,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return candidate
        return reverse("dashboard:project-detail", args=[project.id])


class ProjectSuspendView(_ProjectStatusChangeView):
    """Suspension d'un projet `/dashboard/projects/<uuid>/suspend/` (réversible)."""

    service_method = "suspend_project"
    success_message = "Le projet « {name} » a été suspendu."


class ProjectDisableView(_ProjectStatusChangeView):
    """Désactivation d'un projet `/dashboard/projects/<uuid>/disable/` (réversible)."""

    service_method = "disable_project"
    success_message = "Le projet « {name} » a été désactivé."


class ProjectReactivateView(_ProjectStatusChangeView):
    """Réactivation d'un projet `/dashboard/projects/<uuid>/reactivate/`."""

    service_method = "reactivate_project"
    success_message = "Le projet « {name} » a été réactivé."


@method_decorator(never_cache, name="dispatch")
class ProjectLogsFeedView(DeveloperRequiredMixin, View):
    """Flux JSON du journal SDK (`/dashboard/projects/<uuid>/logs/feed/`).

    Alimente le rafraîchissement temps réel de l'onglet « Journal SDK » : le navigateur interroge
    cet endpoint toutes les quelques secondes avec le paramètre `since` (dernier horodatage connu)
    et reçoit uniquement les entrées reçues depuis. La réponse porte aussi l'état courant du SDK.

    `never_cache` : un flux « temps réel » mis en cache afficherait des données périmées.
    """

    def get(self, request, pk):
        project = get_project_or_404(request, pk)

        # Scoping : le journal d'un autre projet n'est jamais atteignable (404 via le helper).
        qs = SdkLog.objects.filter(project=project).select_related("session")

        since_raw = request.GET.get("since", "").strip()
        since = parse_datetime(since_raw) if since_raw else None
        if since is not None and timezone.is_naive(since):
            # `since` est produit côté serveur (ISO, conscient du fuseau) ; on tolère néanmoins
            # une valeur naïve en la considérant dans le fuseau courant.
            since = timezone.make_aware(since)
        if since is not None:
            qs = qs.filter(received_at__gt=since)

        # Plafond de 100 : un onglet resté longtemps fermé ne doit pas recevoir un mur d'entrées.
        logs = qs.order_by("-received_at")[:100]
        return JsonResponse(
            {
                "status": sdk_status_row(compute_sdk_status(project)),
                "logs": [log_row(log) for log in logs],
            }
        )


class AccountView(DeveloperRequiredMixin, View):
    """Paramètres du compte `/dashboard/account/` (UC-1, §8.9)."""

    template_name = "dashboard/account.html"

    def _context(self, request, form):
        # Un compte 100 % social n'a pas de mot de passe utilisable : on propose alors de le
        # DÉFINIR plutôt que de le changer (06_FRONTEND_GUIDE.md §8.9).
        if request.user.has_usable_password():
            password_url = reverse("account_change_password")
            password_label = gettext_lazy("Changer le mot de passe")
        else:
            password_url = reverse("account_set_password")
            password_label = gettext_lazy("Définir un mot de passe")
        return {
            "form": form,
            "password_url": password_url,
            "password_label": password_label,
            "delete_url": reverse("dashboard:account-delete"),
        }

    def get(self, request):
        developer = request.user.developer_profile
        form = AccountForm(initial={"full_name": developer.full_name})
        return render(request, self.template_name, self._context(request, form))

    def post(self, request):
        developer = request.user.developer_profile
        form = AccountForm(request.POST)
        if form.is_valid():
            developer.full_name = form.cleaned_data["full_name"]
            developer.save(update_fields=["full_name"])
            messages.success(request, "Profil mis à jour.")
            return redirect("dashboard:account")
        return render(request, self.template_name, self._context(request, form))


class AccountDeleteView(DeveloperRequiredMixin, View):
    """Désactivation du compte `/dashboard/account/delete/` (§8.9, §17 point 1).

    Comportement provisoire aligné sur la logique d'archivage : on archive les projets du
    développeur et on désactive le compte (is_active=False) — la purge définitive relèvera
    d'une tâche de maintenance privilégiée. Point à valider (signalé).
    """

    template_name = "dashboard/account_confirm_delete.html"

    def _expected(self, request):
        return request.user.email

    def _context(self, request, form):
        return {"form": form, "cancel_url": reverse("dashboard:account")}

    def get(self, request):
        form = ConfirmByNameForm(expected_value=self._expected(request))
        return render(request, self.template_name, self._context(request, form))

    def post(self, request):
        form = ConfirmByNameForm(request.POST, expected_value=self._expected(request))
        if form.is_valid():
            developer = request.user.developer_profile
            for project in Project.objects.for_tenant(developer):
                ProjectService.archive_project(project)
            user = request.user
            user.is_active = False
            user.save(update_fields=["is_active"])
            logout(request)
            messages.success(request, "Votre compte a été désactivé.")
            return redirect("account_login")
        return render(request, self.template_name, self._context(request, form))
