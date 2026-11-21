from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters

from .forms import FreelancerRegistrationForm, HirerRegistrationForm, JobForm, RoleLoginForm
from .models import FreelancerProfile, HirerAccessCode, User


def home(request):
    return render(request, "marketplace/home.html")


def roles(request, action):
    return render(request, "marketplace/roles.html", {"action": action})


class AccountLoginView(LoginView):
    template_name = "marketplace/auth.html"
    authentication_form = RoleLoginForm
    role = None

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "role": self.role}

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs), "role": self.role,
            "role_label": User.Role(self.role).label,
        }


class RequirementAlreadyUsed(Exception):
    pass


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
            return redirect("dashboard")

    return render(request, "marketplace/auth.html", {
        "form": form, "role": role, "role_label": User.Role(role).label, "signup": True,
    })


@login_required
def dashboard(request):
    context = {}
    if request.user.role == User.Role.HIRER:
        context["jobs"] = request.user.jobs.all()
    elif request.user.role == User.Role.FREELANCER:
        context["profile"] = request.user.freelancer_profile
    return render(request, "marketplace/dashboard.html", context)


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
        return redirect("dashboard")
    return render(request, "marketplace/job_form.html", {"form": form})
