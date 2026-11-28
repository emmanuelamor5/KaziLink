from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from .forms import FreelancerRegistrationForm, HirerRegistrationForm, JobForm, RoleLoginForm
from .job_views import can_view_jobs
from .models import FreelancerProfile, HirerAccessCode, Job, JobApplication, User


@never_cache
def home(request):
    return render(request, "marketplace/home.html")


@never_cache
def roles(request, action):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "marketplace/roles.html", {"action": action})


class AccountLoginView(LoginView):
    template_name = "marketplace/auth.html"
    authentication_form = RoleLoginForm
    role = None

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "role": self.role}

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data["remember_me"]:
            self.request.session.set_expiry(
                timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE)
            )
        else:
            self.request.session.set_expiry(0)
        messages.success(self.request, "You’re signed in.")
        return response

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs), "role": self.role,
            "role_label": User.Role(self.role).label,
        }


@method_decorator(never_cache, name="dispatch")
class AccountPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = "marketplace/password_change.html"
    success_url = reverse_lazy("dashboard")
    success_message = "Your password was changed."


class RequirementAlreadyUsed(Exception):
    pass


@never_cache
@sensitive_post_parameters("password1", "password2", "document_number", "requirement_id")
def signup(request, role):
    if request.user.is_authenticated:
        return redirect("dashboard")
    is_freelancer = role == User.Role.FREELANCER
    form_class = FreelancerRegistrationForm if is_freelancer else HirerRegistrationForm
    form = form_class(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if not is_freelancer:
                    updated = HirerAccessCode.objects.filter(
                        digest=form.cleaned_data["requirement_id"], redeemed_at__isnull=True,
                    ).update(redeemed_at=timezone.now())
                    if not updated:
                        raise RequirementAlreadyUsed

                user = form.save(commit=False)
                user.role = role
                user.save()

                if is_freelancer:
                    FreelancerProfile.objects.create(
                        user=user, skills=form.cleaned_data["skills"],
                        available=form.cleaned_data["available"],
                        document_type=form.cleaned_data["document_type"],
                        document_hash=make_password(form.cleaned_data["document_number"]),
                    )
        except RequirementAlreadyUsed:
            form.add_error("requirement_id", "This hirer requirement ID has already been used.")
        except IntegrityError:
            if not User.objects.filter(username=form.cleaned_data["username"]).exists():
                raise
            form.add_error("username", "A user with that username already exists.")
        else:
            login(request, user)
            request.session.set_expiry(0)
            messages.success(request, "Your account has been created.")
            return redirect("dashboard")

    steps = [("Contact details", ("first_name", "last_name", "email"))]
    if is_freelancer:
        steps.extend([
            ("Work profile", ("location", "skills", "available")),
            ("Identification", ("document_type", "document_number")),
        ])
    else:
        steps.append(("Hirer details", ("location", "requirement_id")))
    steps.append(("Login details", ("username", "password1", "password2")))
    return render(request, "marketplace/auth.html", {
        "form": form, "role": role, "role_label": User.Role(role).label, "signup": True,
        "signup_steps": [(title, [form[name] for name in names]) for title, names in steps],
    })


@never_cache
@login_required
def dashboard(request):
    user = request.user
    context = {"can_view_jobs": can_view_jobs(user)}
    if user.role == User.Role.FREELANCER:
        context["profile"] = getattr(user, "freelancer_profile", None)
        applications = user.job_applications.select_related("job", "job__hirer").defer("resume_pdf")
        context["applications"] = applications
        context["invitation_count"] = applications.filter(status=JobApplication.Status.INVITED).count()
    elif user.role == User.Role.HIRER:
        context["posted_jobs"] = user.jobs.annotate(
            viewer_count=Count("views", distinct=True), applicant_count=Count("applications", distinct=True),
        )
    if context["can_view_jobs"]:
        jobs = Job.objects.filter(closed_at__isnull=True).select_related("hirer")
        query = request.GET.get("q", "").strip()[:100]
        if query:
            jobs = jobs.filter(
                Q(title__icontains=query) | Q(location__icontains=query)
                | Q(description__icontains=query) | Q(expectations__icontains=query)
            )
        context.update({"jobs": jobs, "search_query": query})
    return render(request, "marketplace/dashboard.html", context)


@never_cache
@login_required
def create_job(request):
    if request.user.role != User.Role.HIRER:
        raise PermissionDenied
    form = JobForm(
        request.POST if request.method == "POST" else None,
        initial={"location": request.user.location},
    )
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.hirer = request.user
        job.save()
        messages.success(request, "Your job has been posted.")
        return redirect("dashboard")
    return render(request, "marketplace/job_form.html", {"form": form})
